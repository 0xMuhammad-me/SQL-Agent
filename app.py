from __future__ import annotations

from agents import (
    AnswerAgent,
    QuerySpecGeneratorAgent,
    ReflectionAgent,
    SQLGeneratorAgent,
    SQLRepairAgent,
    SQLReviewAgent,
)
from config import AGENT_CONFIG, DB_CONFIG, LLM_CONFIG, OBSERVABILITY_CONFIG, SECURITY_CONFIG
from core import ProviderClient
from memory import BusinessMemory, InMemoryCache, MemoryRetriever, MetricMemory, SchemaMemory
from metadata import SchemaIndex
from observability import AgentLogger, AgentMetrics
from orchestration import ReflectionCoordinator, SQLAgent, SQLWorkflow
from security import PIIGuard, PermissionManager, SecurityPolicy, SQLFirewall
from sql import DatabaseExecutor, QueryCostGuard, ResultPolicy, SQLValidator
from tools.metadata_tools import MetadataTools


def build_sql_agent() -> SQLAgent:
    """Build the production application graph in one composition root."""
    logger: AgentLogger = AgentLogger(
        service_name=OBSERVABILITY_CONFIG.service_name,
        level=OBSERVABILITY_CONFIG.log_level,
        log_file_path=OBSERVABILITY_CONFIG.log_file_path,
        enable_console=OBSERVABILITY_CONFIG.enable_console,
        enable_file=OBSERVABILITY_CONFIG.enable_file,
        json_logging=OBSERVABILITY_CONFIG.json_logging,
    )
    llm_client: ProviderClient = ProviderClient(
        default_model=LLM_CONFIG.model,
        timeout_seconds=LLM_CONFIG.timeout_seconds,
    )

    schema_memory: SchemaMemory = SchemaMemory()
    business_memory: BusinessMemory = BusinessMemory()
    metric_memory: MetricMemory = MetricMemory()
    semantic_memory: MemoryRetriever = MemoryRetriever(schema_memory, business_memory, metric_memory)
    cache: InMemoryCache = InMemoryCache()
    metadata_tools: MetadataTools = MetadataTools(semantic_memory, cache,         logger=logger)

    schema_index: SchemaIndex = SchemaIndex()
    sql_validator: SQLValidator = SQLValidator(schema_index)

    security_policy: SecurityPolicy = SecurityPolicy(
        role_name=SECURITY_CONFIG.role_name,
        allow_pii_access=SECURITY_CONFIG.allow_pii_access,
        max_query_rows=SECURITY_CONFIG.max_query_rows,
        max_result_bytes=SECURITY_CONFIG.max_result_bytes,
        max_sql_length=SECURITY_CONFIG.max_sql_length,
        allowed_tables=SECURITY_CONFIG.allowed_tables,
    )
    pii_guard: PIIGuard = PIIGuard()
    permission_manager: PermissionManager = PermissionManager()
    sql_firewall: SQLFirewall = SQLFirewall(security_policy)

    database_executor: DatabaseExecutor = DatabaseExecutor(
        DB_CONFIG.connection_string,
        statement_timeout_ms=DB_CONFIG.statement_timeout_ms,
        max_rows=SECURITY_CONFIG.max_query_rows,
    )
    cost_guard: QueryCostGuard = QueryCostGuard(
        database_executor,
        max_cost=SECURITY_CONFIG.max_query_cost,
        max_estimated_rows=SECURITY_CONFIG.max_estimated_rows,
    )
    result_policy: ResultPolicy = ResultPolicy(
        max_rows=SECURITY_CONFIG.max_query_rows,
        max_bytes=SECURITY_CONFIG.max_result_bytes,
        pii_guard=pii_guard,
    )

    query_spec_generator: QuerySpecGeneratorAgent = QuerySpecGeneratorAgent(
        llm_client=llm_client,
        logger=logger,
        metadata_tools=metadata_tools,
    )
    sql_generator: SQLGeneratorAgent = SQLGeneratorAgent(llm_client=llm_client, logger=logger)
    sql_review_agent: SQLReviewAgent = SQLReviewAgent(llm_client=llm_client,logger=logger)
    sql_repair_agent: SQLRepairAgent = SQLRepairAgent(llm_client=llm_client, logger=logger)
    reflection_agent: ReflectionAgent = ReflectionAgent(llm_client=llm_client, logger=logger)
    answer_agent: AnswerAgent = AnswerAgent(llm_client=llm_client, logger=logger)

    metrics: AgentMetrics = AgentMetrics()

    reflection_coordinator: ReflectionCoordinator = ReflectionCoordinator(
        max_repair_attempts=AGENT_CONFIG.max_repair_attempts,
        minimum_repair_confidence=AGENT_CONFIG.minimum_repair_confidence,
    )

    workflow: SQLWorkflow = SQLWorkflow(
        query_spec_generator=query_spec_generator,
        sql_generator=sql_generator,
        sql_review_agent=sql_review_agent,
        sql_repair_agent=sql_repair_agent,
        sql_validator=sql_validator,
        sql_firewall=sql_firewall,
        permission_manager=permission_manager,
        security_policy=security_policy,
        pii_guard=pii_guard,
        cost_guard=cost_guard,
        database_executor=database_executor,
        result_policy=result_policy,
        reflection_agent=reflection_agent,
        reflection_coordinator=reflection_coordinator,
        answer_agent=answer_agent,
        logger=logger,
        metrics=metrics,
        available_capabilities=("read_only_sql", "semantic_metadata_memory", "sql_review", "reflection", "repair"),
    )
    return SQLAgent(workflow=workflow)


__all__: list[str] = ["build_sql_agent"]
