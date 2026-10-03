from __future__ import annotations

from dataclasses import asdict, dataclass

from .business_memory import (
    BusinessMemory,
    BusinessSearchResult,
)

from .metric_memory import (
    MetricMemory,
    MetricSearchResult,
)

from .schema_memory import (
    SchemaMemory,
    SchemaSearchResult,
)


@dataclass(frozen=True)
class MemoryContext:
    """
    Relevant semantic context retrieved for one user request.
    """
    schema: list[SchemaSearchResult]
    business: list[BusinessSearchResult]
    metrics: list[MetricSearchResult]


class MemoryRetriever:
    """
    Coordinates retrieval across schema, business, and metric memory.
    """

    def __init__(self, schema_memory: SchemaMemory, business_memory: BusinessMemory, metric_memory: MetricMemory) -> None:

        self.schema_memory: SchemaMemory = schema_memory
        self.business_memory: BusinessMemory = business_memory
        self.metric_memory: MetricMemory = metric_memory


    def retrieve(self, question: str, *, schema_top_k: int = 8, business_top_k: int = 6, metric_top_k: int = 6) -> MemoryContext:
        """
        Retrieve relevant semantic information for a question.

        Returns:
            MemoryContext containing ranked candidates.
        """

        schema_results: list[SchemaSearchResult] = self.schema_memory.search(question, top_k=schema_top_k)
        business_results: list[BusinessSearchResult] = self.business_memory.search(question, top_k=business_top_k)
        metric_results: list[MetricSearchResult] = self.metric_memory.search(question, top_k=metric_top_k)

        return MemoryContext(
            schema=schema_results,
            business=business_results,
            metrics=metric_results,
        )


    @staticmethod
    def to_prompt_context(memory_context: MemoryContext) -> dict[str, list[dict]]:
        """
        Convert memory results into a prompt-safe serializable structure.

        Returns:
            Dictionary containing only metadata required by LLM prompts.
        """
        return {
            "schema": [asdict(result.table) for result in memory_context.schema],
            "business": [{"name": result.name, "definition": result.definition} for result in memory_context.business],
            "metrics": [{"name": result.name, "definition": result.definition} for result in memory_context.metrics],
        }