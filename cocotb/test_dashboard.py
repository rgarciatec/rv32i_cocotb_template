"""Expose individual Cocotb results as pytest cases for the HTML dashboard."""

import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from rv32i_test_config import ALL_INSTRUCTIONS, selected_tests

RESULTS_FILE = Path(os.environ.get("COCOTB_RESULTS_FILE", "results.xml"))
COVERAGE_FILE = Path(os.environ.get("COCOTB_COVERAGE_FILE", "coverage.json"))
EXPECTED_TESTS = selected_tests()


def load_results() -> dict[str, tuple[bool, str]]:
    if not RESULTS_FILE.exists():
        return {name: (False, f"Missing simulator results: {RESULTS_FILE}") for name in EXPECTED_TESTS}

    root = ET.parse(RESULTS_FILE).getroot()
    cases: dict[str, tuple[bool, str]] = {}
    for testcase in root.iter("testcase"):
        name = testcase.attrib.get("name", "")
        result_element = next(
            (child for child in testcase if child.tag in ("failure", "error", "skipped")),
            None,
        )
        if result_element is None:
            cases[name] = (True, "")
        else:
            details = result_element.attrib.get("message", "") or (result_element.text or "").strip()
            cases[name] = (False, details or result_element.tag)
    return cases


RESULTS = load_results()


@pytest.mark.parametrize("name", EXPECTED_TESTS, ids=EXPECTED_TESTS)
def test_cocotb_case(name: str) -> None:
    passed, details = RESULTS.get(name, (False, "Cocotb result was not reported"))
    assert passed, f"{name.upper()} failed: {details}"


def load_coverage() -> dict:
    if not COVERAGE_FILE.exists():
        return {}
    return json.loads(COVERAGE_FILE.read_text())


def test_functional_instruction_coverage() -> None:
    coverage = load_coverage()
    assert coverage, f"Missing Cocotb functional coverage data: {COVERAGE_FILE}"
    assert coverage.get("all_instructions") == list(ALL_INSTRUCTIONS)
    assert coverage.get("covered_instructions") is not None
