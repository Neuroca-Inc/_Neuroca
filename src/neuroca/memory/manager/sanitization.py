"""Sanitization helpers for memory ingestion.

This module centralizes the logic for scrubbing memory payloads before they are
persisted. The sanitization process performs several responsibilities:

* Remove HTML/control characters and redact sensitive values such as emails,
  phone numbers, API keys, or access tokens.
* Detect prompt-injection phrases that attempt to override agent behaviour and
  reject the offending payloads.
* Normalise tags so they can be safely persisted as metadata keys without
  leaking PII or malicious instructions.

The sanitiser is intentionally light-weight and dependency free so it can be
used inside the memory manager without dragging infrastructure concerns into
the business logic layer.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable, Mapping

from neuroca.core.exceptions import MemoryValidationError

try:  # pragma: no cover - optional dependency wrapper
    from neuroca.core.utils.security import sanitize_input as _external_sanitize_input
except ModuleNotFoundError:  # pragma: no cover - fallback when optional deps missing
    def _sanitize_input(input_str: str, allow_html: bool = False) -> str:
        if not isinstance(input_str, str):
            raise TypeError("Input must be a string")

        sanitized = input_str if allow_html else re.sub(r"<[^>]*>", "", input_str)
        sanitized = re.sub(r"[\x00-\x1F\x7F]", "", sanitized)
        return sanitized
else:
    def _sanitize_input(input_str: str, allow_html: bool = False) -> str:
        return _external_sanitize_input(input_str, allow_html=allow_html)


class MemorySanitizer:
    """Scrub and validate memory payloads before persistence."""

    _SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("email", re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")),
        (
            "phone",
            re.compile(
                r"(?:(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?)\d{3}[\s-]?\d{4})"
            ),
        ),
        ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
        (
            "credit_card",
            re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
        ),
        (
            "api_secret",
            re.compile(r"(?i)(?:api|secret|token)[-_ ]?(?:key|token)?\s*[:=]\s*['\"]?[A-Z0-9]{8,}['\"]?"),
        ),
        ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
        ("openai", re.compile(r"sk-[a-z0-9]{16,}", re.IGNORECASE)),
    )

    _PROMPT_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(
            r"(?i)\b(ignore|disregard)\b[^\n]{0,80}\b(previous|earlier)\b[^\n]{0,80}\b(instruction|directive)s?\b"
        ),
        re.compile(r"(?i)\breset\b[^\n]{0,40}\bsystem prompt\b"),
        re.compile(r"(?i)\byou are now\b[^\n]{0,60}\b(system|root)\b"),
        re.compile(r"(?i)\bdo anything now\b"),
    )

    _TAG_INVALID_CHARS = re.compile(r"[^a-z0-9:_-]+")
    _TAG_DUPLICATE_UNDERSCORES = re.compile(r"_{2,}")

    def __init__(
        self,
        *,
        redaction_token: str = "[REDACTED]",
        max_tag_length: int = 64,
        log: logging.Logger | None = None,
    ) -> None:
        self._log = log or logging.getLogger(__name__)
        self._redaction_token = redaction_token
        self._max_tag_length = max(8, max_tag_length)

    # ------------------------------------------------------------------
    # Public sanitization helpers
    # ------------------------------------------------------------------

    def sanitize_text(self, field: str, value: str, *, allow_html: bool = False) -> str:
        """Return a scrubbed string value for ``field``."""

        return self._sanitize_string(field, value, allow_html=allow_html)

    def sanitize_optional_text(
        self,
        field: str,
        value: str | None,
        *,
        allow_html: bool = False,
    ) -> str | None:
        """Sanitize ``value`` when provided, otherwise propagate ``None``."""

        if value is None:
            return None
        return self._sanitize_string(field, value, allow_html=allow_html)

    def sanitize_value(self, field: str, value: Any) -> Any:
        """Best-effort sanitization for arbitrarily nested values."""

        return self._sanitize_value(field, value)

    def sanitize_content(self, value: Any) -> dict[str, Any]:
        """Sanitize memory content payloads for storage or updates.

        Args:
            value: Arbitrary memory content supplied by a caller.

        Returns:
            A mapping of sanitized content fields suitable for persistence.
        """

        if value is None:
            return {}

        if isinstance(value, str):
            return {"text": self._sanitize_string("content", value)}

        sanitized_value = self._sanitize_value("content", value)

        if isinstance(sanitized_value, Mapping):
            return dict(sanitized_value)

        if isinstance(sanitized_value, (list, tuple, set)):
            ordered = list(sanitized_value)
            return {"raw_content": ordered}

        return {"raw_content": sanitized_value}

    def sanitize_metadata(
        self, metadata: Mapping[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return sanitized metadata and a sanitized tag mapping."""

        sanitized: dict[str, Any] = {}
        tags: dict[str, Any] = {}

        for key, value in metadata.items():
            if key == "tags":
                tags = self.sanitize_tag_map(value)
                continue
            sanitized[key] = self._sanitize_value(f"metadata.{key}", value)

        return sanitized, tags

    def sanitize_tag_list(self, tags: Iterable[str]) -> dict[str, Any]:
        """Sanitize a list of tag strings into a canonical mapping."""

        sanitized: dict[str, Any] = {}
        for tag in tags:
            sanitized_tag = self._sanitize_tag(str(tag))
            sanitized[sanitized_tag] = True
        return sanitized

    def sanitize_tag_map(self, value: Any) -> dict[str, Any]:
        """Sanitize an arbitrary tag payload into a dict."""

        if value is None:
            return {}

        if isinstance(value, Mapping):
            sanitized: dict[str, Any] = {}
            for raw_key, raw_value in value.items():
                sanitized_key = self._sanitize_tag(str(raw_key))
                if isinstance(raw_value, bool):
                    sanitized[sanitized_key] = raw_value
                else:
                    sanitized[sanitized_key] = self._sanitize_value(
                        f"tags.{sanitized_key}", raw_value
                    )
            return sanitized

        if isinstance(value, (list, tuple, set)):
            return self.sanitize_tag_list(value)

        return {self._sanitize_tag(str(value)): True}

    def merge_tag_maps(self, *maps: Mapping[str, Any]) -> dict[str, Any]:
        """Combine multiple tag maps preserving sanitised values."""

        merged: dict[str, Any] = {}
        for mapping in maps:
            if not mapping:
                continue
            for key, raw_value in mapping.items():
                sanitized_key = self._sanitize_tag(str(key))
                if isinstance(raw_value, bool):
                    merged[sanitized_key] = raw_value
                else:
                    merged[sanitized_key] = self._sanitize_value(
                        f"tags.{sanitized_key}", raw_value
                    )
        return merged

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sanitize_string(
        self, field: str, value: str, *, allow_html: bool = False
    ) -> str:
        """Scrub ``value`` and enforce prompt-injection safeguards."""

        sanitized = _sanitize_input(value, allow_html=allow_html)
        sanitized = sanitized.strip()
        sanitized = self._redact_sensitive(field, sanitized)
        self._ensure_prompt_safe(field, sanitized)
        return sanitized

    def _sanitize_value(self, field: str, value: Any) -> Any:
        if isinstance(value, str):
            return self._sanitize_string(field, value)

        if isinstance(value, Mapping):
            return {
                str(key): self._sanitize_value(f"{field}.{key}", item)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [self._sanitize_value(f"{field}[{index}]", item) for index, item in enumerate(value)]

        if isinstance(value, tuple):
            return tuple(
                self._sanitize_value(f"{field}[{index}]", item)
                for index, item in enumerate(value)
            )

        if isinstance(value, set):
            return {
                self._sanitize_value(f"{field}[set]", item) for item in value
            }

        return value

    def _sanitize_tag(self, raw_tag: str) -> str:
        sanitized = self._sanitize_string("tag", raw_tag)
        sanitized = sanitized.lower()
        sanitized = sanitized.replace(" ", "_")
        sanitized = self._TAG_INVALID_CHARS.sub("_", sanitized)
        sanitized = self._TAG_DUPLICATE_UNDERSCORES.sub("_", sanitized)
        sanitized = sanitized.strip("_:")

        if not sanitized:
            raise MemoryValidationError(
                field="tags",
                value=self._redaction_token,
                message="Tag value became empty after sanitization",
            )

        if len(sanitized) > self._max_tag_length:
            sanitized = sanitized[: self._max_tag_length]

        return sanitized

    def _redact_sensitive(self, field: str, value: str) -> str:
        redacted = value
        for label, pattern in self._SENSITIVE_PATTERNS:
            if pattern.search(redacted):
                self._log.debug("Redacting %s pattern from %s", label, field)
                redacted = pattern.sub(self._redaction_token, redacted)
        return redacted

    def _ensure_prompt_safe(self, field: str, value: str) -> None:
        for pattern in self._PROMPT_INJECTION_PATTERNS:
            if pattern.search(value):
                self._log.warning(
                    "Rejected %s due to prompt-injection heuristic %s",
                    field,
                    pattern.pattern,
                )
                raise MemoryValidationError(
                    field=field,
                    value=self._redaction_token,
                    message=f"Rejected {field} containing prompt-injection instructions",
                )


__all__ = ["MemorySanitizer"]
