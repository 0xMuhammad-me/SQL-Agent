from dataclasses import dataclass


@dataclass
class AgentMetrics:
    """
    Stores aggregated system performance metrics.
    """
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    sql_generated_count: int = 0
    sql_execution_count: int = 0
    sql_execution_failures: int = 0
    reflection_failures: int = 0

    def success_rate(self) -> float:
        """
        Calculates overall request success rate.
        """
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests