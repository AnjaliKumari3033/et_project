"""
NovaChem Industrial Knowledge Graph - Query Library
====================================================
Production-grade query interface for the NovaChem MultiDiGraph.

CHANGE LOG (duplicate-edge refactor):
--------------------------------------
After build_graph.py was refactored to use add_unique_edge(), each
(source, relation, target) triple now has exactly ONE edge in the graph.
That edge carries:

    source_docs     : list[str]  — all source files/datasets that contributed
    event_ids       : list[str]  — all event IDs this relation was seen in
    grounded        : bool       — True if ANY source was grounded
    occurrence_count: int        — how many times this relation was observed

All query functions that return lists of entities have been updated to:
  - read occurrence_count for sorting failures by frequency
  - read event_ids for event association
  - merge roles for people (same person, different relation types)
  - deduplicate by node_id (now trivially guaranteed by the graph structure,
    but the query layer enforces it independently for safety)

The _single_hop() method is the central traversal primitive — it now reads
the new edge schema and the _edge_source() / _edge_grounded() helpers
have been updated accordingly.

equipment_summary() now returns the structured format requested:
    unique counts + top failures sorted by occurrence_count + merged people.

All existing public methods are preserved with identical signatures.
"""

from __future__ import annotations

import logging
import pickle
from collections import Counter, defaultdict
from typing import Any, Iterator, Literal

import networkx as nx
from rapidfuzz import fuzz, process

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
NodeID    = str
Direction = Literal["out", "in", "both"]

# ---------------------------------------------------------------------------
# Constants — all relation names verified against build_graph.py
# ---------------------------------------------------------------------------
_PERSON_RELATIONS: frozenset[str] = frozenset(
    ["repaired_by", "documented_by", "reported_by", "assigned_to"]
)
_PROCESS_FLOW_SOURCE = "equipment_relationships.xlsx"
_EVENT_PREFIX        = "EVENT:"


# ===========================================================================
# KnowledgeGraph
# ===========================================================================
class KnowledgeGraph:
    """
    Production query interface for the NovaChem Industrial Knowledge Graph.

    The underlying graph is a ``networkx.MultiDiGraph`` loaded once at
    construction time and never mutated by this class.

    Usage
    -----
    >>> kg = KnowledgeGraph("graph.gpickle")
    >>> kg.get_failures("P-101")
    >>> kg.equipment_summary("P-101")
    >>> kg.get_context("P-101")
    """

    # ------------------------------------------------------------------ #
    # 1. GRAPH LOADING                                                     #
    # ------------------------------------------------------------------ #

    def __init__(self, graph_path: str = "data/graph/knowledge_graph.gpickle") -> None:
        """
        Load the serialised NetworkX MultiDiGraph from *graph_path*.

        Raises
        ------
        FileNotFoundError, ValueError
        """
        self._graph_path = graph_path
        self._G: nx.MultiDiGraph = self._load_graph(graph_path)

        if not isinstance(self._G, nx.MultiDiGraph):
            raise ValueError(
                f"Expected networkx.MultiDiGraph, got {type(self._G).__name__}. "
                "Rebuild the graph with build_graph.py."
            )

        # Build label index and per-type sub-indices once at startup.
        self._label_index: dict[str, NodeID] = {}
        self._type_index:  dict[str, dict[str, NodeID]] = {}
        self._build_indices()

        # Pre-compute immutable statistics (O(1) retrieval later)
        self._node_type_counts: dict[str, int] = self._compute_node_type_counts()
        self._relation_counts:  dict[str, int] = self._compute_relation_counts()

        logger.info(
            "KnowledgeGraph loaded: %d nodes, %d edges from '%s'",
            self._G.number_of_nodes(),
            self._G.number_of_edges(),
            graph_path,
        )

    @staticmethod
    def _load_graph(path: str) -> nx.MultiDiGraph:
        """Deserialise graph, handling NX 2.x and 3.x pickle formats."""
        try:
            G = nx.read_gpickle(path)          # type: ignore[attr-defined]
            logger.debug("Graph loaded via nx.read_gpickle.")
            return G
        except AttributeError:
            pass

        try:
            with open(path, "rb") as fh:
                G = pickle.load(fh)
            logger.debug("Graph loaded via pickle.load.")
            return G
        except FileNotFoundError:
            logger.error("Graph file not found: '%s'", path)
            raise
        except Exception as exc:
            logger.error("Failed to load graph from '%s': %s", path, exc)
            raise RuntimeError(f"Could not load graph from '{path}'") from exc

    def _build_indices(self) -> None:
        """Build label → node_id and per-type sub-index maps."""
        label_index: dict[str, NodeID]            = {}
        type_index:  dict[str, dict[str, NodeID]] = {}

        for node_id in self._G.nodes:
            label = self._node_label(node_id)
            ntype = self._get_node_type(node_id)

            if label in label_index and label_index[label] != node_id:
                logger.warning(
                    "Label collision: '%s' -> '%s' and '%s'. Last writer wins.",
                    label, label_index[label], node_id,
                )
            label_index[label] = node_id
            type_index.setdefault(ntype, {})[label] = node_id

        self._label_index = label_index
        self._type_index  = type_index

    # ------------------------------------------------------------------ #
    # 2. SEARCH                                                            #
    # ------------------------------------------------------------------ #

    def search(
        self,
        query: str,
        *,
        fuzzy: bool           = True,
        top_k: int            = 10,
        node_type: str | None = None,
        score_cutoff: int     = 60,
    ) -> list[dict[str, Any]]:
        """
        Search for graph nodes whose label matches *query*.

        Returns list of dicts: node_id, label, node_type, score.
        """
        candidates: dict[str, NodeID] = (
            self._type_index.get(node_type, {})
            if node_type is not None
            else self._label_index
        )

        if not candidates:
            return []

        if fuzzy:
            raw = process.extract(
                query, list(candidates.keys()),
                scorer=fuzz.WRatio,
                limit=top_k,
                score_cutoff=score_cutoff,
            )
            return [
                {
                    "node_id":   candidates[label],
                    "label":     label,
                    "node_type": self._get_node_type(candidates[label]),
                    "score":     round(score, 1),
                }
                for label, score, _ in raw
            ]
        else:
            q_lower = query.lower().strip()
            return [
                {
                    "node_id":   node_id,
                    "label":     label,
                    "node_type": self._get_node_type(node_id),
                    "score":     100,
                }
                for label, node_id in candidates.items()
                if label.lower() == q_lower
            ][:top_k]

    def resolve_node(
        self,
        query: str,
        *,
        node_type: str | None = None,
    ) -> NodeID | None:
        """
        Resolve a query string to a single canonical node id.

        Resolution order: direct key → exact label → fuzzy top-1.
        """
        if query in self._G:
            ntype = self._get_node_type(query)
            if node_type is None or ntype == node_type:
                return query

        exact = self.search(query, fuzzy=False, top_k=1, node_type=node_type)
        if exact:
            return exact[0]["node_id"]

        fuzzy_hits = self.search(
            query, fuzzy=True, top_k=1, node_type=node_type, score_cutoff=55
        )
        if fuzzy_hits:
            return fuzzy_hits[0]["node_id"]

        logger.warning("resolve_node(%r, node_type=%r): no match.", query, node_type)
        return None

    # ------------------------------------------------------------------ #
    # 3. HELPER METHODS                                                    #
    # ------------------------------------------------------------------ #

    def _node_label(self, node_id: NodeID) -> str:
        """Return human-readable label for a node."""
        attrs = self._G.nodes.get(node_id, {})
        if "name"  in attrs: return str(attrs["name"])
        if "label" in attrs: return str(attrs["label"])
        sid = str(node_id)
        if sid.startswith(_EVENT_PREFIX):
            return sid[len(_EVENT_PREFIX):]
        return sid

    def _get_node_type(self, node_id: NodeID) -> str:
        """Return node_type attribute or 'Unknown'."""
        return self._G.nodes.get(node_id, {}).get("node_type", "Unknown")

    def _get_node_attrs(self, node_id: NodeID) -> dict[str, Any]:
        """Return a copy of all node attributes."""
        return dict(self._G.nodes.get(node_id, {}))

    def _edge_relation(self, data: dict[str, Any]) -> str | None:
        """Extract relation string from edge data dict."""
        return (
            data.get("relation")
            or data.get("relation_type")
            or data.get("label")
        )

    # CHANGED: The original helper returned a single string 'source'.
    # After the refactor, source_docs is a list.  This helper returns
    # the primary source (first entry) for backwards-compatible display.
    def _edge_primary_source(self, data: dict[str, Any]) -> str | None:
        """Return the first source_doc from the edge, or None."""
        docs = data.get("source_docs", [])
        # Graceful fallback: graphs built before this refactor stored 'source'
        # as a plain string. Support both schemas.
        if isinstance(docs, list):
            return docs[0] if docs else None
        return data.get("source")  # legacy scalar

    # CHANGED: Same dual-schema support for event_ids.
    def _edge_primary_event(self, data: dict[str, Any]) -> str | None:
        """Return the first event_id from the edge, or None."""
        ids = data.get("event_ids", [])
        if isinstance(ids, list):
            return ids[0] if ids else None
        return data.get("event_id")  # legacy scalar

    def _edge_occurrence_count(self, data: dict[str, Any]) -> int:
        """Return occurrence_count, defaulting to 1 for legacy edges."""
        return data.get("occurrence_count", 1)

    def _event_id_to_node(self, event_id: str) -> NodeID:
        if event_id.startswith(_EVENT_PREFIX):
            return event_id
        return f"{_EVENT_PREFIX}{event_id}"

    def _strip_event_prefix(self, node_id: NodeID) -> str:
        return node_id[len(_EVENT_PREFIX):] if node_id.startswith(_EVENT_PREFIX) else node_id

    # ------------------------------------------------------------------ #
    # 4. GENERIC GRAPH TRAVERSAL                                           #
    # ------------------------------------------------------------------ #

    def neighbors(
        self,
        node_id: NodeID,
        *,
        relation: str | list[str] | None = None,
        node_type: str | None             = None,
        direction: Direction              = "out",
        depth: int                        = 1,
        grounded_only: bool               = False,
    ) -> list[dict[str, Any]]:
        """
        Core traversal method — used by every specialised query.

        Returns neighbour records within *depth* hops, filtered by relation,
        node_type, direction, and grounding.

        Each record contains:
            node_id, label, node_type, relation, source_docs, event_ids,
            grounded, occurrence_count, depth.
        """
        if node_id not in self._G:
            return []

        if direction not in ("out", "in", "both"):
            raise ValueError(f"direction must be 'out', 'in', or 'both', got {direction!r}.")

        relations: frozenset[str] | None = None
        if relation is not None:
            relations = frozenset(
                [relation] if isinstance(relation, str) else relation
            )

        if depth == 1:
            return list(
                self._single_hop(
                    node_id,
                    relations=relations,
                    node_type=node_type,
                    direction=direction,
                    grounded_only=grounded_only,
                    current_depth=1,
                )
            )
        return self._bfs(
            node_id,
            relations=relations,
            node_type=node_type,
            direction=direction,
            grounded_only=grounded_only,
            max_depth=depth,
        )

    def _single_hop(
        self,
        node_id: NodeID,
        *,
        relations: frozenset[str] | None,
        node_type: str | None,
        direction: Direction,
        grounded_only: bool,
        current_depth: int,
    ) -> Iterator[dict[str, Any]]:
        """
        Yield neighbour records for a single hop from *node_id*.

        CHANGE: Result dict now includes source_docs (list), event_ids (list),
        and occurrence_count (int) in place of the old scalar source/event_id.
        Deduplication key uses (neighbour, rel) only — since add_unique_edge()
        guarantees at most one edge per (src, tgt, relation) triple, there are
        no parallel duplicates to collapse at query time.
        """
        G = self._G
        seen: set[tuple[str, str | None]] = set()  # (neighbour, relation)

        def _process(neighbour: NodeID, data: dict[str, Any]) -> dict[str, Any] | None:
            rel = self._edge_relation(data)

            # Since the graph now has at most one edge per (src, tgt, relation),
            # this dedup is a safety net only.
            sig = (neighbour, rel)
            if sig in seen:
                return None
            seen.add(sig)

            if relations is not None and rel not in relations:
                return None
            if grounded_only and not data.get("grounded", True):
                return None

            n_type = self._get_node_type(neighbour)
            if node_type is not None and n_type != node_type:
                return None

            # CHANGED: expose source_docs/event_ids as lists
            # + occurrence_count for ranking
            source_docs = data.get("source_docs", [])
            event_ids   = data.get("event_ids", [])
            # Backwards-compat with graphs built before the refactor
            if not isinstance(source_docs, list):
                source_docs = [source_docs] if source_docs else []
            if not isinstance(event_ids, list):
                event_ids = [event_ids] if event_ids else []

            return {
                "node_id":          neighbour,
                "label":            self._node_label(neighbour),
                "node_type":        n_type,
                "relation":         rel,
                "source_docs":      source_docs,
                "event_ids":        event_ids,
                "grounded":         data.get("grounded", True),
                "occurrence_count": data.get("occurrence_count", 1),
                "depth":            current_depth,
            }

        # Two separate if-blocks (not if/elif) so both directions fire for "both"
        if direction in ("out", "both"):
            for _, v, data in G.out_edges(node_id, data=True):
                rec = _process(v, data)
                if rec is not None:
                    yield rec

        if direction in ("in", "both"):
            for u, _, data in G.in_edges(node_id, data=True):
                rec = _process(u, data)
                if rec is not None:
                    yield rec

    def _bfs(
        self,
        start: NodeID,
        *,
        relations: frozenset[str] | None,
        node_type: str | None,
        direction: Direction,
        grounded_only: bool,
        max_depth: int,
    ) -> list[dict[str, Any]]:
        """BFS traversal up to max_depth hops. Unchanged logic."""
        visited:  set[NodeID]          = {start}
        frontier: list[NodeID]         = [start]
        results:  list[dict[str, Any]] = []

        for depth in range(1, max_depth + 1):
            next_frontier: list[NodeID] = []
            for node_id in frontier:
                for record in self._single_hop(
                    node_id,
                    relations=relations,
                    node_type=node_type,
                    direction=direction,
                    grounded_only=grounded_only,
                    current_depth=depth,
                ):
                    results.append(record)
                    nid = record["node_id"]
                    if nid not in visited:
                        visited.add(nid)
                        next_frontier.append(nid)
            frontier = next_frontier
            if not frontier:
                break

        return results

    # ------------------------------------------------------------------ #
    # 5. EQUIPMENT QUERIES                                                 #
    # ------------------------------------------------------------------ #

    def get_failures(
        self,
        equipment: str,
        *,
        grounded_only: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Return unique failure modes for *equipment*, sorted by
        occurrence_count descending (most-observed failure first).

        Each result dict contains:
            node_id, label, node_type, occurrence_count,
            source_docs, event_ids, grounded.
        """
        node_id = self.resolve_node(equipment, node_type="Equipment")
        if node_id is None:
            logger.warning("get_failures: equipment '%s' not found.", equipment)
            return []

        raw = self.neighbors(
            node_id,
            relation="has_failure",
            node_type="FailureMode",
            direction="out",
            grounded_only=grounded_only,
        )

        # CHANGED: sort by occurrence_count descending.
        # The graph already guarantees one record per failure mode
        # (one edge per relation), but we sort for useful ranking.
        return sorted(raw, key=lambda r: r["occurrence_count"], reverse=True)

    def get_people(
        self,
        equipment: str,
        *,
        roles: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return unique people associated with *equipment*, with all their
        roles merged into a single record per person.

        CHANGED: In the old graph, the same person appeared multiple times
        (once per edge). Now there is at most one edge per (equipment, person,
        role) triple from the graph, but a person can have multiple DIFFERENT
        roles (repaired_by, assigned_to, etc.) — these are merged here.

        Returns list of dicts:
            node_id, label, node_type, roles (list), occurrence_count (sum),
            source_docs (merged), event_ids (merged), grounded.
        """
        node_id = self.resolve_node(equipment, node_type="Equipment")
        if node_id is None:
            logger.warning("get_people: equipment '%s' not found.", equipment)
            return []

        allowed: list[str] = roles if roles is not None else list(_PERSON_RELATIONS)

        raw = self.neighbors(
            node_id,
            relation=allowed,
            node_type="Person",
            direction="out",
        )

        # CHANGED: merge multiple role-edges for the same person into one record.
        merged: dict[NodeID, dict[str, Any]] = {}
        for rec in raw:
            pid = rec["node_id"]
            if pid not in merged:
                merged[pid] = {
                    "node_id":          pid,
                    "label":            rec["label"],
                    "node_type":        "Person",
                    "roles":            [rec["relation"]],
                    "occurrence_count": rec["occurrence_count"],
                    "source_docs":      list(rec["source_docs"]),
                    "event_ids":        list(rec["event_ids"]),
                    "grounded":         rec["grounded"],
                }
            else:
                # Same person, different role — merge
                if rec["relation"] not in merged[pid]["roles"]:
                    merged[pid]["roles"].append(rec["relation"])
                merged[pid]["occurrence_count"] += rec["occurrence_count"]
                for sd in rec["source_docs"]:
                    if sd not in merged[pid]["source_docs"]:
                        merged[pid]["source_docs"].append(sd)
                for eid in rec["event_ids"]:
                    if eid not in merged[pid]["event_ids"]:
                        merged[pid]["event_ids"].append(eid)
                if rec["grounded"]:
                    merged[pid]["grounded"] = True

        # Sort by occurrence_count descending (most active person first)
        return sorted(merged.values(), key=lambda r: r["occurrence_count"], reverse=True)

    def get_actions(self, equipment: str) -> list[dict[str, Any]]:
        """
        Return unique maintenance actions for *equipment*, sorted by
        occurrence_count descending.
        """
        node_id = self.resolve_node(equipment, node_type="Equipment")
        if node_id is None:
            logger.warning("get_actions: equipment '%s' not found.", equipment)
            return []

        raw = self.neighbors(
            node_id,
            relation="resolved_by",
            node_type="MaintenanceAction",
            direction="out",
        )
        # CHANGED: sorted by occurrence_count
        return sorted(raw, key=lambda r: r["occurrence_count"], reverse=True)

    def get_events(self, equipment: str) -> list[dict[str, Any]]:
        """
        Return unique EventChain nodes that involve *equipment*.

        CHANGED: EventChain node IDs are unique by definition (one node per
        event), so deduplication is trivially guaranteed. Enriched with
        date/severity/priority/status from node attributes.
        """
        node_id = self.resolve_node(equipment, node_type="Equipment")
        if node_id is None:
            logger.warning("get_events: equipment '%s' not found.", equipment)
            return []

        raw = self.neighbors(
            node_id,
            relation="involves",
            node_type="EventChain",
            direction="in",
        )

        enriched: list[dict[str, Any]] = []
        seen_events: set[str] = set()
        for rec in raw:
            eid = self._strip_event_prefix(rec["node_id"])
            if eid in seen_events:
                continue
            seen_events.add(eid)
            attrs = self._get_node_attrs(rec["node_id"])
            enriched.append({
                **rec,
                "event_id": eid,
                "date":     attrs.get("date"),
                "severity": attrs.get("severity"),
                "priority": attrs.get("priority"),
                "status":   attrs.get("status"),
            })
        return enriched

    def get_standards(self, equipment: str) -> list[dict[str, Any]]:
        """Return unique standards linked to *equipment*."""
        node_id = self.resolve_node(equipment, node_type="Equipment")
        if node_id is None:
            logger.warning("get_standards: equipment '%s' not found.", equipment)
            return []

        return self.neighbors(
            node_id,
            relation="follows_standard",
            node_type="Standard",
            direction="out",
        )

    def get_references(self, equipment: str) -> list[dict[str, Any]]:
        """
        Return unique public Reference documents linked to *equipment*.
        Enriched with doc_type and file_name from node attributes.
        """
        node_id = self.resolve_node(equipment, node_type="Equipment")
        if node_id is None:
            logger.warning("get_references: equipment '%s' not found.", equipment)
            return []

        raw = self.neighbors(
            node_id,
            relation="has_reference",
            node_type="Reference",
            direction="out",
        )

        return [
            {
                **rec,
                "doc_type":  self._get_node_attrs(rec["node_id"]).get("doc_type"),
                "file_name": self._get_node_attrs(rec["node_id"]).get("file_name"),
            }
            for rec in raw
        ]

    def get_related_equipment(
        self,
        equipment: str,
        *,
        include_spatial: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Return equipment related via process-flow or spatial proximity.

        CHANGED: source lookup now checks source_docs list instead of the
        old scalar 'source' field.
        """
        node_id = self.resolve_node(equipment, node_type="Equipment")
        if node_id is None:
            logger.warning("get_related_equipment: '%s' not found.", equipment)
            return []

        G = self._G
        results: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        def _add(
            neighbour: NodeID,
            rel: str,
            direction_label: str,
            data: dict[str, Any],
        ) -> None:
            if self._get_node_type(neighbour) != "Equipment":
                return
            sig = (neighbour, rel, direction_label)
            if sig in seen:
                return
            seen.add(sig)
            # CHANGED: source_docs is now a list
            source_docs = data.get("source_docs", [])
            if not isinstance(source_docs, list):
                source_docs = [source_docs] if source_docs else []
            results.append({
                "node_id":   neighbour,
                "label":     self._node_label(neighbour),
                "node_type": "Equipment",
                "relation":  rel,
                "direction": direction_label,
                "source_docs": source_docs,
                "grounded":  data.get("grounded", True),
                "reason":    data.get("reason"),
            })

        for _, v, data in G.out_edges(node_id, data=True):
            src_docs = data.get("source_docs", [])
            if not isinstance(src_docs, list):
                src_docs = [src_docs] if src_docs else []
            rel = self._edge_relation(data) or ""
            if _PROCESS_FLOW_SOURCE in src_docs:
                _add(v, rel, "downstream", data)
            elif include_spatial and rel == "near":
                _add(v, rel, "near", data)

        for u, _, data in G.in_edges(node_id, data=True):
            src_docs = data.get("source_docs", [])
            if not isinstance(src_docs, list):
                src_docs = [src_docs] if src_docs else []
            rel = self._edge_relation(data) or ""
            if _PROCESS_FLOW_SOURCE in src_docs:
                _add(u, rel, "upstream", data)
            elif include_spatial and rel == "near":
                _add(u, rel, "near", data)

        return results

    def get_failure_history(
        self,
        equipment: str,
        *,
        grounded_only: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Return complete failure history for *equipment*, enriched with
        root causes and sorted by occurrence_count descending.
        """
        node_id = self.resolve_node(equipment, node_type="Equipment")
        if node_id is None:
            logger.warning("get_failure_history: '%s' not found.", equipment)
            return []

        failure_edges = self.neighbors(
            node_id,
            relation="has_failure",
            node_type="FailureMode",
            direction="out",
            grounded_only=grounded_only,
        )

        history: list[dict[str, Any]] = []
        for fe in failure_edges:
            fm_id = fe["node_id"]
            root_causes = [
                r["label"]
                for r in self.neighbors(fm_id, relation="caused_by", direction="out", depth=1)
            ]
            history.append({
                "failure_mode":     fe["label"],
                "failure_node_id":  fm_id,
                "root_causes":      root_causes,
                # CHANGED: list fields instead of scalars
                "event_ids":        fe.get("event_ids", []),
                "source_docs":      fe.get("source_docs", []),
                "grounded":         fe.get("grounded", True),
                "occurrence_count": fe.get("occurrence_count", 1),
            })

        # CHANGED: sort by occurrence_count descending
        return sorted(history, key=lambda r: r["occurrence_count"], reverse=True)

    # ------------------------------------------------------------------ #
    # 6. FAILURE QUERIES                                                   #
    # ------------------------------------------------------------------ #

    def get_root_causes(
        self,
        failure: str,
        *,
        depth: int = 3,
    ) -> list[dict[str, Any]]:
        """Return root-cause chain for *failure* up to *depth* hops."""
        node_id = self.resolve_node(failure, node_type="FailureMode")
        if node_id is None:
            logger.warning("get_root_causes: '%s' not found.", failure)
            return []
        return self.neighbors(node_id, relation="caused_by", direction="out", depth=depth)

    def get_failure_taxonomy(self, failure: str) -> list[dict[str, Any]]:
        """
        Return taxonomy classification path for *failure*.
        Follows classified_as → part_of chain upward.
        """
        node_id = self.resolve_node(failure, node_type="FailureMode")
        if node_id is None:
            logger.warning("get_failure_taxonomy: '%s' not found.", failure)
            return []

        taxonomy_hits = self.neighbors(
            node_id, relation="classified_as", node_type="FailureTaxonomy", direction="out"
        )
        if not taxonomy_hits:
            return []

        results: list[dict[str, Any]] = []
        for hit in taxonomy_hits:
            tax_id = hit["node_id"]
            attrs  = self._get_node_attrs(tax_id)
            results.append({
                "taxonomy_node_id":   tax_id,
                "label":              hit["label"],
                "level1":             attrs.get("level1"),
                "level2":             attrs.get("level2"),
                "possible_cause":     attrs.get("possible_cause"),
                "affected_equipment": attrs.get("affected_equipment"),
                "recommended_action": attrs.get("recommended_action"),
                "hierarchy":          self._get_taxonomy_hierarchy(tax_id),
            })
        return results

    def _get_taxonomy_hierarchy(self, taxonomy_node_id: NodeID) -> list[str]:
        """Walk part_of edges outward (L3→L2→L1) with cycle guard."""
        path:    list[str]   = [self._node_label(taxonomy_node_id)]
        visited: set[NodeID] = {taxonomy_node_id}
        current: NodeID      = taxonomy_node_id

        for _ in range(5):
            parents = self.neighbors(
                current, relation="part_of", node_type="FailureTaxonomy",
                direction="out", depth=1,
            )
            if not parents:
                break
            parent_id = parents[0]["node_id"]
            if parent_id in visited:
                logger.warning(
                    "_get_taxonomy_hierarchy: cycle at '%s'. Stopping.", parent_id
                )
                break
            visited.add(parent_id)
            path.append(self._node_label(parent_id))
            current = parent_id

        return path

    def get_failure_chain(
        self,
        equipment: str,
        *,
        max_depth: int = 4,
        grounded_only: bool = False,
    ) -> dict[str, Any]:
        """Build full failure chain: Equipment → FailureModes → RootCauses → Taxonomy."""
        node_id = self.resolve_node(equipment, node_type="Equipment")
        if node_id is None:
            logger.warning("get_failure_chain: '%s' not found.", equipment)
            return {}

        failure_edges = self.neighbors(
            node_id, relation="has_failure", node_type="FailureMode",
            direction="out", grounded_only=grounded_only,
        )

        chains: list[dict[str, Any]] = []
        for fe in failure_edges:
            fm_id = fe["node_id"]
            root_causes = self.neighbors(
                fm_id, relation="caused_by", direction="out", depth=max_depth
            )
            taxonomy = self.get_failure_taxonomy(fe["label"])
            chains.append({
                "failure_mode":     fe["label"],
                "failure_node_id":  fm_id,
                "event_ids":        fe.get("event_ids", []),
                "source_docs":      fe.get("source_docs", []),
                "grounded":         fe.get("grounded", True),
                "occurrence_count": fe.get("occurrence_count", 1),
                "root_causes":      [r["label"] for r in root_causes],
                "taxonomy":         taxonomy,
            })

        return {
            "equipment_id":    node_id,
            "equipment_attrs": self._get_node_attrs(node_id),
            "failure_chains":  chains,
        }

    # ------------------------------------------------------------------ #
    # 7. PERSON QUERIES                                                    #
    # ------------------------------------------------------------------ #

    def get_equipment_for_person(self, person: str) -> list[dict[str, Any]]:
        """
        Return all equipment linked to *person* (incoming person-role edges).
        """
        node_id = self.resolve_node(person, node_type="Person")
        if node_id is None:
            logger.warning("get_equipment_for_person: '%s' not found.", person)
            return []
        return self.neighbors(
            node_id, relation=list(_PERSON_RELATIONS),
            node_type="Equipment", direction="in",
        )

    def get_events_for_person(self, person: str) -> list[dict[str, Any]]:
        """
        Return all events in which *person* was involved (two-hop traversal).
        """
        node_id = self.resolve_node(person, node_type="Person")
        if node_id is None:
            logger.warning("get_events_for_person: '%s' not found.", person)
            return []

        equipment_links = self.get_equipment_for_person(person)
        results: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        for eq_rec in equipment_links:
            eq_id = eq_rec["node_id"]
            role  = eq_rec["relation"]
            for ev in self.get_events(eq_id):
                sig = (ev["event_id"], eq_id, role)
                if sig in seen:
                    continue
                seen.add(sig)
                results.append({
                    "event_id":        ev["event_id"],
                    "equipment_id":    eq_id,
                    "equipment_label": self._node_label(eq_id),
                    "role":            role,
                    "date":            ev.get("date"),
                    "severity":        ev.get("severity"),
                    "priority":        ev.get("priority"),
                    "status":          ev.get("status"),
                })
        return results

    def get_person_profile(self, person: str) -> dict[str, Any]:
        """Return a complete profile for *person*."""
        node_id = self.resolve_node(person, node_type="Person")
        if node_id is None:
            logger.warning("get_person_profile: '%s' not found.", person)
            return {}
        return {
            "person":     self._node_label(node_id),
            "node_id":    node_id,
            "attributes": self._get_node_attrs(node_id),
            "equipment":  self.get_equipment_for_person(person),
            "events":     self.get_events_for_person(person),
        }

    # ------------------------------------------------------------------ #
    # 8. EVENT QUERIES                                                     #
    # ------------------------------------------------------------------ #

    def get_event(self, event_id: str) -> dict[str, Any]:
        """Return the full record for a single event."""
        chain_node = self._event_id_to_node(event_id)
        if chain_node not in self._G:
            logger.warning("get_event: '%s' not found.", event_id)
            return {}

        attrs    = self._get_node_attrs(chain_node)
        involved = self.neighbors(chain_node, relation="involves", direction="out")

        return {
            "event_id":  self._strip_event_prefix(chain_node),
            "node_id":   chain_node,
            "date":      attrs.get("date"),
            "severity":  attrs.get("severity"),
            "priority":  attrs.get("priority"),
            "status":    attrs.get("status"),
            "entities":  involved,
        }

    def get_event_summary(self, event_id: str) -> dict[str, Any]:
        """Return enriched event summary for LLM prompts / dashboards."""
        event = self.get_event(event_id)
        if not event:
            return {}

        entities = event.get("entities", [])

        def _by_type(ntype: str) -> list[str]:
            return [e["label"] for e in entities if e.get("node_type") == ntype]

        equipment_ids = [
            e["node_id"] for e in entities if e.get("node_type") == "Equipment"
        ]
        failure_chains: list[dict] = []
        for eq_id in equipment_ids:
            fc = self.get_failure_chain(eq_id)
            if fc:
                failure_chains.append(fc)

        return {
            "event_id": event["event_id"],
            "metadata": {
                "date":     event.get("date"),
                "severity": event.get("severity"),
                "priority": event.get("priority"),
                "status":   event.get("status"),
            },
            "equipment":      _by_type("Equipment"),
            "failures":       _by_type("FailureMode"),
            "people":         _by_type("Person"),
            "standards":      _by_type("Standard"),
            "actions":        _by_type("MaintenanceAction"),
            "failure_chains": failure_chains,
        }

    # ------------------------------------------------------------------ #
    # 9. CONTEXT GENERATION  (LLM API)                                    #
    # ------------------------------------------------------------------ #

    def equipment_summary(self, equipment: str) -> dict[str, Any]:
        """
        Return a structured, deduplicated summary of *equipment*.

        CHANGED: Output format now matches the requested structure:
          - Unique counts for each category
          - Failures sorted by occurrence_count (top failures highlighted)
          - People with merged roles list

        Returns
        -------
        dict with keys:
            equipment_id, attributes,
            counts (dict of unique counts),
            top_failures (sorted by occurrence_count),
            people (merged roles),
            standards, events, corrective_actions, references,
            related_equipment, failure_chains.
        """
        node_id = self.resolve_node(equipment, node_type="Equipment")
        if node_id is None:
            logger.warning("equipment_summary: '%s' not found.", equipment)
            return {"error": f"Equipment '{equipment}' not found in graph."}

        failures  = self.get_failures(node_id)
        people    = self.get_people(node_id)
        standards = self.get_standards(node_id)
        events    = self.get_events(node_id)
        actions   = self.get_actions(node_id)
        refs      = self.get_references(node_id)
        related   = self.get_related_equipment(node_id)
        fc        = self.get_failure_chain(node_id)

        # CHANGED: top_failures is sorted by occurrence_count (already sorted
        # by get_failures), formatted for human / LLM readability.
        top_failures = [
            {
                "name":             f["label"],
                "occurrence_count": f["occurrence_count"],
                "event_ids":        f.get("event_ids", []),
                "grounded":         f.get("grounded", True),
            }
            for f in failures
        ]

        # CHANGED: people formatted with merged roles list
        people_formatted = [
            {
                "name":             p["label"],
                "roles":            p["roles"],
                "occurrence_count": p["occurrence_count"],
            }
            for p in people
        ]

        return {
            "equipment_id": node_id,
            "attributes":   self._get_node_attrs(node_id),

            # CHANGED: unique counts section
            "counts": {
                "failures":   len(failures),
                "people":     len(people),
                "events":     len(events),
                "actions":    len(actions),
                "references": len(refs),
                "standards":  len(standards),
            },

            # CHANGED: sorted by occurrence_count
            "top_failures": top_failures,

            # CHANGED: merged roles per person
            "people":    people_formatted,

            "standards": [s["label"] for s in standards],
            "events": [
                {
                    "event_id": e["event_id"],
                    "date":     e.get("date"),
                    "severity": e.get("severity"),
                    "status":   e.get("status"),
                }
                for e in events
            ],
            "corrective_actions": [a["label"] for a in actions],
            "references": [
                {
                    "file_name": r.get("file_name"),
                    "doc_type":  r.get("doc_type"),
                }
                for r in refs
            ],
            "related_equipment": [
                {
                    "equipment_id": r["node_id"],
                    "relation":     r["relation"],
                    "direction":    r["direction"],
                }
                for r in related
            ],
            "failure_chains": fc.get("failure_chains", []),
        }

    def get_context(
        self,
        entity: str,
        *,
        depth: int          = 1,
        grounded_only: bool = False,
        include_attrs: bool = True,
    ) -> dict[str, Any]:
        """
        Return structured JSON context for *entity* for LLM injection.

        CHANGED: outgoing/incoming records now include source_docs (list),
        event_ids (list), and occurrence_count instead of the old scalar fields.
        """
        node_id = self.resolve_node(entity)
        if node_id is None:
            logger.warning("get_context: '%s' not found.", entity)
            return {
                "entity":    entity,
                "node_id":   None,
                "node_type": None,
                "error":     f"Entity '{entity}' not found in graph.",
                "outgoing":  [],
                "incoming":  [],
            }

        label = self._node_label(node_id)
        ntype = self._get_node_type(node_id)

        def _format(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                {
                    "relation":         r["relation"],
                    "target":           r["label"],
                    "target_node_id":   r["node_id"],
                    "target_type":      r["node_type"],
                    # CHANGED: lists instead of scalars
                    "source_docs":      r.get("source_docs", []),
                    "event_ids":        r.get("event_ids", []),
                    "grounded":         r.get("grounded", True),
                    "occurrence_count": r.get("occurrence_count", 1),
                    "depth":            r.get("depth", 1),
                }
                for r in records
            ]

        outgoing = self.neighbors(
            node_id, direction="out", depth=depth, grounded_only=grounded_only,
        )
        incoming = self.neighbors(
            node_id, direction="in",  depth=depth, grounded_only=grounded_only,
        )

        result: dict[str, Any] = {
            "entity":    label,
            "node_id":   node_id,
            "node_type": ntype,
            "outgoing":  _format(outgoing),
            "incoming":  _format(incoming),
        }

        if include_attrs:
            result["attributes"] = self._get_node_attrs(node_id)

        return result

    # ------------------------------------------------------------------ #
    # 10. STATISTICS                                                        #
    # ------------------------------------------------------------------ #

    def graph_statistics(self) -> dict[str, Any]:
        """Comprehensive statistics report for the entire graph."""
        G = self._G

        grounded = sum(
            1 for _, _, data in G.edges(data=True)
            if data.get("grounded", True)
        )

        isolated_count = sum(1 for _ in nx.isolates(G))

        degree_seq = sorted(
            (
                (node, G.in_degree(node) + G.out_degree(node))
                for node in G.nodes
            ),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        top_nodes = [
            {
                "node_id":   nid,
                "label":     self._node_label(nid),
                "node_type": self._get_node_type(nid),
                "degree":    deg,
            }
            for nid, deg in degree_seq
        ]

        return {
            "node_count":              G.number_of_nodes(),
            "edge_count":              G.number_of_edges(),
            "node_type_counts":        self._node_type_counts,
            "relation_counts":         self._relation_counts,
            "grounded_edge_count":     grounded,
            "ungrounded_edge_count":   G.number_of_edges() - grounded,
            "isolated_node_count":     isolated_count,
            "top_connected_nodes":     top_nodes,
        }

    def count_by_node_type(self) -> dict[str, int]:
        """Pre-computed node-type counts. O(1)."""
        return dict(self._node_type_counts)

    def count_by_relation(self) -> dict[str, int]:
        """Pre-computed edge-relation counts. O(1)."""
        return dict(self._relation_counts)

    def count_ungrounded(self) -> dict[str, int]:
        """Count ungrounded edges by relation. Computed on demand."""
        counts: Counter[str] = Counter()
        for _, _, data in self._G.edges(data=True):
            if not data.get("grounded", True):
                rel = self._edge_relation(data) or "unknown"
                counts[rel] += 1
        return dict(counts.most_common())

    def _compute_node_type_counts(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for _, data in self._G.nodes(data=True):
            counts[data.get("node_type", "Unknown")] += 1
        return dict(counts.most_common())

    def _compute_relation_counts(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for _, _, data in self._G.edges(data=True):
            counts[self._edge_relation(data) or "unknown"] += 1
        return dict(counts.most_common())
