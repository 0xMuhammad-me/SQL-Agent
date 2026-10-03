import os
from dataclasses import dataclass

@dataclass(frozen=True)
class LLMConfig:

    model:str
    api_key:str
    temperature:float
    max_retry:int


LLM_CONFIG = LLMConfig(
    model=os.getenv("LLM_MODEL","openai:gpt-5.6-luna"),
    api_key=os.getenv("AVALAI_API_KEY", ""),
    temperature=0,
    max_retry=3,
)