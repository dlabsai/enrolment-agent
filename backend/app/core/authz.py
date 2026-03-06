from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, status

from app.models import User, UserRole


@dataclass(frozen=True, init=False)
class AllowedRoles:
    roles: tuple[UserRole, ...]

    def __init__(self, *roles: UserRole) -> None:
        object.__setattr__(self, "roles", roles)

    def __iter__(self) -> Iterator[UserRole]:
        return iter(self.roles)

    def __len__(self) -> int:
        return len(self.roles)

    def __contains__(self, role: UserRole) -> bool:
        return role in self.roles


def forbidden(detail: str = "Access denied") -> None:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def require_roles(current_user: User, *roles: UserRole, detail: str = "Access denied") -> User:
    if current_user.role not in roles:
        forbidden(detail)
    return current_user


def ensure_owner_or_roles(
    owner_id: UUID | None, current_user: User, *roles: UserRole, detail: str = "Access denied"
) -> None:
    if owner_id is not None and owner_id == current_user.id:
        return
    if current_user.role not in roles:
        forbidden(detail)
