"""Phase 1 step 1: confirm environment before any loading."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DOCS = ["PID_GRAPH_ONTOLOGY_V1.md", "PID_GRAPH_DECISIONS.md"]


def main() -> int:
    ok = True
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")

    for name in REQUIRED_DOCS:
        present = (ROOT / name).exists()
        ok &= present
        print(f"[{'OK' if present else 'MISSING'}] {name}")

    xlsx = sorted((ROOT / "data").glob("*.xlsx"))
    pdfs = sorted((ROOT / "data").glob("*.pdf"))
    print(f"[{'OK' if xlsx else 'MISSING'}] data/*.xlsx  -> {[p.name for p in xlsx]}")
    print(f"[{'OK' if pdfs else 'MISSING'}] data/*.pdf   -> {[p.name for p in pdfs]}")
    ok &= bool(xlsx) and bool(pdfs)

    env_ok = (ROOT / ".env").exists()
    ok &= env_ok
    print(f"[{'OK' if env_ok else 'MISSING'}] .env")

    docker = shutil.which("docker")
    print(f"[{'OK' if docker else 'MISSING'}] docker CLI -> {docker}")
    if docker:
        out = subprocess.run([docker, "ps", "--filter", "name=neo4j-kg", "--format", "{{.Names}} {{.Status}}"],
                             capture_output=True, text=True)
        running = "neo4j-kg" in out.stdout
        ok &= running
        print(f"[{'OK' if running else 'NOT RUNNING'}] container neo4j-kg -> {out.stdout.strip() or '(not found)'}")
    else:
        ok = False

    if env_ok and docker:
        try:
            from db import check_connection  # noqa: WPS433
            print(f"[OK] Neo4j reachable: {check_connection()}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"[FAIL] Neo4j connection: {exc}")

    print("\nENVIRONMENT READY" if ok else "\nENVIRONMENT NOT READY - fix the items above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
