from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    max_iterations:int=3
    enable_reflection:bool=True
    enable_planning:bool=True
    enable_tool_validation:bool=True


AGENT_CONFIG = AgentConfig()