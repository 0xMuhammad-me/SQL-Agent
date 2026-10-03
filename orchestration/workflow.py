from __future__ import annotations

import time

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence

from core.context import AgentContext

from errors.exceptions import SQLValidationError

from memory.memory_retriever import (
    MemoryContext,
    MemoryRetriever,
)

from agent_schemas.agent_outputs import (
    ReflectionResult,
    SQLGenerationResult,
    SQLRepairResult,
)

from agent_schemas.query_spec import (
    QuerySpec,
    RequestType,
)

from observability.events import (
    AgentEvent,
    EventType,
)

from observability.logger import AgentLogger

from orchestration.reflection import (
    ReflectionCoordinator,
)

from agents.answer_agent import AnswerAgent
from agents.query_spec_generator_agent import (
    QuerySpecGeneratorAgent,
)
from agents.reflection_agent import (
    ReflectionAgent,
)
from agents.sql_generator_agent import (
    SQLGeneratorAgent,
)
from agents.sql_repair_agent import (
    SQLRepairAgent,
)

from metadata.relationship_catalog import (
    RELATIONSHIPS,
)


class WorkflowStatus(str, Enum):
    """
    Final status of a workflow execution.
    """

    SUCCESS = "success"
    CLARIFICATION_REQUIRED = "clarification_required"
    UNSUPPORTED = "unsupported"
    VALIDATION_FAILED = "validation_failed"
    EXECUTION_FAILED = "execution_failed"
    REFLECTION_FAILED = "reflection_failed"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class SQLValidationOutput:
    """
    Normalized SQL validator result.

    The concrete sql/validator.py implementation can map its result
    into this structure.
    """

    valid: bool
    issues: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class CostGuardOutput:
    """
    Normalized query cost validation result.
    """

    allowed: bool
    estimated_cost: float | None = None
    reason: str | None = None


@dataclass(frozen=True)
class DatabaseExecutionOutput:
    """
    Normalized database execution result.
    """

    rows: Sequence[Mapping[str, Any]]
    row_count: int
    execution_ms: float
    success: bool
    error_code: str | None = None


@dataclass(frozen=True)
class SanitizedResult:
    """
    Result after result policy, row limiting, and privacy processing.
    """

    rows: Sequence[Mapping[str, Any]]
    row_count: int
    truncated: bool
    columns: tuple[str, ...]
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class WorkflowResult:
    """
    Public result returned to the application layer.
    """

    status: WorkflowStatus
    answer: str | None
    query_spec: QuerySpec | None
    sql: str | None
    parameters: Mapping[str, Any]
    reflection: ReflectionResult | None
    repair_attempts: int
    execution_ms: float
    trace_id: str


class SQLValidator(Protocol):
    """
    Backend SQL validation interface.
    """

    def validate(self, sql: str, *, parameters: Mapping[str, Any]) -> SQLValidationOutput:
        ...


class QueryCostGuard(Protocol):
    """
    Backend query cost validation interface.
    """

    def validate(self, sql: str, *, parameters: Mapping[str, Any]) -> CostGuardOutput:
        ...


class DatabaseExecutor(Protocol):
    """
    Read-only database execution interface.
    """

    def execute(self, sql: str, *, parameters: Mapping[str, Any]) -> DatabaseExecutionOutput:
        ...


class ResultPolicy(Protocol):
    """
    Result sanitization and privacy boundary.
    """

    def apply(self, rows: Sequence[Mapping[str, Any]]) -> SanitizedResult:
        ...


class SQLWorkflow:
    """
    Backend-controlled SQL workflow.

    This class owns the execution order but delegates specialized
    operations to injected components.
    """

    agent_name: str = "sql_workflow"

    def __init__(
            self,
            *,
            query_spec_generator: QuerySpecGeneratorAgent,
            sql_generator: SQLGeneratorAgent,
            sql_repair_agent: SQLRepairAgent,
            reflection_agent: ReflectionAgent,
            answer_agent: AnswerAgent,
            memory_retriever: MemoryRetriever,
            sql_validator: SQLValidator,
            cost_guard: QueryCostGuard,
            database_executor: DatabaseExecutor,
            result_policy: ResultPolicy,
            reflection_coordinator: ReflectionCoordinator,
            logger: AgentLogger,
            metric_catalog: Sequence[Mapping[str, Any]],
            business_catalog: Sequence[Mapping[str, Any]],
            glossary: Sequence[Mapping[str, Any]] = (),
            available_capabilities: Sequence[str] = (),
            dialect: str = "postgresql",
    ) -> None:

        self.query_spec_generator = query_spec_generator
        self.sql_generator = sql_generator
        self.sql_repair_agent = sql_repair_agent
        self.reflection_agent = reflection_agent
        self.answer_agent = answer_agent
        self.memory_retriever = memory_retriever
        self.sql_validator = sql_validator
        self.cost_guard = cost_guard
        self.database_executor = database_executor
        self.result_policy = result_policy
        self.reflection_coordinator = reflection_coordinator
        self.logger = logger
        self.metric_catalog = tuple(metric_catalog)
        self.business_catalog = tuple(business_catalog)
        self.glossary = tuple(glossary)
        self.available_capabilities = tuple(available_capabilities)
        self.dialect = dialect

    def run(self, *, context: AgentContext) -> WorkflowResult | None:
        """
        Execute the complete SQL workflow.

        Args:
            context:
                Request-scoped AgentContext.

        Returns:
            WorkflowResult.
        """

        workflow_started_at: float = time.perf_counter()
        generated_sql: str | None = None
        parameters: dict[str, Any] = {}
        reflection_result: ReflectionResult | None = None
        repair_attempts: int = 0
        final_status: WorkflowStatus = WorkflowStatus.INCONCLUSIVE

        try:
            query_spec: QuerySpec = self._generate_query_spec(context=context)
            context.set("query_spec", query_spec)

            if query_spec.request_type == RequestType.CLARIFICATION:
                final_status = WorkflowStatus.CLARIFICATION_REQUIRED

                return WorkflowResult(
                    status=final_status,
                    answer=query_spec.clarification_question,
                    query_spec=query_spec,
                    sql=None,
                    parameters={},
                    reflection=None,
                    repair_attempts=0,
                    execution_ms=self._elapsed_ms(workflow_started_at),
                    trace_id=context.trace_id,
                )

            if query_spec.request_type == RequestType.UNSUPPORTED:
                final_status = WorkflowStatus.UNSUPPORTED

                return WorkflowResult(
                    status=final_status,
                    answer=query_spec.unsupported_reason,
                    query_spec=query_spec,
                    sql=None,
                    parameters={},
                    reflection=None,
                    repair_attempts=0,
                    execution_ms=self._elapsed_ms(workflow_started_at),
                    trace_id=context.trace_id,
                )

            memory_context: MemoryContext = self.memory_retriever.retrieve(context.user_query)
            context.set("memory_context", memory_context)
            prompt_context: dict[str, list[dict]] = self.memory_retriever.to_prompt_context(memory_context)
            context.set("prompt_context", prompt_context)

            sql_result: SQLGenerationResult = (
                self._generate_sql(
                    context=context,
                    query_spec=query_spec,
                    prompt_context=prompt_context,
                )
            )

            if sql_result.status == "clarification_required":
                final_status = WorkflowStatus.CLARIFICATION_REQUIRED
                return WorkflowResult(
                    status=final_status,
                    answer=sql_result.clarification_question,
                    query_spec=query_spec,
                    sql=None,
                    parameters={},
                    reflection=None,
                    repair_attempts=0,
                    execution_ms=self._elapsed_ms(workflow_started_at),
                    trace_id=context.trace_id,
                )
            generated_sql = sql_result.sql
            parameters = sql_result.parameters

            if generated_sql is None:
                raise SQLValidationError("SQL generation returned no SQL.")

            context.set("generated_sql", generated_sql)
            context.set("sql_parameters", parameters)

            while True:

                validation: SQLValidationOutput = self.sql_validator.validate(generated_sql, parameters=parameters)
                context.set("sql_validation", validation)

                if not validation.valid:

                    repair_issues: tuple[Mapping[str, Any], ...] = (
                        self._select_repairable_issues(validation.issues))

                    if not repair_issues:
                        final_status = WorkflowStatus.VALIDATION_FAILED

                        return WorkflowResult(
                            status=final_status,
                            answer="The query could not be safely executed.",
                            query_spec=query_spec,
                            sql=generated_sql,
                            parameters=parameters,
                            reflection=None,
                            repair_attempts=repair_attempts,
                            execution_ms=self._elapsed_ms(workflow_started_at),
                            trace_id=context.trace_id,
                        )

                    if repair_attempts >= self.reflection_coordinator.max_repair_attempts:
                        final_status = WorkflowStatus.VALIDATION_FAILED

                        return WorkflowResult(
                            status=final_status,
                            answer="The generated query could not be validated safely.",
                            query_spec=query_spec,
                            sql=generated_sql,
                            parameters=parameters,
                            reflection=None,
                            repair_attempts=repair_attempts,
                            execution_ms=self._elapsed_ms(workflow_started_at),
                            trace_id=context.trace_id,
                        )

                    repaired: SQLRepairResult = self.sql_repair_agent.run(
                        context=context,
                        question=context.user_query,
                        current_sql=generated_sql,
                        current_parameters=parameters,
                        issues=list(repair_issues),
                        schema_context=prompt_context["schema"],
                        relationship_context=list(RELATIONSHIPS),
                        business_context=prompt_context["business"],
                        metric_context=prompt_context["metrics"],
                        dialect=self.dialect,
                    )

                    repair_attempts += 1
                    if repaired.status != "repaired":
                        return WorkflowResult(
                            status=WorkflowStatus.VALIDATION_FAILED,
                            answer="The query could not be repaired safely.",
                            query_spec=query_spec,
                            sql=generated_sql,
                            parameters=parameters,
                            reflection=None,
                            repair_attempts=repair_attempts,
                            execution_ms=self._elapsed_ms(workflow_started_at),
                            trace_id=context.trace_id
                        )

                    generated_sql = repaired.sql
                    parameters = repaired.parameters

                    if generated_sql is None:
                        return WorkflowResult(
                            status=WorkflowStatus.VALIDATION_FAILED,
                            answer="The query repair did not produce a valid query.",
                            query_spec=query_spec,
                            sql=None,
                            parameters=parameters,
                            reflection=None,
                            repair_attempts=repair_attempts,
                            execution_ms=self._elapsed_ms(workflow_started_at),
                            trace_id=context.trace_id,
                        )

                    context.set("generated_sql", generated_sql)
                    context.set("sql_parameters", parameters)
                    continue

                cost_result: CostGuardOutput = (
                    self.cost_guard.validate(
                        generated_sql,
                        parameters=parameters,
                    )
                )

                context.set("cost_guard", cost_result)

                if not cost_result.allowed:
                    final_status = WorkflowStatus.VALIDATION_FAILED

                    return WorkflowResult(
                        status=final_status,
                        answer="The query is too expensive to execute safely.",
                        query_spec=query_spec,
                        sql=generated_sql,
                        parameters=parameters,
                        reflection=None,
                        repair_attempts=repair_attempts,
                        execution_ms=self._elapsed_ms(workflow_started_at),
                        trace_id=context.trace_id,
                    )

                execution: DatabaseExecutionOutput = (
                    self.database_executor.execute(
                        generated_sql,
                        parameters=parameters,
                    )
                )

                context.set("execution", execution)

                if not execution.success:
                    final_status = WorkflowStatus.EXECUTION_FAILED

                    return WorkflowResult(
                        status=final_status,
                        answer="The database query could not be completed.",
                        query_spec=query_spec,
                        sql=generated_sql,
                        parameters=parameters,
                        reflection=None,
                        repair_attempts=repair_attempts,
                        execution_ms=self._elapsed_ms(workflow_started_at),
                        trace_id=context.trace_id,
                    )

                sanitized: SanitizedResult = self.result_policy.apply(execution.rows)
                context.set("sanitized_result", sanitized)

                reflection_result: ReflectionResult = self._reflect(
                    context=context,
                    query_spec=query_spec,
                    sql=generated_sql,
                    sanitized=sanitized,
                    execution=execution,
                    prompt_context=prompt_context,
                )
                context.set("reflection", reflection_result)

                decision = self.reflection_coordinator.decide(
                    reflection=reflection_result,
                    repair_attempts=repair_attempts,
                )

                self.logger.log(
                    AgentEvent(
                        event_type=EventType.REFLECTION_COMPLETED,
                        trace_id=context.trace_id,
                        agent_name=self.agent_name,
                        stage_name="reflection_decision",
                        input_data={
                            "verdict": reflection_result.verdict,
                            "confidence": reflection_result.confidence,
                            "repair_attempts": repair_attempts,
                        },
                        output_data={"action": decision.action, "should_repair": decision.should_repair}
                    )
                )

                if decision.action == "accept":
                    answer: str = self.answer_agent.run(
                        context=context,
                        question=context.user_query,
                        result=sanitized.rows,
                        result_metadata={
                            **dict(sanitized.metadata),
                            "row_count": sanitized.row_count,
                            "truncated": sanitized.truncated,
                            "status": "success",
                        },
                    )

                    final_status = WorkflowStatus.SUCCESS

                    return WorkflowResult(
                        status=final_status,
                        answer=answer,
                        query_spec=query_spec,
                        sql=generated_sql,
                        parameters=parameters,
                        reflection=reflection_result,
                        repair_attempts=repair_attempts,
                        execution_ms=self._elapsed_ms(workflow_started_at),
                        trace_id=context.trace_id,
                    )

                if decision.action == "repair":

                    repair_issues = tuple(
                        {
                            "type": issue.type,
                            "severity": issue.severity,
                            "description": issue.description,
                            "evidence": issue.evidence,
                        }
                        for issue
                        in reflection_result.issues
                    )

                    repaired = self.sql_repair_agent.run(
                        context=context,
                        question=context.user_query,
                        current_sql=generated_sql,
                        current_parameters=parameters,
                        issues=list(repair_issues),
                        schema_context=prompt_context["schema"],
                        relationship_context=list(RELATIONSHIPS),
                        business_context=prompt_context["business"],
                        metric_context=prompt_context["metrics"],
                        dialect=self.dialect
                    )

                    repair_attempts += 1

                    if repaired.status != "repaired":
                        return WorkflowResult(
                            status=WorkflowStatus.REFLECTION_FAILED,
                            answer="The query could not be repaired reliably.",
                            query_spec=query_spec,
                            sql=generated_sql,
                            parameters=parameters,
                            reflection=reflection_result,
                            repair_attempts=repair_attempts,
                            execution_ms=self._elapsed_ms(workflow_started_at),
                            trace_id=context.trace_id,
                        )

                    generated_sql = repaired.sql
                    parameters = dict(repaired.parameters)

                    if generated_sql is None:
                        return WorkflowResult(
                            status=WorkflowStatus.REFLECTION_FAILED,
                            answer="The repair step did not produce a valid query.",
                            query_spec=query_spec,
                            sql=None,
                            parameters=parameters,
                            reflection=reflection_result,
                            repair_attempts=repair_attempts,
                            execution_ms=self._elapsed_ms(workflow_started_at),
                            trace_id=context.trace_id,
                        )

                    context.set("generated_sql", generated_sql)
                    context.set("sql_parameters", parameters)
                    continue

                if decision.action == "clarify":
                    return WorkflowResult(
                        status=WorkflowStatus.CLARIFICATION_REQUIRED,
                        answer=self._clarification_message(reflection_result),
                        query_spec=query_spec,
                        sql=generated_sql,
                        parameters=parameters,
                        reflection=reflection_result,
                        repair_attempts=repair_attempts,
                        execution_ms=self._elapsed_ms(workflow_started_at),
                        trace_id=context.trace_id,
                    )

                if decision.action == "reject":
                    return WorkflowResult(
                        status=WorkflowStatus.UNSUPPORTED,
                        answer=(
                            "This request cannot be processed "
                            "by the current analytical system."
                        ),
                        query_spec=query_spec,
                        sql=generated_sql,
                        parameters=parameters,
                        reflection=reflection_result,
                        repair_attempts=repair_attempts,
                        execution_ms=self._elapsed_ms(workflow_started_at),
                        trace_id=context.trace_id,
                    )

                return WorkflowResult(
                    status=WorkflowStatus.INCONCLUSIVE,
                    answer="The system could not verify the result reliably.",
                    query_spec=query_spec,
                    sql=generated_sql,
                    parameters=parameters,
                    reflection=reflection_result,
                    repair_attempts=repair_attempts,
                    execution_ms=self._elapsed_ms(workflow_started_at),
                    trace_id=context.trace_id,
                )

        except Exception as exc:

            self.logger.log(
                AgentEvent(
                    event_type=EventType.ERROR,
                    trace_id=context.trace_id,
                    agent_name=self.agent_name,
                    stage_name="workflow",
                    status="error",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    metadata={"repair_attempts": repair_attempts},
                )
            )

            raise

    def _generate_query_spec(self, *, context: AgentContext) -> QuerySpec:

        return self.query_spec_generator.run(
            context=context,
            question=context.user_query,
            metric_catalog=self.metric_catalog,
            business_catalog=self.business_catalog,
            glossary=self.glossary,
            available_capabilities=self.available_capabilities,
        )

    def _generate_sql(
            self,
            *,
            context: AgentContext,
            query_spec: QuerySpec,
            prompt_context: Mapping[str, list[dict]],
    ) -> SQLGenerationResult:

        return (
            self.sql_generator.run(
                context=context,
                question=context.user_query,
                query_spec=query_spec,
                schema_context=prompt_context["schema"],
                relationship_context=list(RELATIONSHIPS),
                business_context=prompt_context["business"],
                metric_context=prompt_context["metrics"],
                dialect=self.dialect,
            )
        )

    def _reflect(
            self,
            *,
            context: AgentContext,
            query_spec: QuerySpec,
            sql: str,
            sanitized: SanitizedResult,
            execution: DatabaseExecutionOutput,
            prompt_context: Mapping[str, list[dict]],
    ) -> ReflectionResult:

        result_metadata: dict[str, Any] = {
            "row_count": sanitized.row_count,
            "truncated": sanitized.truncated,
            "columns": sanitized.columns,
            "status": "success",
            "execution_ms": execution.execution_ms,
        }

        return (
            self.reflection_agent.run(
                context=context,
                question=context.user_query,
                query_spec=query_spec,
                sql=sql,
                execution_result=sanitized.rows,
                execution_metadata=result_metadata,
                schema_context=prompt_context["schema"],
                business_context=prompt_context["business"],
                metric_context=prompt_context["metrics"]
            )
        )

    @staticmethod
    def _select_repairable_issues(issues: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:

        repairable_types: frozenset[str] = frozenset(
            {
                "syntax",
                "schema",
                "semantic",
                "join",
                "aggregation",
                "date_logic",
                "business_rule",
                "metric",
            }
        )

        return tuple(issue for issue in issues if str(issue.get("type", "")).lower() in repairable_types)

    @staticmethod
    def _clarification_message(reflection: ReflectionResult) -> str:

        if reflection.repair_instructions:
            return reflection.repair_instructions[0]

        return "I need a little more information to answer this reliably."

    @staticmethod
    def _elapsed_ms(started_at: float, ) -> float:

        return (time.perf_counter() - started_at) * 1000
