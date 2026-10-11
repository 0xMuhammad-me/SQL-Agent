from __future__ import annotations
import time,uuid
class TraceContext:
    def __init__(self,trace_id:str|None=None)->None:self.trace_id=trace_id or str(uuid.uuid4()); self._started_at=time.perf_counter()
    def elapsed_ms(self)->float:return (time.perf_counter()-self._started_at)*1000.0
