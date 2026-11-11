"""Start the MCP server over stdio exactly as a client would, list the tools, call them.

Runs under pytest (skipped when Neo4j is not reachable) or directly:
    python tests/test_mcp_smoke.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _attr(obj, *names, default=None):
    for n in names:
        if getattr(obj, n, None) is not None:
            return getattr(obj, n)
    return default


def _payload(result):
    structured = _attr(result, "structured_content", "structuredContent")
    if structured:
        return structured.get("result", structured) if isinstance(structured, dict) and set(structured) == {"result"} else structured
    for block in result.content:
        if getattr(block, "type", "") == "text":
            try:
                return json.loads(block.text)
            except json.JSONDecodeError:
                return block.text
    return None


async def _run() -> dict:
    params = StdioServerParameters(command=sys.executable, args=["-m", "pid_graph.mcp_server"], cwd=str(ROOT))
    out: dict = {}
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            init = await s.initialize()
            info = _attr(init, "server_info", "serverInfo")
            out["server"] = f"{info.name} {info.version}"
            tools = await s.list_tools()
            out["tools"] = sorted(t.name for t in tools.tools)
            for name, args in [
                ("graph_info", {}),
                ("find", {"query": "PT-100"}),
                ("describe", {"identifier": "XV-1002"}),
                ("describe", {"identifier": "NOT-A-TAG"}),
                ("list_sifs", {}),
                ("documents", {}),
                ("out_of_service", {"tag": "PT-1001A"}),
                ("out_of_service", {"tag": "XV-1001"}),
                ("shelve_impact", {"alarm_id": "PT-1001A.PAH"}),
                ("moc_impact", {"identifier": "L-101", "hops": 2}),
                ("trip", {"sif_id": "SIF-100-02"}),
                ("exceptions", {"code": "X10"}),
                ("schema_reference", {}),
                ("read_cypher", {"cypher": "MATCH (s:SIF) RETURN s.sif_id AS sif ORDER BY sif"}),
                ("read_cypher", {"cypher": "MATCH (n) DETACH DELETE n"}),
            ]:
                r = await s.call_tool(name, args)
                out[f"{name}:{json.dumps(args, sort_keys=True)}"] = {"is_error": bool(_attr(r, "is_error", "isError", default=False)),
                                                                     "data": _payload(r)}
    return out


def _neo4j_up() -> bool:
    try:
        from pid_graph.db import get_driver
        d = get_driver()
        d.verify_connectivity()
        d.close()
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _neo4j_up(), reason="Neo4j not reachable")
def test_mcp_server_over_stdio():
    out = asyncio.run(_run())
    assert out["server"].startswith("pid_graph")
    assert {"out_of_service", "shelve_impact", "moc_impact", "trip", "exceptions", "describe", "find",
            "list_sifs", "documents", "graph_info", "schema_reference", "read_cypher"} <= set(out["tools"])
    assert not any(v["is_error"] for k, v in out.items() if isinstance(v, dict) and "is_error" in v)
    oos = out['out_of_service:{"tag": "PT-1001A"}']["data"]
    assert oos["as_initiator"][0]["status"] == "DEGRADED"
    cur = {c["alarm"]: c["validity"] for c in oos["as_initiator"][0]["curated_compensating_alarms"]}
    assert cur["PT-1005.PAH"] == "valid" and cur["PT-1001A.PAH"].startswith("INVALID NOW")
    xv = out['out_of_service:{"tag": "XV-1001"}']["data"]
    assert {x["sif"]: x["status"] for x in xv["as_final_element"]}["SIF-100-03"].startswith("DEFEATED")
    assert out['describe:{"identifier": "NOT-A-TAG"}']["data"]["error"] == "not in graph"
    x10 = out['exceptions:{"code": "X10"}']["data"]
    assert x10["count"] == 1 and x10["exceptions"][0]["id"] == "SIF-100-02"
    assert out['trip:{"sif_id": "SIF-100-02"}']["data"]["voting_check"][0]["listed"] == 2
    ok = out['read_cypher:{"cypher": "MATCH (s:SIF) RETURN s.sif_id AS sif ORDER BY sif"}']["data"]
    assert [r["sif"] for r in ok["rows"]] == ["SIF-100-01", "SIF-100-02", "SIF-100-03"]
    bad = out['read_cypher:{"cypher": "MATCH (n) DETACH DELETE n"}']["data"]
    assert "error" in bad
    # the write attempt must not have touched the graph
    assert out["graph_info:{}"]["data"]["nodes_by_label"]["SIF"] == 3


if __name__ == "__main__":
    res = asyncio.run(_run())
    print(res["server"])
    print(f"tools ({len(res['tools'])}): {', '.join(res['tools'])}")
    for k, v in res.items():
        if isinstance(v, dict) and "is_error" in v:
            print(f"  {'FAIL' if v['is_error'] else 'ok  '} {k} -> {json.dumps(v['data'], default=str)[:150]}")
