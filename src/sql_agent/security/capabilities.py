from enum import Enum


class Capability(str, Enum):
    READ_SCHEMA = "read_schema"
    READ_DATABASE = "read_database"
    READ_AGGREGATED_DATA = "read_aggregated_data"
    READ_PII = "read_pii"