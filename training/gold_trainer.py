# training/gold_trainer.py
# ------------------------------------------------------------
# Learns from:
#  - data/extended_proposals.jsonl (produced by gold_tester)
#  - training/gold_tests.json (your 284 cases)
# Updates:
#  - data/extended_schema.json        (new/unknown tests + metadata)
#  - data/alias_maps.json             (merges aliases found)
#  - data/signals_catalog.json        (evidence counts per genus/test/value)

import os, json, hashlib
from collections import defaultdict, Counter
from typing import Dict, List, Tuple

DATA_DIR = "data"
GOLD_PATH = os.path.join("training", "gold_tests.json")
PROPOSALS_PATH = os.path.join(DATA_DIR, "extended_proposals.jsonl")
EXT_SCHEMA_PATH = os.path.join(DATA_DIR, "extended_schema.json")
ALIAS_MAPS_PATH = os.path.join(DATA_DIR, "alias_maps.json")
SIGNALS_PATH = os.path.join(DATA_DIR, "signals_catalog.json")

# -----------------------
# IO utils
# -----------------------
def _read_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return default

def _write_json(path: str, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def _iter_jsonl(path: str):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue

# -----------------------
# Normalization helpers
# -----------------------
def canon_field_name(name: str, field_aliases: Dict[str, str]) -> str:
    if name is None:
        return ""
    n = name.strip()
    # exact alias map (case-insensitive)
    for k, v in field_aliases.items():
        if n.lower() == k.lower():
            return v
    return n

def canon_value_pnv(val: str, value_aliases: Dict[str, str]) -> str:
    if val is None:
        return "Unknown"
    v = str(val).strip()
    low = v.lower()
    for k, mapped in value_aliases.items():
        if low == k:
            return mapped
    # normalize to title-case Positive/Negative/Variable if already spelled fully
    if low in ("positive", "negative", "variable"):
        return v.capitalize()
    return v

def is_core_schema(field: str) -> bool:
    # The core schema fields are in engine/schema.py; we assume the trainer only handles fields NOT in core.
    # To avoid importing engine.schema here (keeps trainer decoupled), we hard-exclude obvious core signals by name prefix.
    CORE_FIELDS_HINT = [
        "Genus","Species","Gram Stain","Shape","Colony Morphology","Haemolysis","Haemolysis Type","Motility","Capsule",
        "Spore Formation","Growth Temperature","Oxygen Requirement","Media Grown On","Catalase","Oxidase","Coagulase",
        "DNase","Urease","Citrate","Methyl Red","VP","H2S","ONPG","Nitrate Reduction","Lipase Test","NaCl Tolerant (>=6%)",
        "Lysine Decarboxylase","Ornitihine Decarboxylase","Arginine dihydrolase","Gelatin Hydrolysis","Esculin Hydrolysis",
        "Glucose Fermentation","Lactose Fermentation","Sucrose Fermentation","Mannitol Fermentation","Sorbitol Fermentation",
        "Maltose Fermentation","Xylose Fermentation","Rhamnose Fermentation","Arabinose Fermentation","Raffinose Fermentation",
        "Trehalose Fermentation","Inositol Fermentation","Extra Notes"
    ]
    return field in CORE_FIELDS_HINT

def stable_hash(*parts: str) -> str:
    m = hashlib.sha256()
    for p in parts:
        m.update(p.encode("utf-8"))
        m.update(b"\x00")
    return m.hexdigest()[:16]

# -----------------------
# Main training routine
# -----------------------
def train_from_gold() -> Dict:
    ext_schema = _read_json(EXT_SCHEMA_PATH, {})
    alias_maps = _read_json(ALIAS_MAPS_PATH, {"field_aliases":{}, "media_aliases":{}, "value_aliases_pnv":{}})
    signals = _read_json(SIGNALS_PATH, {})

    field_aliases = alias_maps.get("field_aliases", {})
    value_aliases = alias_maps.get("value_aliases_pnv", {})

    # 1) Scan proposals to discover new fields and values
    new_fields = set()
    proposals_consumed = 0
    for rec in _iter_jsonl(PROPOSALS_PATH):
        proposals_consumed += 1
        rtype = rec.get("type","")
        field = rec.get("field","")
        if not field:
            continue
        canon = canon_field_name(field, field_aliases)

        # A) expected fields not in schema → extended schema candidates
        if rtype in ("expected_field_not_in_schema","unknown_field"):
            if not is_core_schema(canon):
                if canon not in ext_schema:
                    # default type is enum_PNV; can be changed later via UI
                    ext_schema[canon] = {
                        "value_type": "enum_PNV",
                        "status": "experimental",
                        "aliases": list({field} - {canon})
                    }
                else:
                    # add alias if different spelling observed
                    if field != canon and field not in ext_schema[canon].get("aliases",[]):
                        ext_schema[canon].setdefault("aliases", []).append(field)
                new_fields.add(canon)

        # B) unknown enum values for core fields are not handled here (core owned by schema.py)

    # 2) Aggregate evidence for extended fields from gold_tests "expected"
    tests = _read_json(GOLD_PATH, [])
    # signals structure: { Genus: { TestName: { "Positive": n, "Negative": n, "Variable": n, "_n": total } } }
    for case in tests:
        name = case.get("name","")
        genus = name.split()[0] if name else ""
        expected = case.get("expected",{})
        for k, v in expected.items():
            canon_k = canon_field_name(k, field_aliases)
            if is_core_schema(canon_k):
                continue
            # ensure test exists in extended schema at least tentatively
            if canon_k not in ext_schema:
                ext_schema[canon_k] = {"value_type": "enum_PNV", "status": "experimental", "aliases": [k] if k!=canon_k else []}
            vcanon = canon_value_pnv(v, value_aliases)
            signals.setdefault(genus, {}).setdefault(canon_k, {"Positive":0,"Negative":0,"Variable":0,"_n":0})
            if vcanon in ("Positive","Negative","Variable"):
                signals[genus][canon_k][vcanon] += 1
                signals[genus][canon_k]["_n"] += 1

    # 3) Write back updated files
    _write_json(EXT_SCHEMA_PATH, ext_schema)
    alias_maps["field_aliases"] = field_aliases
    alias_maps["value_aliases_pnv"] = value_aliases
    _write_json(ALIAS_MAPS_PATH, alias_maps)
    _write_json(SIGNALS_PATH, signals)

    return {
        "updated_fields": sorted(list(new_fields)),
        "extended_schema_path": EXT_SCHEMA_PATH,
        "signals_path": SIGNALS_PATH,
        "alias_maps_path": ALIAS_MAPS_PATH,
        "proposals_scanned": proposals_consumed
    }
