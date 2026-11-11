"""In-memory graph store with Neo4j MERGE semantics.

Loaders write here first. The Neo4j store then writes the merged result in one
pass (full rebuild per unit), and reconcile/eval can read either store through
the same methods: nodes(label), rels(type), counts(), conflicts.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import ontology as O


def node_key(label: str, key: dict) -> tuple:
    return (label, tuple(str(key[k]) for k in O.KEYS[label]))


# Provenance-like properties that describe where a fact came from, not the fact itself.
# They never count as property conflicts.
NOT_A_FACT = set(O.PROVENANCE) | {"source_ref", "source_file", "stub_unit"}


@dataclass
class Conflict:
    label: str
    key: dict
    prop: str
    existing: str
    incoming: str
    existing_source: str
    incoming_source: str


@dataclass
class MemoryStore:
    _nodes: dict = field(default_factory=dict)
    _rels: dict = field(default_factory=dict)
    conflicts: list[Conflict] = field(default_factory=list)

    # ---- writes ---------------------------------------------------------
    def merge_node(self, label: str, key: dict, props: dict, *, stub: bool = False) -> None:
        O.check_key(label, key)
        O.check_provenance(props, f"{label} {key}")
        clean = {k: v for k, v in props.items() if v not in (None, "")}
        nk = node_key(label, key)
        if nk not in self._nodes:
            self._nodes[nk] = {"label": label, "key": dict(key), "props": {**clean, "stub": stub}}
            return
        n = self._nodes[nk]["props"]
        if n.get("stub") and not stub:
            # A stub created from a reference is now being filled from its owning source:
            # the real source takes over the provenance and the flag (decisions section 6).
            for p in O.PROVENANCE:
                if clean.get(p):
                    n[p] = clean[p]
            n["stub"] = False
        for p, v in clean.items():
            if p in NOT_A_FACT:
                continue
            if n.get(p) in (None, ""):
                n[p] = v
            elif str(n[p]) != str(v):
                # Conflict rule (ontology section 4): never pick a winner silently.
                self.conflicts.append(Conflict(label, dict(key), p, str(n[p]), str(v),
                                               n.get("source_doc", ""), clean.get("source_doc", "")))

    def merge_rel(self, rel: str, start_label: str, start_key: dict, end_label: str, end_key: dict, props: dict) -> None:
        O.check_rel(rel, start_label, end_label)
        O.check_key(start_label, start_key)
        O.check_key(end_label, end_key)
        O.check_provenance(props, f"{rel} {start_key}->{end_key}")
        sk, ek = node_key(start_label, start_key), node_key(end_label, end_key)
        if sk not in self._nodes or ek not in self._nodes:
            raise KeyError(f"{rel}: endpoint missing in store: {sk if sk not in self._nodes else ek}")
        clean = {k: v for k, v in props.items() if v not in (None, "")}
        # Edge identity includes the evidencing document (decisions section 6, D-P1-06):
        # an index claim and a drawing extraction of the same fact are two edges with
        # two provenances, so agreement and disagreement stay queryable (CQ7).
        rk = (rel, sk, ek, clean["source_doc"])
        if rk not in self._rels:
            self._rels[rk] = {"type": rel, "start_label": start_label, "start_key": dict(start_key),
                              "end_label": end_label, "end_key": dict(end_key), "props": clean}
            return
        e = self._rels[rk]["props"]
        for p, v in clean.items():
            if e.get(p) in (None, ""):
                e[p] = v

    # ---- reads ----------------------------------------------------------
    def nodes(self, label: str | None = None) -> list[dict]:
        return [n for n in self._nodes.values() if label is None or n["label"] == label]

    def rels(self, rel: str | None = None) -> list[dict]:
        return [r for r in self._rels.values() if rel is None or r["type"] == rel]

    def has_node(self, label: str, key: dict) -> bool:
        return node_key(label, key) in self._nodes

    def get_node(self, label: str, key: dict) -> dict | None:
        return self._nodes.get(node_key(label, key))

    def counts(self) -> dict:
        by_label: dict[str, int] = {}
        for n in self._nodes.values():
            by_label[n["label"]] = by_label.get(n["label"], 0) + 1
        by_rel: dict[str, int] = {}
        for r in self._rels.values():
            by_rel[r["type"]] = by_rel.get(r["type"], 0) + 1
        return {"nodes": len(self._nodes), "rels": len(self._rels),
                "by_label": dict(sorted(by_label.items())), "by_rel": dict(sorted(by_rel.items()))}

    def to_dict(self) -> dict:
        return {"nodes": self.nodes(), "rels": self.rels(),
                "conflicts": [c.__dict__ for c in self.conflicts]}
