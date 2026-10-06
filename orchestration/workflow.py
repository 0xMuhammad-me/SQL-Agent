from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter
from typing import Any, Mapping, Sequence

import sqlglot
from sqlglot import exp

from agent_schemas import (
    QuerySpec,
    ReflectionResult,
    SQLGenerationResult,
    SQLReviewResult,
    RequestType,
)
from agent_schemas.agent_outputs import SQLParameter
from agents import (
    AnswerAgent,
    QuerySpecGeneratorAgent,
    ReflectionAgent,
    SQLGeneratorAgent,
    SQLRepairAgent,
    SQLReviewAgent,
)
from core.context import AgentContext
from errors import AgentError, PermissionDeniedError
from observability import AgentEvent, AgentLogger, AgentMetrics, EventType
from security import PIIGuard, PermissionManager, SecurityPolicy, SQLFirewall
from sql import (
    DatabaseExecutionResult,
    QueryCostGuard,
    ResultPolicy,
    SQLValidationResult,
    SQLValidator, CostGuardResult,
)
from tools.metadata_tools import RelevantMetadata

from .reflection_coordinator import ReflectionCoordinator


class WorkflowStatus(str, Enum):
    ANSWERED = "answered"
    CLARIFICATION_REQUIRED = "clarification_required"
    UNSUPPORTED = "unsupported"
    QUERY_SPEC_VALIDATION_FAILED = "query_spec_validation_failed"
    SQL_GENERATION_CLARIFICATION = "sql_generation_clarification"
    SQL_REVIEW_CLARIFICATION = "sql_review_clarification"
    SQL_REVIEW_FAILED = "sql_review_failed"
    SQL_VALIDATION_FAILED = "sql_validation_failed"
    SECURITY_REJECTED = "security_rejected"
    PERMISSION_DENIED = "permission_denied"
    COST_REJECTED = "cost_rejected"
    EXECUTION_FAILED = "execution_failed"
    REFLECTION_REJECTED = "reflection_rejected"
    INCONCLUSIVE = "inconclusive"
    AGENT_ERROR = "agent_error"
    SYSTEM_ERROR = "system_error"


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Backend result returned to the application boundary."""

    status: WorkflowStatus
    answer: str | None
    query_spec: QuerySpec | None
    sql: str | None
    parameters: Mapping[str, Any]
    reflection: ReflectionResult | None
    repair_attempts: int
    execution_ms: float
    trace_id: str
    issues: tuple[str, ...] = ()
    clarification_question: str | None = None


@dataclass(frozen=True, slots=True)
class _CandidateOutcome:
    status: WorkflowStatus | None
    sql: str
    parameters: Mapping[str, Any]

    issues: tuple[str, ...] = ()
    repairable: bool = False
    repair_instructions: tuple[str, ...] = ()

    result: DatabaseExecutionResult | None = None
    sanitized_rows: tuple[Mapping[str, Any], ...] = ()
    sanitized_metadata: Mapping[str, Any] = field(default_factory=dict)
    reflection: ReflectionResult | None = None


class SQLWorkflow:
    """Fixed backend-controlled Text-to-SQL execution workflow."""

    agent_name: str = "sql_workflow"

    def __init__(
            self,
            *,
            query_spec_generator: QuerySpecGeneratorAgent,
            sql_generator: SQLGeneratorAgent,
            sql_review_agent: SQLReviewAgent,
            sql_repair_agent: SQLRepairAgent,
            sql_validator: SQLValidator,
            sql_firewall: SQLFirewall,
            permission_manager: PermissionManager,
            security_policy: SecurityPolicy,
            pii_guard: PIIGuard,
            cost_guard: QueryCostGuard,
            database_executor: Any,
            result_policy: ResultPolicy,
            reflection_agent: ReflectionAgent,
            reflection_coordinator: ReflectionCoordinator,
            answer_agent: AnswerAgent,
            logger: AgentLogger,
            metrics: AgentMetrics | None = None,
            available_capabilities: Sequence[str] = (),
            dialect: str = "postgresql",
    ) -> None:
        self.query_spec_generator = query_spec_generator
        self.sql_generator = sql_generator
        self.sql_review_agent = sql_review_agent
        self.sql_repair_agent = sql_repair_agent
        self.sql_validator = sql_validator
        self.sql_firewall = sql_firewall
        self.permission_manager = permission_manager
        self.security_policy = security_policy
        self.pii_guard = pii_guard
        self.cost_guard = cost_guard
        self.database_executor = database_executor
        self.result_policy = result_policy
        self.reflection_agent = reflection_agent
        self.reflection_coordinator = reflection_coordinator
        self.answer_agent = answer_agent
        self.logger = logger
        self.metrics: AgentMetrics = metrics or AgentMetrics()
        self.available_capabilities = tuple(available_capabilities)
        self.dialect = dialect

    def run(self, *, context: AgentContext) -> WorkflowResult:

        started_at: float = perf_counter()
        self.metrics.record_request()
        self._log_request_started(context)

        query_spec: QuerySpec | None = None
        current_sql: str | None = None
        current_parameters: Mapping[str, Any] = {}
        reflection: ReflectionResult | None = None
        repair_attempts: int = 0
        try:
            query_spec = self.query_spec_generator.run(
                context=context,
                question=context.user_query,
                available_capabilities=self.available_capabilities,
            )

            if query_spec.request_type == RequestType.CLARIFICATION:
                return self._finish(
                    context=context,
                    status=WorkflowStatus.CLARIFICATION_REQUIRED,
                    answer=None,
                    query_spec=query_spec,
                    sql=None,
                    parameters={},
                    reflection=None,
                    repair_attempts=0,
                    started_at=started_at,
                    clarification_question=query_spec.clarification_question,
                )

            if query_spec.request_type == RequestType.UNSUPPORTED:
                return self._finish(
                    context=context,
                    status=WorkflowStatus.UNSUPPORTED,
                    answer=None,
                    query_spec=query_spec,
                    sql=None,
                    parameters={},
                    reflection=None,
                    repair_attempts=0,
                    started_at=started_at,
                    issues=(query_spec.unsupported_reason or "Unsupported request.",)
                )

            metadata_value: Any = context.get("_query_spec_metadata")

            if not isinstance(metadata_value, RelevantMetadata):
                raise AgentError("QuerySpec agent completed without valid retrieved metadata.")

            metadata: RelevantMetadata = metadata_value

            generation: SQLGenerationResult = self.sql_generator.run(
                context=context,
                question=context.user_query,
                query_spec=query_spec,
                schema_context=metadata.schema,
                relationship_context=metadata.relationships,
                business_context=metadata.business,
                metric_context=metadata.metrics,
                glossary_context=metadata.glossary,
                dialect=self.dialect,
            )

            if generation.status == "clarification_required":
                return self._finish(
                    context=context,
                    status=WorkflowStatus.SQL_GENERATION_CLARIFICATION,
                    answer=None,
                    query_spec=query_spec,
                    sql=None,
                    parameters={},
                    reflection=None,
                    repair_attempts=0,
                    started_at=started_at,
                    clarification_question=generation.clarification_question,
                )

            current_sql = generation.sql
            current_parameters = self._parameter_mapping(generation.parameters)

            while current_sql and repair_attempts <= self._max_repair_attempts():
                review: SQLReviewResult = self.sql_review_agent.run(
                    context=context,
                    question=context.user_query,
                    query_spec=query_spec,
                    sql=current_sql,
                    parameters=current_parameters,
                    schema_context=metadata.schema,
                    relationship_context=metadata.relationships,
                    business_context=metadata.business,
                    metric_context=metadata.metrics,
                    glossary_context=metadata.glossary,
                    dialect=self.dialect,
                )

                if review.verdict == "clarification_required":
                    return self._finish(
                        context=context,
                        status=WorkflowStatus.SQL_REVIEW_CLARIFICATION,
                        answer=None,
                        query_spec=query_spec,
                        sql=current_sql,
                        parameters=current_parameters,
                        reflection=None,
                        repair_attempts=repair_attempts,
                        started_at=started_at,
                        issues=tuple(
                            issue.description
                            for issue in review.issues
                        ),
                        clarification_question=review.clarification_question,
                    )

                if review.verdict == "fail":
                    return self._finish(
                        context=context,
                        status=WorkflowStatus.SQL_REVIEW_FAILED,
                        answer=None,
                        query_spec=query_spec,
                        sql=current_sql,
                        parameters=current_parameters,
                        reflection=None,
                        repair_attempts=repair_attempts,
                        started_at=started_at,
                        issues=tuple(
                            issue.description
                            for issue in review.issues
                        ),
                    )

                if review.verdict == "inconclusive":
                    return self._finish(
                        context=context,
                        status=WorkflowStatus.INCONCLUSIVE,
                        answer=None,
                        query_spec=query_spec,
                        sql=current_sql,
                        parameters=current_parameters,
                        reflection=None,
                        repair_attempts=repair_attempts,
                        started_at=started_at,
                        issues=tuple(
                            issue.description
                            for issue in review.issues
                        ),
                    )

                if review.verdict == "repair":
                    if repair_attempts >= self._max_repair_attempts():
                        return self._finish(
                            context=context,
                            status=WorkflowStatus.INCONCLUSIVE,
                            answer=None,
                            query_spec=query_spec,
                            sql=current_sql,
                            parameters=current_parameters,
                            reflection=None,
                            repair_attempts=repair_attempts,
                            started_at=started_at,
                            issues=(
                                "Maximum repair attempts reached "
                                "during SQL semantic review.",
                            ),
                        )

                    repair_issues: list[Mapping[str, Any]] = [
                        {
                            "type": issue.type,
                            "severity": issue.severity,
                            "description": issue.description,
                            "evidence": issue.evidence,
                        }
                        for issue in review.issues
                    ]

                    repair_issues.extend(
                        {
                            "type": "semantic",
                            "severity": "high",
                            "description": instruction,
                            "evidence": "SQLReviewAgent repair instruction.",
                        }
                        for instruction in review.repair_instructions
                    )

                    repaired = self.sql_repair_agent.run(
                        context=context,
                        question=context.user_query,
                        query_spec=query_spec,
                        current_sql=current_sql,
                        current_parameters=current_parameters,
                        issues=repair_issues,
                        repair_instructions=review.repair_instructions,
                        schema_context=metadata.schema,
                        relationship_context=metadata.relationships,
                        business_context=metadata.business,
                        metric_context=metadata.metrics,
                        glossary_context=metadata.glossary,
                        dialect=self.dialect,
                    )

                    repair_attempts += 1

                    if repaired.status != "repaired" or not repaired.sql:
                        return self._finish(
                            context=context,
                            status=WorkflowStatus.INCONCLUSIVE,
                            answer=None,
                            query_spec=query_spec,
                            sql=current_sql,
                            parameters=current_parameters,
                            reflection=None,
                            repair_attempts=repair_attempts,
                            started_at=started_at,
                            issues=tuple(issue.description for issue in review.issues),
                            clarification_question=repaired.clarification_question,
                        )

                    current_sql = repaired.sql
                    current_parameters = self._parameter_mapping(repaired.parameters)

                    continue

                outcome: _CandidateOutcome = self._evaluate_candidate(
                    context=context,
                    question=context.user_query,
                    query_spec=query_spec,
                    sql=current_sql,
                    parameters=current_parameters,
                    metadata=metadata,
                )

                if outcome.repairable and repair_attempts < self._max_repair_attempts():
                    repaired = self.sql_repair_agent.run(
                        context=context,
                        question=context.user_query,
                        query_spec=query_spec,
                        current_sql=current_sql,
                        current_parameters=current_parameters,
                        issues=[{"type": "sql_or_execution", "description": issue} for issue in outcome.issues],
                        repair_instructions=review.repair_instructions,
                        schema_context=metadata.schema,
                        relationship_context=metadata.relationships,
                        business_context=metadata.business,
                        metric_context=metadata.metrics,
                        glossary_context=metadata.glossary,
                        dialect=self.dialect,
                    )
                    repair_attempts += 1
                    if repaired.status != "repaired" or not repaired.sql:
                        return self._finish(
                            context=context,
                            status=WorkflowStatus.INCONCLUSIVE,
                            answer=None,
                            query_spec=query_spec,
                            sql=current_sql,
                            parameters=current_parameters,
                            reflection=outcome.reflection,
                            repair_attempts=repair_attempts,
                            started_at=started_at,
                            issues=outcome.issues,
                            clarification_question=repaired.clarification_question,
                        )
                    current_sql = repaired.sql
                    current_parameters = self._parameter_mapping(repaired.parameters)
                    continue

                if outcome.reflection is not None:
                    reflection = outcome.reflection
                    decision = self.reflection_coordinator.decide(reflection, repair_attempts=repair_attempts)
                    if decision.action == "accept":
                        answer: str = self.answer_agent.run(
                            context=context,
                            question=context.user_query,
                            result=outcome.sanitized_rows,
                            result_metadata=outcome.sanitized_metadata,
                        )
                        return self._finish(
                            context=context,
                            status=WorkflowStatus.ANSWERED,
                            answer=answer,
                            query_spec=query_spec,
                            sql=current_sql,
                            parameters=current_parameters,
                            reflection=reflection,
                            repair_attempts=repair_attempts,
                            started_at=started_at,
                        )
                    if decision.action == "repair" and repair_attempts < self._max_repair_attempts():
                        repaired = self.sql_repair_agent.run(
                            context=context,
                            question=context.user_query,
                            query_spec=query_spec,
                            current_sql=current_sql,
                            current_parameters=current_parameters,
                            issues=[
                                       {
                                           "type": issue.type,
                                           "severity": issue.severity,
                                           "description": issue.description,
                                           "evidence": issue.evidence,
                                       }
                                       for issue in reflection.issues
                                   ]
                                   + [
                                       {
                                           "type": "semantic",
                                           "severity": "high",
                                           "description": instruction,
                                           "evidence": "ReflectionAgent repair instruction.",
                                       }
                                       for instruction in decision.repair_instructions
                                   ],
                            repair_instructions=review.repair_instructions,
                            schema_context=metadata.schema,
                            relationship_context=metadata.relationships,
                            business_context=metadata.business,
                            metric_context=metadata.metrics,
                            glossary_context=metadata.glossary,
                            dialect=self.dialect,
                        )
                        repair_attempts += 1
                        if repaired.status != "repaired" or not repaired.sql:
                            return self._finish(
                                context=context,
                                status=WorkflowStatus.INCONCLUSIVE,
                                answer=None,
                                query_spec=query_spec,
                                sql=current_sql,
                                parameters=current_parameters,
                                reflection=reflection,
                                repair_attempts=repair_attempts,
                                started_at=started_at,
                                issues=decision.issues,
                                clarification_question=repaired.clarification_question,
                            )
                        current_sql = repaired.sql
                        current_parameters = self._parameter_mapping(repaired.parameters)

                        continue
                    if decision.action == "clarify":
                        return self._finish(
                            context=context,
                            status=WorkflowStatus.CLARIFICATION_REQUIRED,
                            answer=None,
                            query_spec=query_spec,
                            sql=current_sql,
                            parameters=current_parameters,
                            reflection=reflection,
                            repair_attempts=repair_attempts,
                            started_at=started_at,
                            issues=decision.issues,
                            clarification_question=decision.clarification_question,
                        )
                    if decision.action == "reject":
                        return self._finish(
                            context=context,
                            status=WorkflowStatus.REFLECTION_REJECTED,
                            answer=None,
                            query_spec=query_spec,
                            sql=current_sql,
                            parameters=current_parameters,
                            reflection=reflection,
                            repair_attempts=repair_attempts,
                            started_at=started_at,
                            issues=decision.issues,
                        )
                    return self._finish(
                        context=context,
                        status=WorkflowStatus.INCONCLUSIVE,
                        answer=None,
                        query_spec=query_spec,
                        sql=current_sql,
                        parameters=current_parameters,
                        reflection=reflection,
                        repair_attempts=repair_attempts,
                        started_at=started_at,
                        issues=decision.issues,
                    )

                return self._finish(
                    context=context,
                    status=outcome.status or WorkflowStatus.INCONCLUSIVE,
                    answer=None,
                    query_spec=query_spec,
                    sql=current_sql,
                    parameters=current_parameters,
                    reflection=None,
                    repair_attempts=repair_attempts,
                    started_at=started_at,
                    issues=outcome.issues,
                )

            return self._finish(
                context=context,
                status=WorkflowStatus.INCONCLUSIVE,
                answer=None,
                query_spec=query_spec,
                sql=current_sql,
                parameters=current_parameters,
                reflection=reflection,
                repair_attempts=repair_attempts,
                started_at=started_at,
                issues=("Repair budget exhausted.",),
            )
        except AgentError as exc:
            elapsed_ms = (perf_counter() - started_at) * 1000.0
            self.metrics.record_result(success=False, latency_ms=elapsed_ms)
            self.logger.log(
                AgentEvent(
                    event_type=EventType.ERROR,
                    trace_id=context.trace_id,
                    stage_name="workflow",
                    latency_ms=elapsed_ms,
                    status="error",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    metadata={
                        "category": exc.category,
                        "retryable": exc.retryable,
                        "cause_type": type(exc.cause).__name__ if exc.cause else None,
                        "cause_message": str(exc.cause)[:1000] if exc.cause else None,
                        "details": exc.details,
                    },
                )
            )
            return WorkflowResult(
                status=WorkflowStatus.AGENT_ERROR,
                answer=None,
                query_spec=query_spec,
                sql=current_sql,
                parameters=dict(current_parameters),
                reflection=reflection,
                repair_attempts=repair_attempts,
                execution_ms=elapsed_ms,
                trace_id=context.trace_id,
                issues=(str(exc),),
            )
        except Exception as exc:
            elapsed_ms = (perf_counter() - started_at) * 1000.0
            self.metrics.record_result(success=False, latency_ms=elapsed_ms)
            self.logger.log(
                AgentEvent(
                    event_type=EventType.ERROR,
                    trace_id=context.trace_id,
                    stage_name="workflow",
                    latency_ms=elapsed_ms,
                    status="error",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            )
            return WorkflowResult(
                status=WorkflowStatus.SYSTEM_ERROR,
                answer=None,
                query_spec=query_spec,
                sql=current_sql,
                parameters=dict(current_parameters),
                reflection=reflection,
                repair_attempts=repair_attempts,
                execution_ms=elapsed_ms,
                trace_id=context.trace_id,
                issues=(f"{type(exc).__name__}: {exc}",),
            )

    def _evaluate_candidate(
            self,
            *,
            context: AgentContext,
            question: str,
            query_spec: QuerySpec,
            sql: str,
            parameters: Mapping[str, Any],
            metadata: Any,
    ) -> _CandidateOutcome:
        validation: SQLValidationResult = self.sql_validator.validate(sql, parameters)
        self._log_sql_validation(context=context, validation=validation, supplied_parameters=parameters)

        if not validation.valid:
            return _CandidateOutcome(
                status=WorkflowStatus.SQL_VALIDATION_FAILED,
                sql=sql,
                parameters=parameters,
                issues=validation.issues,
                repairable=bool(validation.issues),
            )

        firewall = self.sql_firewall.validate(sql)
        self._log_firewall(context, firewall.allowed, firewall.issues)
        if not firewall.allowed:
            return _CandidateOutcome(
                status=WorkflowStatus.SECURITY_REJECTED,
                sql=sql,
                parameters=parameters,
                issues=firewall.issues,
                repairable=False,
            )

        pii_columns: tuple[str, ...] = self.pii_guard.find_pii_columns(validation.columns)
        aggregated: bool = self._is_aggregated(sql)
        role_name: str = str(context.metadata.get("role_name", self.security_policy.role_name))
        try:
            self.permission_manager.check_query(
                role_name=role_name,
                tables=validation.tables,
                pii_columns=pii_columns,
                is_aggregated=aggregated,
                policy=self.security_policy,
            )
        except PermissionDeniedError as exc:
            self._log_permission(context, allowed=False, message=str(exc))
            return _CandidateOutcome(
                status=WorkflowStatus.PERMISSION_DENIED,
                sql=sql,
                parameters=parameters,
                issues=(str(exc),),
                repairable=False,
            )

        self._log_permission(context, allowed=True, message="Permission check passed.")
        cost = self.cost_guard.validate(sql, parameters)
        self._log_cost(context, cost)
        if not cost.allowed:
            status: WorkflowStatus = WorkflowStatus.COST_REJECTED if cost.status.value == "too_expensive" else WorkflowStatus.INCONCLUSIVE
            return _CandidateOutcome(status=status, sql=sql, parameters=parameters,
                                     issues=(cost.reason or "Cost check inconclusive.",), repairable=False)

        execution: DatabaseExecutionResult = self.database_executor.execute(sql, parameters)

        self.logger.log(
            AgentEvent(
                event_type=EventType.SQL_EXECUTED,
                trace_id=context.trace_id,
                agent_name=self.agent_name,
                stage_name="database_execution",
                output_data={
                    "success": execution.success,
                    "row_count": execution.row_count,
                    "execution_ms": execution.execution_ms,
                    "truncated": execution.truncated,
                    "error_type": execution.error_type,
                },
                latency_ms=execution.execution_ms,
                status="success" if execution.success else "error",
            )
        )

        if not execution.success:
            repairable: bool = execution.error_type not in {
                "OperationalError",
                "InterfaceError",
                "ConnectionException",
                "TimeoutError",
            }
            return _CandidateOutcome(
                status=WorkflowStatus.EXECUTION_FAILED,
                sql=sql,
                parameters=parameters,
                result=execution,
                issues=(execution.error_message or "Database execution failed.",),
                repairable=repairable,
            )

        allow_pii: bool = self.security_policy.allow_pii_access
        sanitized = self.result_policy.apply(execution.rows, allow_pii=allow_pii)
        self.logger.log(
            AgentEvent(
                event_type=EventType.RESULT_POLICY_APPLIED,
                trace_id=context.trace_id,
                stage_name="result_policy",
                output_data={"row_count": sanitized.row_count, "truncated": sanitized.truncated,
                             "redacted_pii": sanitized.redacted_pii},
                status="success",
            )
        )

        metadata_map: dict[str, Any] = {
            "row_count": sanitized.row_count,
            "columns": list(sanitized.columns),
            "truncated": sanitized.truncated,
            "execution_ms": execution.execution_ms,
            "status": "success",
            "cost": cost.estimated_cost,
            "estimated_rows": cost.estimated_rows,
        }

        reflection: ReflectionResult = self.reflection_agent.run(
            context=context,
            question=question,
            query_spec=query_spec,
            sql=sql,
            execution_result=sanitized.rows,
            execution_metadata=metadata_map,
            schema_context=metadata.schema,
            relationship_context=metadata.relationships,
            business_context=metadata.business,
            metric_context=metadata.metrics,
            glossary_context=metadata.glossary,
        )
        self.logger.log(
            AgentEvent(
                event_type=EventType.REFLECTION_COMPLETED,
                trace_id=context.trace_id,
                stage_name="reflection",
                output_data={"verdict": reflection.verdict, "confidence": reflection.confidence},
                status="success",
            )
        )

        return _CandidateOutcome(
            status=None,
            sql=sql,
            parameters=parameters,
            result=execution,
            sanitized_rows=sanitized.rows,
            sanitized_metadata=metadata_map,
            reflection=reflection,
        )

    @staticmethod
    def _parameter_mapping(parameters: Sequence[SQLParameter]) -> dict[str, Any]:
        return {parameter.name: parameter.value for parameter in parameters}

    @staticmethod
    def _is_aggregated(sql: str) -> bool:
        try:
            parsed = sqlglot.parse_one(sql, read="postgres")
        except Exception:
            return False
        return bool(parsed.find(exp.AggFunc) or parsed.find(exp.Group))

    def _max_repair_attempts(self) -> int:
        return self.reflection_coordinator.max_repair_attempts

    def _log_request_started(self, context: AgentContext) -> None:
        self.logger.log(
            AgentEvent(
                event_type=EventType.REQUEST_STARTED,
                trace_id=context.trace_id,
                stage_name="workflow",
                input_data={"question_length": len(context.user_query)},
                status="started",
            )
        )

    # def _log_query_spec_validation(
    #         self,
    #         *,
    #         context: AgentContext,
    #         validation: QuerySpecValidationResult,
    # ) -> None:
    #     self.logger.log(
    #         AgentEvent(
    #             event_type=EventType.QUERY_SPEC_VALIDATED,
    #             trace_id=context.trace_id,
    #             agent_name=self.agent_name,
    #             stage_name="query_spec_validation",
    #             output_data={
    #                 "valid": validation.valid,
    #                 "issue_count": len(validation.issues),
    #                 "issues": list(validation.issues),
    #             },
    #             status="success" if validation.valid else "error",
    #         )
    #     )

    def _log_sql_validation(
            self,
            *,
            context: AgentContext,
            validation: SQLValidationResult,
            supplied_parameters: Mapping[str, Any],
    ) -> None:
        self.logger.log(
            AgentEvent(
                event_type=EventType.SQL_VALIDATED,
                trace_id=context.trace_id,
                stage_name="sql_validation",
                output_data={
                    "valid": validation.valid,
                    "issue_count": len(validation.issues),
                    "issues": list(validation.issues),
                    "parameters_used": list(validation.parameters_used),
                    "supplied_parameter_names": sorted(
                        str(name)
                        for name in supplied_parameters
                    ),
                },
                status="success" if validation.valid else "error",
            )
        )

    def _log_firewall(self, context: AgentContext, allowed: bool, issues: Sequence[str]) -> None:
        self.logger.log(
            AgentEvent(
                event_type=EventType.SQL_FIREWALL_CHECKED,
                trace_id=context.trace_id,
                stage_name="sql_firewall",
                output_data={"allowed": allowed, "issue_count": len(issues)},
                status="success" if allowed else "error",
            )
        )

    def _log_permission(self, context: AgentContext, *, allowed: bool, message: str) -> None:
        self.logger.log(
            AgentEvent(
                event_type=EventType.PERMISSION_CHECKED,
                trace_id=context.trace_id,
                stage_name="permissions",
                output_data={"allowed": allowed, "message": message},
                status="success" if allowed else "error",
            )
        )

    def _log_cost(self, context: AgentContext, result: CostGuardResult) -> None:
        self.logger.log(
            AgentEvent(
                event_type=EventType.QUERY_COST_CHECKED,
                trace_id=context.trace_id,
                stage_name="query_cost",
                output_data={
                    "status": result.status.value,
                    "estimated_cost": result.estimated_cost,
                    "estimated_rows": result.estimated_rows,
                    "reason": result.reason,
                },
                status="success" if result.status.value == "allowed" else "error",
            )
        )

    @staticmethod
    def _failed_stage_for_status(status: WorkflowStatus) -> str | None:
        mapping: dict[WorkflowStatus, str] = {
            WorkflowStatus.QUERY_SPEC_VALIDATION_FAILED: "query_spec_validation",
            WorkflowStatus.SQL_VALIDATION_FAILED: "sql_validation",
            WorkflowStatus.SECURITY_REJECTED: "sql_firewall",
            WorkflowStatus.PERMISSION_DENIED: "permissions",
            WorkflowStatus.COST_REJECTED: "query_cost",
            WorkflowStatus.EXECUTION_FAILED: "database_execution",
            WorkflowStatus.REFLECTION_REJECTED: "reflection",
            WorkflowStatus.AGENT_ERROR: "agent",
            WorkflowStatus.SYSTEM_ERROR: "workflow",
            WorkflowStatus.SQL_REVIEW_CLARIFICATION: "sql_review",
            WorkflowStatus.SQL_REVIEW_FAILED: "sql_review",
        }
        return mapping.get(status)

    @staticmethod
    def _request_log_status(status: WorkflowStatus) -> str:
        error_statuses: frozenset[WorkflowStatus] = frozenset(
            {
                WorkflowStatus.QUERY_SPEC_VALIDATION_FAILED,
                WorkflowStatus.SQL_VALIDATION_FAILED,
                WorkflowStatus.SECURITY_REJECTED,
                WorkflowStatus.PERMISSION_DENIED,
                WorkflowStatus.COST_REJECTED,
                WorkflowStatus.EXECUTION_FAILED,
                WorkflowStatus.REFLECTION_REJECTED,
                WorkflowStatus.AGENT_ERROR,
                WorkflowStatus.SYSTEM_ERROR,
                WorkflowStatus.SQL_REVIEW_CLARIFICATION,
                WorkflowStatus.SQL_REVIEW_FAILED,
            }
        )

        if status in error_statuses:
            return "error"

        if status == WorkflowStatus.ANSWERED:
            return "success"

        return "completed"

    def _finish(
            self,
            *,
            context: AgentContext,
            status: WorkflowStatus,
            answer: str | None,
            query_spec: QuerySpec | None,
            sql: str | None,
            parameters: Mapping[str, Any],
            reflection: ReflectionResult | None,
            repair_attempts: int,
            started_at: float,
            issues: Sequence[str] = (),
            clarification_question: str | None = None,
    ) -> WorkflowResult:
        elapsed_ms: float = (perf_counter() - started_at) * 1000.0
        result = WorkflowResult(
            status=status,
            answer=answer,
            query_spec=query_spec,
            sql=sql,
            parameters=dict(parameters),
            reflection=reflection,
            repair_attempts=repair_attempts,
            execution_ms=elapsed_ms,
            trace_id=context.trace_id,
            issues=tuple(issues),
            clarification_question=clarification_question,
        )
        self.metrics.record_result(success=status == WorkflowStatus.ANSWERED, latency_ms=elapsed_ms)
        failed_stage: str | None = self._failed_stage_for_status(status)
        request_status: str = self._request_log_status(status)
        self.logger.log(
            AgentEvent(
                event_type=EventType.REQUEST_COMPLETED,
                trace_id=context.trace_id,
                agent_name=self.agent_name,
                stage_name="workflow",
                output_data={
                    "status": status.value,
                    "failed_stage": failed_stage,
                    "issue_count": len(issues),
                    "issues": list(issues),
                    "repair_attempts": repair_attempts,
                },
                latency_ms=elapsed_ms,
                status=request_status,
            )
        )
        return result
