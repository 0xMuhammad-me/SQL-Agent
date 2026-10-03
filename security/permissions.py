from dataclasses import dataclass
from typing import Final

from security.capabilities import Capability


@dataclass(frozen=True)
class RolePermissions:
    """Permissions assigned to an application role."""

    role_name: str
    capabilities: frozenset[Capability]


ROLE_PERMISSIONS: Final[dict[str, RolePermissions]] = {
    "analyst": RolePermissions(
        role_name="analyst",
        capabilities=frozenset(
            {
                Capability.READ_SCHEMA,
                Capability.READ_DATABASE,
                Capability.READ_AGGREGATED_DATA,
            }
        ),
    ),
    "admin": RolePermissions(
        role_name="admin",
        capabilities=frozenset(
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
    """Checks whether a role is allowed to use required capabilities."""

    def __init__(self, role_permissions: dict[str, RolePermissions] | None = None) -> None:
        self._role_permissions = (role_permissions or ROLE_PERMISSIONS)

    def get_role_permissions(self,role_name: str) -> RolePermissions:
        """Return permissions for a role."""

        permissions = self._role_permissions.get(role_name)

        if permissions is None:
            raise PermissionError(f"Unknown role: {role_name}")

        return permissions

    def check_capabilities(self,role_name: str,required_capabilities: frozenset[Capability]) -> bool:
        """Raise PermissionError if a role lacks required capabilities."""

        permissions = self.get_role_permissions(role_name)

        missing = (required_capabilities- permissions.capabilities)

        if missing:
            raise PermissionError(
                "Missing capabilities: "
                + ", ".join(capability.value for capability in sorted(missing,key=lambda item: item.value))
            )

        return True