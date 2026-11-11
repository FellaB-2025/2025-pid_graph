"""v1.3 Phase 11 (PIDKG_UPGRADE.md): close-out. The documents say what the code does.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pid_graph import ontology as O  # noqa: E402
from pid_graph.reconcile import TITLES  # noqa: E402


def _text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("doc", ["PID_GRAPH_ONTOLOGY_V1_3.md", "CLAUDE.md"])
def test_closed_lists_in_the_documents_are_the_ones_in_the_code(doc):
    text = _text(doc)
    for label in O.LABELS:
        assert f"`{label}`" in text, f"{doc} does not list label {label}"
    for rel in O.RELS:
        assert f"`{rel}`" in text, f"{doc} does not list relationship {rel}"
    assert f"({len(O.LABELS)})" in text and f"({len(O.RELS)}" in text
    assert len(O.LABELS) == 11 and len(O.RELS) == 19


def test_no_label_or_relationship_in_the_documents_is_missing_from_the_code():
    text = _text("PID_GRAPH_ONTOLOGY_V1_3.md")
    table = text.split("## 3. Relationship types")[1].split("## 4.")[0]
    in_doc = set(re.findall(r"^\| `([A-Z_]+)` \|", table, flags=re.M))
    assert in_doc == set(O.RELS)
    labels = text.split("## 2. Node labels")[1].split("## 3.")[0]
    assert set(re.findall(r"^\| `(\w+)` \|", labels, flags=re.M)) == set(O.LABELS)


def test_mcp_schema_reference_names_every_relationship():
    src = _text("pid_graph/mcp_server.py")
    block = src.split("def schema_reference")[1].split("return {")[0]
    assert set(re.findall(r'"([A-Z_]+)": "', block)) == set(O.RELS)


def test_exception_codes_are_one_unbroken_series():
    assert sorted(TITLES, key=lambda c: int(c[1:])) == [f"X{i}" for i in range(1, 37)]
    claude = _text("CLAUDE.md")
    assert "X21–X29" in claude and "X30–X36" in claude


def test_readme_is_the_v13_cheat_sheet():
    readme = _text("README.md")
    assert readme.startswith("# pid_graph (Neo4j, ontology v1.3)") and "PID_GRAPH_ONTOLOGY_V1_3.md" in readme
    for module in ("pid_graph.load_pidkg", "pid_graph.topology_queries", "pid_graph.summary", "eval.topology_eval", "--pidkg"):
        assert module in readme, module
    for needle in ("review_register_U-100.xlsx", "neo4j-pidgraph", "7688", "EXPLORATION ONLY", "THIRD_PARTY_NOTICES.md"):
        assert needle in readme, needle
    # every module the README tells you to run exists
    for mod in set(re.findall(r"python -m (pid_graph\.\w+|eval\.\w+|pid_graph)\b", readme)):
        path = ROOT / (mod.replace(".", "/") + ".py") if "." in mod else ROOT / "pid_graph" / "__main__.py"
        assert path.is_file(), f"README runs {mod}, which does not exist"


def test_plan_records_what_was_built_in_every_phase():
    plan = _text("PIDKG_UPGRADE.md")
    assert plan.count("As built (10 Nov 2026)") + plan.count("As run (10 Nov 2026)") >= 8
    assert "C:\\dev\\kg_suppression" in plan and "v1.3.0" in plan
    decisions = _text("PID_GRAPH_DECISIONS.md")
    assert "## 14. v1.3 decisions" in decisions and all(f"D-V13-{i:02d}" in decisions for i in range(1, 12))
