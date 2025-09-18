"""Operation policy resolution for storage backend factory."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from neuroca.memory.backends.factory.backend_type import BackendType
from neuroca.memory.backends.policies import BackendOperationPolicy, RetryPolicy


_DEFAULT_POLICIES: Dict[BackendType, BackendOperationPolicy] = {
    BackendType.REDIS: BackendOperationPolicy(
        timeout_seconds=2.5,
        retry=RetryPolicy(attempts=5, initial_delay_seconds=0.05, backoff_multiplier=2.0, max_delay_seconds=0.5),
    ),
    BackendType.SQL: BackendOperationPolicy(
        timeout_seconds=10.0,
        retry=RetryPolicy(attempts=4, initial_delay_seconds=0.1, backoff_multiplier=2.0, max_delay_seconds=1.0),
    ),
    BackendType.VECTOR: BackendOperationPolicy(
        timeout_seconds=6.0,
        retry=RetryPolicy(attempts=3, initial_delay_seconds=0.1, backoff_multiplier=1.5, max_delay_seconds=0.6),
    ),
}

_POLICY_KEYS = {
    "operation_policy",
    "operation_policies",
    "operation_timeout_seconds",
    "retry_attempts",
    "retry_backoff_seconds",
    "retry_initial_delay_seconds",
    "retry_backoff_multiplier",
    "retry_max_backoff_seconds",
}


def _extract_mapping(config: Mapping[str, Any], backend_type: BackendType) -> Optional[Mapping[str, Any] | BackendOperationPolicy]:
    direct = config.get("operation_policy")
    if isinstance(direct, (Mapping, BackendOperationPolicy)):
        return direct

    grouped = config.get("operation_policies")
    if isinstance(grouped, Mapping):
        backend_key = backend_type.value
        candidate = grouped.get(backend_key) or grouped.get("default")
        if isinstance(candidate, (Mapping, BackendOperationPolicy)):
            return candidate

    flattened: Dict[str, Any] = {}
    for key in ("operation_timeout_seconds", "retry_attempts", "retry_backoff_seconds", "retry_max_backoff_seconds", "retry_backoff_multiplier", "retry_initial_delay_seconds"):
        if key in config:
            flattened[key] = config[key]

    return flattened or None


def resolve_operation_policy(
    backend_type: BackendType,
    config: Optional[Mapping[str, Any]],
) -> BackendOperationPolicy:
    """Resolve the effective operation policy for *backend_type*."""

    base_policy = _DEFAULT_POLICIES.get(backend_type, BackendOperationPolicy.default())

    if not isinstance(config, Mapping):
        return base_policy

    mapping = _extract_mapping(config, backend_type)
    if mapping is None:
        return base_policy

    return BackendOperationPolicy.from_mapping(mapping, fallback=base_policy)


def sanitize_policy_keys(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Remove policy-only keys from *config* before passing to backend constructors."""

    if not isinstance(config, dict):
        return {}

    return {key: value for key, value in config.items() if key not in _POLICY_KEYS}
