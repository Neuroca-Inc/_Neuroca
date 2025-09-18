"""Retrieval scoping helpers for the memory manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, FrozenSet, Iterable, Mapping


def _coerce_str(value: Any) -> str | None:
    """Return ``value`` as a string when possible."""

    if value is None:
        return None

    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None

    try:
        candidate = str(value)
    except Exception:  # pragma: no cover - defensive conversion
        return None

    candidate = candidate.strip()
    return candidate or None


def _as_string_set(value: Any) -> FrozenSet[str]:
    """Normalise ``value`` into a frozenset of non-empty strings."""

    if value is None:
        return frozenset()

    if isinstance(value, str):
        coerced = _coerce_str(value)
        return frozenset({coerced}) if coerced else frozenset()

    if isinstance(value, (set, frozenset, list, tuple)):
        items = {_coerce_str(item) for item in value}
        return frozenset({item for item in items if item})

    if isinstance(value, Mapping):
        items = {_coerce_str(key) for key, flag in value.items() if flag}
        return frozenset({item for item in items if item})

    coerced = _coerce_str(value)
    return frozenset({coerced}) if coerced else frozenset()


def _lower_set(values: Iterable[str]) -> FrozenSet[str]:
    """Return a case-insensitive frozenset."""

    return frozenset(value.lower() for value in values)


@dataclass(frozen=True)
class MemoryRetrievalScope:
    """Scope guard that enforces user/session level isolation."""

    principal_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    allowed_user_ids: FrozenSet[str] = field(default_factory=frozenset)
    allowed_session_ids: FrozenSet[str] = field(default_factory=frozenset)
    roles: FrozenSet[str] = field(default_factory=frozenset)
    allow_admin: bool = False

    ADMIN_ROLES: FrozenSet[str] = frozenset({"admin", "administrator"})

    @classmethod
    def system(cls) -> "MemoryRetrievalScope":
        """Return an unrestricted administrative scope."""

        return cls(principal_id="system", allow_admin=True)

    @classmethod
    def for_user(
        cls,
        user_id: str,
        *,
        session_id: str | None = None,
        roles: Iterable[str] | None = None,
        allow_admin: bool = False,
        shared_user_ids: Iterable[str] | None = None,
        shared_session_ids: Iterable[str] | None = None,
    ) -> "MemoryRetrievalScope":
        """Construct a scope bound to ``user_id``."""

        normalized_roles = frozenset(role for role in (roles or ()) if role)
        return cls(
            principal_id=user_id,
            user_id=user_id,
            session_id=session_id,
            roles=normalized_roles,
            allow_admin=allow_admin,
            allowed_user_ids=frozenset(
                {item for item in (shared_user_ids or []) if item}
            ),
            allowed_session_ids=frozenset(
                {item for item in (shared_session_ids or []) if item}
            ),
        )

    @property
    def is_admin(self) -> bool:
        """Return ``True`` when scope has administrative privileges."""

        if self.allow_admin:
            return True

        if not self.roles:
            return False

        return bool(_lower_set(self.roles) & self.ADMIN_ROLES)

    def allows_metadata(self, metadata: Mapping[str, Any]) -> bool:
        """Return ``True`` when ``metadata`` is visible within the scope."""

        if self.is_admin:
            return True

        owner_id = self._resolve_owner(metadata)
        permitted_users = self._resolve_permitted_users(metadata)
        candidate_sessions = self._resolve_sessions(metadata)

        allowed_users = {
            item
            for item in (
                self.principal_id,
                self.user_id,
                *self.allowed_user_ids,
            )
            if item
        }

        if owner_id:
            if not allowed_users:
                return False

            is_owner_allowed = owner_id in allowed_users
            is_permitted_user_allowed = bool(permitted_users & allowed_users)
            if not is_owner_allowed and not is_permitted_user_allowed:
                return False

        allowed_sessions = {
            item
            for item in (
                self.session_id,
                *self.allowed_session_ids,
            )
            if item
        }

        if candidate_sessions and allowed_sessions:
            if candidate_sessions.isdisjoint(allowed_sessions):
                return False

        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_owner(self, metadata: Mapping[str, Any]) -> str | None:
        """Extract the owner identifier from ``metadata``."""

        candidates = [
            metadata.get("user_id"),
            metadata.get("owner_id"),
        ]

        tags = metadata.get("tags")
        if isinstance(tags, Mapping):
            candidates.extend(
                tags.get(candidate) for candidate in ("user_id", "owner_id")
            )

        additional = metadata.get("additional_metadata")
        if isinstance(additional, Mapping):
            candidates.extend(
                additional.get(candidate)
                for candidate in ("user_id", "owner_id")
            )

        for candidate in candidates:
            owner = _coerce_str(candidate)
            if owner:
                return owner
        return None

    def _resolve_permitted_users(self, metadata: Mapping[str, Any]) -> FrozenSet[str]:
        """Extract shared-user identifiers from ``metadata``."""

        fields = ("shared_with", "permitted_users", "allowed_users")

        collected: FrozenSet[str] = frozenset()
        for field in fields:
            candidate = metadata.get(field)
            collected |= _as_string_set(candidate)

        tags = metadata.get("tags")
        if isinstance(tags, Mapping):
            for field in fields:
                collected |= _as_string_set(tags.get(field))

        additional = metadata.get("additional_metadata")
        if isinstance(additional, Mapping):
            for field in fields:
                collected |= _as_string_set(additional.get(field))

        return collected

    def _resolve_sessions(self, metadata: Mapping[str, Any]) -> FrozenSet[str]:
        """Extract session identifiers from ``metadata``."""

        candidates = _as_string_set(metadata.get("session_id"))

        tags = metadata.get("tags")
        if isinstance(tags, Mapping):
            candidates |= _as_string_set(tags.get("session_id"))

        additional = metadata.get("additional_metadata")
        if isinstance(additional, Mapping):
            candidates |= _as_string_set(additional.get("session_id"))

        return candidates

