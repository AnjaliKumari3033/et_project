"""
NovaChem Knowledge Graph - Entity Extraction (Team B / Person 1)
=================================================================
Reads documents.jsonl (from read_documents.py) and calls a local Ollama
model per document to extract entities + relationships as JSON.

Run in TEST MODE first (--limit 5) to check output quality before
running on all 761 documents.

Usage:
    python extract_entities.py --input documents.jsonl --out entities.json --limit 5
    python extract_entities.py --input documents.jsonl --out entities.json   # full run

Requires: requests (pip install requests)
Requires Ollama running locally (ollama serve) with a model pulled.
"""

import argparse
import json
import re
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5-coder:latest"  # change to "qwen2.5:7b-instruct" if you switch models

ONTOLOGY = """
Entity types (use exactly these): Equipment, FailureMode, Person, Standard, MaintenanceAction
Relationship types (use exactly these): has_failure, repaired_by, follows_standard, caused_by, part_of, documented_by

Rules:
- If an Equipment ID is already given to you (e.g. "P-101"), ALWAYS use that exact ID as the
  entity name for that equipment. Never invent a different name or paraphrase (e.g. do not
  write "Feed Pump" as the entity name if "P-101" was given).
- Only extract entities and relationships that are actually stated in the document text below.
  Do not guess or invent facts that aren't there.
- IGNORE the "Linked Documents" section completely if present (it just lists related filenames
  like "WO_EVT-004.docx" - these are NOT standards, equipment, or any other entity. Never create
  an entity or relationship from a filename.)
- Only create a "follows_standard" relationship if a SPECIFIC named standard is stated in the text
  (e.g. "API 610", "ISO 9001", "OISD-105"). If the text only says something generic like "standard
  reference values" or "standard procedure" with no specific standard named, do NOT create a
  follows_standard relationship at all.
- Person entities and any relationship involving a person (repaired_by, caused_by, etc.) must be
  based ONLY on what the document body text explicitly says a person did. Do NOT assume the
  "Prepared By" or "Approved By" person performed a repair or caused an issue just because their
  name is known - those two roles are document authorship only. If you want to record that a
  person prepared or approved a document, use the "documented_by" relationship type for that,
  never "repaired_by" or "caused_by".
- "caused_by" should link a FailureMode to its root cause (e.g. "Mechanical seal leakage" caused_by
  "Seal wear"), not link Equipment directly to a root cause.
- Output ONLY valid JSON, no other text, no markdown code fences, no explanation.
"""

SCHEMA_EXAMPLE = """
{
  "entities": [
    {"type": "Equipment", "name": "P-101"},
    {"type": "FailureMode", "name": "Bearing wear"},
    {"type": "Person", "name": "Pooja Mehta"}
  ],
  "relationships": [
    {"source": "P-101", "relation": "has_failure", "target": "Bearing wear"},
    {"source": "Bearing wear", "relation": "caused_by", "target": "Lack of lubrication"},
    {"source": "P-101", "relation": "documented_by", "target": "Pooja Mehta"}
  ]
}
"""


def build_prompt(doc: dict) -> str:
    known_equipment = doc.get("Equipment ID", "")
    prepared_by = doc.get("Prepared By", "")
    approved_by = doc.get("Approved By", "")

    prompt = f"""You are extracting structured knowledge from an industrial document.

{ONTOLOGY}

Known facts already confirmed for this document (use these exact values, don't re-derive them):
- Equipment ID: {known_equipment or "not specified"}
- Document prepared by (authorship only, NOT necessarily who did any repair): {prepared_by or "not specified"}
- Document approved by (authorship only, NOT necessarily who did any repair): {approved_by or "not specified"}

Document text:
---
{doc['text']}
---

Return JSON in exactly this shape (this is a FORMAT EXAMPLE, not the real data):
{SCHEMA_EXAMPLE}

Now return the real JSON for the document above. JSON only, no other text."""
    return prompt


def extract_json(raw: str) -> dict | None:
    """Qwen sometimes wraps JSON in markdown fences or adds stray text - strip that."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # try to find the first { ... last } as a fallback
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                return None
        return None


def load_equipment_aliases(equipment_master_path: str) -> dict:
    """Build a case-insensitive {equipment_name: equipment_id} lookup from
    equipment_master.xlsx, so we can normalize 'Feed Pump' -> 'P-101' regardless
    of which form Qwen happened to output."""
    import openpyxl
    aliases = {}
    if not equipment_master_path:
        return aliases
    wb = openpyxl.load_workbook(equipment_master_path, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(h) for h in rows[0]]
    id_col = headers.index("Equipment ID")
    name_col = headers.index("Equipment Name")
    for row in rows[1:]:
        eq_id, eq_name = row[id_col], row[name_col]
        if eq_id and eq_name:
            aliases[str(eq_name).strip().lower()] = str(eq_id).strip()
    return aliases


def normalize_equipment_names(parsed: dict, aliases: dict) -> dict:
    """Rewrite any entity/relationship using an equipment name instead of its
    canonical ID, e.g. 'Feed Pump' -> 'P-101'. Prevents the same equipment
    showing up as two different graph nodes."""
    def norm(name: str) -> str:
        return aliases.get(str(name).strip().lower(), name)

    for e in parsed.get("entities", []):
        if e.get("type") == "Equipment":
            e["name"] = norm(e["name"])
    for r in parsed.get("relationships", []):
        r["source"] = norm(r["source"])
        r["target"] = norm(r["target"])
    return parsed


def check_grounding(parsed: dict, doc: dict) -> dict:
    """Flag entities/relationships whose content doesn't actually appear anywhere
    in the document - either the body text OR the table fields (Prepared By,
    Approved By, etc). Catches real hallucinations (an invented failure mode)
    without false-flagging real facts that only live in a table cell. Doesn't
    delete anything, just marks it so a human can review flagged items."""
    table_field_values = " ".join(
        str(doc[k]) for k in
        ("Prepared By", "Approved By", "Document Number", "Chain ID")
        if doc.get(k)
    )
    text_lower = (doc.get("text", "") + " " + table_field_values).lower()

    def is_grounded(name: str) -> bool:
        return str(name).strip().lower() in text_lower

    for e in parsed.get("entities", []):
        if e.get("type") == "Equipment":
            e["grounded"] = True  # equipment IDs come from trusted metadata, not text search
        else:
            e["grounded"] = is_grounded(e["name"])

    grounded_lookup = {e["name"]: e.get("grounded", False) for e in parsed.get("entities", [])}
    for r in parsed.get("relationships", []):
        r["grounded"] = grounded_lookup.get(r["source"], False) and grounded_lookup.get(r["target"], False)

    return parsed


def call_ollama(prompt: str) -> str:
    resp = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
    }, timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="documents.jsonl")
    parser.add_argument("--out", default="entities.json")
    parser.add_argument("--limit", type=int, default=None, help="Only process first N docs (for testing)")
    parser.add_argument("--equipment_master", default=None,
                         help="Path to equipment_master.xlsx, used to normalize equipment names to canonical IDs")
    parser.add_argument("--include_public", action="store_true",
                         help="Also extract from public_industrial_knowledge docs (SDS/manuals/regulations). "
                              "Off by default - that content doesn't fit this ontology and belongs in RAG instead.")
    args = parser.parse_args()

    aliases = load_equipment_aliases(args.equipment_master) if args.equipment_master else {}
    if aliases:
        print(f"Loaded {len(aliases)} equipment name aliases for normalization")

    docs = []
    with open(args.input, encoding="utf-8") as f:
        for line in f:
            docs.append(json.loads(line))

    if not args.include_public:
        before = len(docs)
        docs = [d for d in docs if d.get("layer") != "public_industrial_knowledge"]
        print(f"Skipping public_industrial_knowledge docs: {before} -> {len(docs)} documents "
              f"(pass --include_public to include them)")

    if args.limit:
        docs = docs[:args.limit]

    results = []
    flagged_count = 0
    for i, doc in enumerate(docs):
        print(f"[{i+1}/{len(docs)}] extracting from {doc['file_name']} ({doc['doc_type']})...")
        prompt = build_prompt(doc)
        try:
            raw = call_ollama(prompt)
            parsed = extract_json(raw)
            if parsed is None:
                print(f"  [WARN] could not parse JSON, raw output was: {raw[:200]}")
                continue

            if aliases:
                parsed = normalize_equipment_names(parsed, aliases)
            parsed = check_grounding(parsed, doc)

            n_flagged = sum(1 for e in parsed.get("entities", []) if not e.get("grounded", True))
            if n_flagged:
                flagged_count += n_flagged
                print(f"  [FLAG] {n_flagged} entity(ies) not found in source text - review before trusting")

            results.append({
                "file_path": doc["file_path"],
                "event_id": doc.get("event_id"),
                "doc_type": doc.get("doc_type"),
                "entities": parsed.get("entities", []),
                "relationships": parsed.get("relationships", []),
            })
        except Exception as e:
            print(f"  [ERROR] {e}")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {len(results)}/{len(docs)} documents extracted -> {args.out}")
    if flagged_count:
        print(f"NOTE: {flagged_count} entities were flagged as 'grounded: false' (not found in source text) - review these before trusting them.")


if __name__ == "__main__":
    main()