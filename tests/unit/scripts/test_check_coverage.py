"""Tests for the coverage checking script helpers."""

from pathlib import Path

import pytest

from tests.scripts import check_coverage


def test_build_pytest_args_uses_expected_paths():
    """The constructed pytest arguments should match the expected targets and reports."""

    args = check_coverage.build_pytest_args()

    expected_targets = [
        str(path.resolve()) for path in check_coverage.DEFAULT_TEST_TARGETS
    ]
    assert args[: len(expected_targets)] == expected_targets

    assert f"--cov={check_coverage.COVERAGE_MODULE}" in args

    html_arg = next(arg for arg in args if arg.startswith("--cov-report=html:"))
    expected_html = (
        f"--cov-report=html:{(check_coverage.DEFAULT_REPORT_DIR.resolve() / 'html').as_posix()}"
    )
    assert html_arg == expected_html

    json_arg = next(arg for arg in args if arg.startswith("--cov-report=json:"))
    expected_json = (
        f"--cov-report=json:{(check_coverage.DEFAULT_REPORT_DIR.resolve() / 'coverage.json').as_posix()}"
    )
    assert json_arg == expected_json


def test_build_pytest_args_rejects_outside_report_directory(tmp_path: Path):
    """Report directories outside the repository must be rejected."""

    outside_report_dir = tmp_path / "coverage"

    with pytest.raises(ValueError):
        check_coverage.build_pytest_args(outside_report_dir)


def test_build_pytest_args_requires_existing_test_target(tmp_path: Path):
    """Test targets must exist inside the repository tree."""

    bogus_target = tmp_path / "not_real"

    with pytest.raises(ValueError):
        check_coverage.build_pytest_args(test_targets=(bogus_target,))

    missing_repo_target = check_coverage.REPO_ROOT / "tests" / "unit" / "does_not_exist"

    with pytest.raises(FileNotFoundError):
        check_coverage.build_pytest_args(test_targets=(missing_repo_target,))
