import json
import os
from pathlib import Path

from rv32i_test_config import (
    ALL_INSTRUCTIONS,
    selected_instructions,
    selected_tests,
)


COVERAGE_FILE = Path(os.environ.get("COCOTB_COVERAGE_FILE", "coverage.json"))
SELECTED_INSTRUCTIONS = selected_instructions()
_COVERED_INSTRUCTIONS: set[str] = set()
_INSTRUCTION_HITS = {name: 0 for name in ALL_INSTRUCTIONS}


def _write_coverage() -> None:
    COVERAGE_FILE.write_text(json.dumps({
        "all_instructions": ALL_INSTRUCTIONS,
        "selected_instructions": SELECTED_INSTRUCTIONS,
        "selected_tests": selected_tests(),
        "covered_instructions": [
            name for name in ALL_INSTRUCTIONS if name in _COVERED_INSTRUCTIONS
        ],
        "instruction_hits": _INSTRUCTION_HITS,
    }, indent=2) + "\n")


def sample_instruction(instruction: str) -> None:
    if instruction not in _INSTRUCTION_HITS:
        raise ValueError(f"Unknown instruction coverage bin: {instruction}")

    _COVERED_INSTRUCTIONS.add(instruction)
    _INSTRUCTION_HITS[instruction] += 1
    _write_coverage()
