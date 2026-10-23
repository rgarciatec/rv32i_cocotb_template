import html
import json
import os
from pathlib import Path

from rv32i_test_config import ALL_INSTRUCTIONS, INSTRUCTION_GROUPS, selected_instructions

GROUP_LABELS = {
    "alu": "ALU (register and immediate)",
    "branch": "Branches",
    "jump": "Jumps",
    "upper": "Upper immediate",
    "memory": "Memory",
    "invalid": "Illegal decode",
}

STYLE = """
<style>
.cov { margin: 12px 0 18px; font-family: Arial, Helvetica, sans-serif; }
.cov h3 { margin: 0 0 6px; }
.cov .bar { background: #e5e7eb; border-radius: 6px; height: 22px; width: 100%; max-width: 560px; overflow: hidden; }
.cov .bar > div { background: #16a34a; height: 100%; color: #fff; font-size: 13px; line-height: 22px; padding-left: 8px; box-sizing: border-box; white-space: nowrap; }
.cov table { border-collapse: collapse; margin-top: 10px; font-size: 13px; }
.cov th, .cov td { border: 1px solid #cbd5e1; padding: 4px 10px; text-align: left; vertical-align: top; }
.cov th { background: #f1f5f9; }
.cov .ok { color: #15803d; font-weight: 700; }
.cov .miss { color: #b91c1c; font-weight: 700; }
.cov .off { color: #94a3b8; }
</style>
"""


def _load_coverage() -> dict:
    coverage_file = Path(os.environ.get("COCOTB_COVERAGE_FILE", "coverage.json"))
    if coverage_file.exists():
        return json.loads(coverage_file.read_text())
    return {}


def _cell(name: str, covered: set, selected: set, hits: dict) -> str:
    if name in covered:
        return f'<span class="ok">&#10004; {html.escape(name)}</span> ({hits.get(name, 0)})'
    if name in selected:
        return f'<span class="miss">&#10008; {html.escape(name)}</span>'
    return f'<span class="off">&#8212; {html.escape(name)} (not selected)</span>'


def pytest_html_results_summary(prefix, summary, postfix) -> None:
    coverage = _load_coverage()
    covered = set(coverage.get("covered_instructions", ()))
    hits = coverage.get("instruction_hits", {})
    selected_names = selected_instructions()
    selected = set(selected_names)

    total = len(ALL_INSTRUCTIONS)
    overall = 100 * len(covered) / total
    selected_covered = covered & selected
    selected_percent = 100 * len(selected_covered) / len(selected)
    missing = [name for name in ALL_INSTRUCTIONS if name not in covered]

    rows = []
    for group, names in INSTRUCTION_GROUPS.items():
        cells = ", ".join(_cell(name, covered, selected, hits) for name in names)
        group_covered = sum(1 for name in names if name in covered)
        rows.append(
            f"<tr><td>{html.escape(GROUP_LABELS.get(group, group))}</td>"
            f"<td>{group_covered}/{len(names)}</td><td>{cells}</td></tr>"
        )

    not_covered = html.escape(", ".join(missing)) if missing else "none"
    prefix.append(
        STYLE
        + '<div class="cov"><h3>Instruction coverage</h3>'
        f'<div class="bar"><div style="width:{max(overall, 12):.1f}%">'
        f"{len(covered)}/{total} bins ({overall:.1f}%)</div></div>"
        f"<p>Selected this run: {len(selected_covered)}/{len(selected)} "
        f"({selected_percent:.1f}%). Not covered: {not_covered}.</p>"
        "<table><tr><th>Group</th><th>Covered</th>"
        "<th>Instruction bins (hit count)</th></tr>" + "".join(rows) + "</table></div>"
    )
