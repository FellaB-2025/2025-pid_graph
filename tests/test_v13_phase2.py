"""v1.3 Phase 2 (PIDKG_UPGRADE.md): pid-to-kg is brought in as an unmodified tool.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

Nothing of theirs is committed to pid_graph; the source, pinned commit and copyright line are recorded.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PINNED = "7ee3a82e655c13c11aa26ee25bdc2c0c01bd58f1"


def _git(*args: str) -> str:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def test_notice_records_source_commit_and_copyright():
    text = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "https://github.com/ScottDuncanAI/PID-to-Knowledge-Graph" in text
    assert PINNED in text
    assert "MIT" in text and "Copyright (c) 2026 The pid-to-kg contributors" in text


def test_nothing_of_theirs_is_tracked():
    assert _git("ls-files", "third_party", ".venv-pidkg", "work", "data/external").strip() == ""


@pytest.mark.parametrize("path", ["third_party/pid-to-kg/LICENSE", ".venv-pidkg/pyvenv.cfg", "work/U-100/kg/graph.json",
                                  "data/external/anything.pdf"])
def test_working_areas_are_ignored(path):
    assert _git("check-ignore", path).strip() == path


def test_clone_is_at_the_pinned_commit_and_unmodified():
    clone = ROOT / "third_party" / "pid-to-kg"
    if not (clone / ".git").exists():
        pytest.skip("pid-to-kg is not cloned on this machine (see THIRD_PARTY_NOTICES.md)")
    assert _git("-C", str(clone), "rev-parse", "HEAD").strip() == PINNED
    assert _git("-C", str(clone), "status", "--porcelain").strip() == ""
