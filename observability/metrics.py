from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AgentMetrics:
    """In-process aggregate metrics suitable for a single application instance."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    sql_generated_count: int = 0
    sql_execution_count: int = 0
    sql_execution_failures: int = 0
    reflection_failures: int = 0

    def record_request(self) -> None:
        self.total_requests += 1

    def record_result(self, *, success: bool, latency_ms: float) -> None:
        self.total_latency_ms += latency_ms
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

    def success_rate(self) -> float:
        return self.successful_requests / self.total_requests if self.total_requests else 0.0

    def average_latency_ms(self) -> float:
        return self.total_latency_ms / self.total_requests if self.total_requests else 0.0
