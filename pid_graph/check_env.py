"""Phase 1 step 1: confirm the environment before any loading."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DOCS = ["PID_GRAPH_ONTOLOGY_V1_2.md", "PID_GRAPH_DECISIONS.md"]


def main() -> int:
    ok = True
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    for name in REQUIRED_DOCS:
        present = (ROOT / name).exists()
        ok &= present
        print(f"[{'OK' if present else 'MISSING'}] {name}")
    xlsx = sorted((ROOT / "data").glob("*.xlsx"))
    csvs = sorted((ROOT / "data").glob("*.csv"))
    print(f"[{'OK' if xlsx else 'MISSING'}] data/*.xlsx -> {[p.name for p in xlsx]}")
    print(f"[{'OK' if csvs else 'MISSING'}] data/*.csv  -> {[p.name for p in csvs]}")
    ok &= bool(xlsx)

    neo_ok = True
    env_ok = (ROOT / ".env").exists()
    print(f"[{'OK' if env_ok else 'MISSING'}] .env")
    docker = shutil.which("docker")
    print(f"[{'OK' if docker else 'MISSING'}] docker CLI -> {docker}")
    if docker:
        import os
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        # pid_graph has its own container; it must not share a database with another project (scripts/setup_neo4j.ps1)
        name = os.getenv("NEO4J_CONTAINER", "neo4j-pidgraph")
        out = subprocess.run([docker, "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}} {{.Status}}"],
                             capture_output=True, text=True)
        running = name in out.stdout
        neo_ok &= running
        print(f"[{'OK' if running else 'NOT RUNNING'}] container {name} -> {out.stdout.strip() or '(not found)'}")
    else:
        neo_ok = False
    if env_ok and docker:
        try:
            from .db import check_connection
            print(f"[OK] Neo4j reachable: {check_connection()}")
        except Exception as exc:  # noqa: BLE001
            neo_ok = False
            print(f"[FAIL] Neo4j connection: {exc}")
    else:
        neo_ok = False

    if ok and neo_ok:
        print("\nENVIRONMENT READY (neo4j backend available)")
    elif ok:
        print("\nENVIRONMENT READY FOR --backend memory ONLY (Neo4j not available)")
    else:
        print("\nENVIRONMENT NOT READY - fix the items above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
