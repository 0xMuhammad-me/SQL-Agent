from enum import Enum
from typing import Final


class Capability(str, Enum):
    """Capabilities that can be granted to tools or agents."""

    READ_SCHEMA = "read_schema"
    READ_DATABASE = "read_database"
    READ_AGGREGATED_DATA = "read_aggregated_data"
    READ_PII = "read_pii"

    WRITE_DATABASE = "write_database"
    NETWORK_ACCESS = "network_access"
    FILESYSTEM_ACCESS = "filesystem_access"
    SUBPROCESS_ACCESS = "subprocess_access"


SAFE_ANALYTICS_CAPABILITIES: Final[frozenset[Capability]] = frozenset(
    {
        Capability.READ_SCHEMA,
        Capability.READ_DATABASE,
        Capability.READ_AGGREGATED_DATA,
    }
)


SENSITIVE_CAPABILITIES: Final[frozenset[Capability]] = frozenset(
    {
        Capability.READ_PII,
    }
)


FORBIDDEN_DEFAULT_CAPABILITIES: Final[frozenset[Capability]] = frozenset(
    {
        Capability.WRITE_DATABASE,
        Capability.NETWORK_ACCESS,
        Capability.FILESYSTEM_ACCESS,
        Capability.SUBPROCESS_ACCESS,
    }
)