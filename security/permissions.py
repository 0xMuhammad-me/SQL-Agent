from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from errors import PermissionDeniedError

from .capabilities import Capability
from .policy import SecurityPolicy


@dataclass(frozen=True, slots=True)
class RolePermissions:
    role_name: str
    capabilities: frozenset[Capability]


ROLE_PERMISSIONS: dict[str, RolePermissions] = {
    "analyst": RolePermissions(
        "analyst",
        frozenset(
            {
                Capability.READ_SCHEMA,
                Capability.READ_DATABASE,
                Capability.READ_AGGREGATED_DATA,
            }
        ),
    ),
    "admin": RolePermissions(
        "admin",
        frozenset(
            {
                Capability.READ_SCHEMA,
                Capability.READ_DATABASE,
                Capability.READ_AGGREGATED_DATA,
                Capability.READ_PII,
            }
        ),
    ),
}


class PermissionManager:
    """Check deterministic role capabilities before database execution."""

    def __init__(self, roles: dict[str, RolePermissions] | None = None) -> None:
        self._roles: dict[str, RolePermissions] = dict(roles or ROLE_PERMISSIONS)

    def check_query(
        self,
        *,
        role_name: str,
        tables: Sequence[str],
        pii_columns: Sequence[str],
        is_aggregated: bool,
        policy: SecurityPolicy,
    ) -> None:
        role: RolePermissions | None = self._roles.get(role_name)
        if role is None:
            raise PermissionDeniedError(
                "Unknown role.",
                details={"role_name": role_name},
            )

        required: set[Capability] = {Capability.READ_DATABASE}
        if is_aggregated:
            required.add(Capability.READ_AGGREGATED_DATA)
        if pii_columns:
            required.add(Capability.READ_PII)

        missing: set[Capability] = required - role.capabilities
        if missing:
            raise PermissionDeniedError(
                "Missing required capabilities.",
                details={"capabilities": sorted(capability.value for capability in missing)},
            )

        if pii_columns and not policy.allow_pii_access:
            raise PermissionDeniedError(
                "PII access is disabled by security policy.",
                details={"columns": list(pii_columns)},
            )

        for table in tables:
            if not policy.is_table_allowed(table):
                raise PermissionDeniedError(
                    "Table is not allowed by security policy.",
                    details={"table": table},
                )
