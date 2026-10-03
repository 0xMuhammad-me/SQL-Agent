import time
import uuid
from typing import Optional

class TraceContext:
    """
    Tracks the lifecycle of a single agent workflow execution.
    """

    def __init__(self,trace_id: Optional[str] = None):
        self.trace_id = (trace_id or str(uuid.uuid4()))
        self.start_time = time.perf_counter()

    def elapsed_ms(self) -> float:
        """
        Returns elapsed execution time in milliseconds.
        """
        return (time.perf_counter() - self.start_time) * 1000