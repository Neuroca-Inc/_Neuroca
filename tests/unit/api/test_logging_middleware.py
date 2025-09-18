"""Unit tests for the API logging middleware helpers."""

from importlib import util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[3] / "src" / "neuroca" / "api" / "middleware" / "logging.py"
_SPEC = util.spec_from_file_location("_logging_middleware", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None, "logging middleware module should be loadable"
_MODULE = util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

_format_placeholder = _MODULE._format_placeholder


def test_format_placeholder_escapes_html_sequences() -> None:
    """User-controlled values should be HTML-escaped before logging."""

    placeholder = _format_placeholder("binary data", "<script>alert('xss')</script>")

    assert placeholder == "<binary data: &lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;>"


def test_format_placeholder_defaults_to_unknown() -> None:
    """Missing values fall back to a safe placeholder."""

    placeholder = _format_placeholder("binary data", None)

    assert placeholder == "<binary data: unknown>"
