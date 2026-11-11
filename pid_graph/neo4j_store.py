"""Neo4j backend: constraints, wipe-per-unit, batched MERGE writes, and reads in the
same shape as MemoryStore so reconcile/eval do not care which one they are given."""
from __future__ import annotations

from . import ontology as O
from .records import MemoryStore


def _key_pattern(label: str, var: str = "r.key") -> str:
    return "{" + ", ".join(f"{k}: {var}.{k}" for k in O.KEYS[label]) + "}"


class Neo4jStore:
    def __init__(self, driver, database: str = "neo4j"):
        self.driver = driver
        self.database = database

    def _run(self, cypher: str, **params):
        with self.driver.session(database=self.database) as s:
            return [r.data() for r in s.run(cypher, **params)]

    # ---- schema ---------------------------------------------------------
    def ensure_schema(self) -> list[str]:
        """Idempotent. Single-property uniqueness per key; Document gets a derived doc_key
        (doc_no + '|' + rev) so uniqueness holds on Community edition (decision D-P1-04)."""
        stmts = []
        for label, keys in O.KEYS.items():
            if len(keys) == 1:
                stmts.append(f"CREATE CONSTRAINT {label.lower()}_{keys[0]}_unique IF NOT EXISTS "
                             f"FOR (n:{label}) REQUIRE n.{keys[0]} IS UNIQUE")
            else:
                stmts.append(f"CREATE CONSTRAINT {label.lower()}_doc_key_unique IF NOT EXISTS "
                             f"FOR (n:{label}) REQUIRE n.doc_key IS UNIQUE")
                for k in keys:
                    stmts.append(f"CREATE INDEX {label.lower()}_{k}_idx IF NOT EXISTS FOR (n:{label}) ON (n.{k})")
            stmts.append(f"CREATE INDEX {label.lower()}_unit_idx IF NOT EXISTS FOR (n:{label}) ON (n.unit)")
        for c in stmts:
            self._run(c)
        return stmts

    def wipe_unit(self, unit: str) -> int:
        """Full-rebuild rule: delete every node (and its edges) loaded for this unit,
        plus stubs this unit created that are STILL stubs. A stub that another unit's
        load has since filled belongs to that unit now and is left alone."""
        rows = self._run("MATCH (n) WHERE n.unit = $unit OR (n.stub_unit = $unit AND coalesce(n.stub, false)) "
                         "DETACH DELETE n RETURN count(*) AS deleted", unit=unit)
        return rows[0]["deleted"] if rows else 0

    # ---- write ----------------------------------------------------------
    def write(self, store: MemoryStore, batch: int = 500) -> dict:
        written = {"nodes": 0, "rels": 0}
        by_label: dict[str, list] = {}
        for n in store.nodes():
            props = dict(n["props"])
            if n["label"] == "Document":
                props["doc_key"] = f"{n['key']['doc_no']}|{n['key']['rev']}"
            by_label.setdefault(n["label"], []).append({"key": n["key"], "props": props})
        for label, rows in by_label.items():
            cypher = (f"UNWIND $rows AS r MERGE (n:{label} {_key_pattern(label)}) "
                      f"SET n += r.props RETURN count(n) AS c")
            for i in range(0, len(rows), batch):
                written["nodes"] += self._run(cypher, rows=rows[i:i + batch])[0]["c"]
        by_rel: dict[tuple, list] = {}
        for r in store.rels():
            by_rel.setdefault((r["type"], r["start_label"], r["end_label"]), []).append(
                {"sk": r["start_key"], "ek": r["end_key"], "props": r["props"]})
        for (rel, sl, el), rows in by_rel.items():
            cypher = (f"UNWIND $rows AS r MATCH (a:{sl} {_key_pattern(sl, 'r.sk')}) "
                      f"MATCH (b:{el} {_key_pattern(el, 'r.ek')}) "
                      f"MERGE (a)-[e:{rel} {{source_doc: r.props.source_doc}}]->(b) "
                      f"SET e += r.props RETURN count(e) AS c")
            for i in range(0, len(rows), batch):
                written["rels"] += self._run(cypher, rows=rows[i:i + batch])[0]["c"]
        return written

    # ---- read (MemoryStore-compatible) ----------------------------------
    def nodes(self, label: str | None = None) -> list[dict]:
        out = []
        for lab in ([label] if label else O.LABELS):
            for row in self._run(f"MATCH (n:{lab}) RETURN properties(n) AS p"):
                p = row["p"]
                key = {k: p.get(k) for k in O.KEYS[lab]}
                out.append({"label": lab, "key": key,
                            "props": {k: v for k, v in p.items() if k not in key and k != "doc_key"}})
        return out

    def rels(self, rel: str | None = None) -> list[dict]:
        out = []
        for typ in ([rel] if rel else O.RELS):
            q = (f"MATCH (a)-[e:{typ}]->(b) RETURN labels(a)[0] AS sl, properties(a) AS a, "
                 f"labels(b)[0] AS el, properties(b) AS b, properties(e) AS e")
            for row in self._run(q):
                out.append({"type": typ, "start_label": row["sl"],
                            "start_key": {k: row["a"].get(k) for k in O.KEYS[row["sl"]]},
                            "end_label": row["el"],
                            "end_key": {k: row["b"].get(k) for k in O.KEYS[row["el"]]},
                            "props": row["e"]})
        return out

    def counts(self) -> dict:
        by_label = {r["l"]: r["c"] for r in self._run(
            "MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY l")}
        by_rel = {r["t"]: r["c"] for r in self._run(
            "MATCH ()-[e]->() RETURN type(e) AS t, count(*) AS c ORDER BY t")}
        return {"nodes": sum(by_label.values()), "rels": sum(by_rel.values()),
                "by_label": by_label, "by_rel": by_rel}

    @property
    def conflicts(self):
        return []
