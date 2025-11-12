# engine/parser_ext.py
# ------------------------------------------------------------
# Data-driven parser for extended tests (not in core schema).
# Uses data/extended_schema.json and data/alias_maps.json.

import json, os, re
from typing import Dict, List

DATA_DIR = "data"
EXT_SCHEMA_PATH = os.path.join(DATA_DIR, "extended_schema.json")
ALIAS_MAPS_PATH = os.path.join(DATA_DIR, "alias_maps.json")

PNV_MAP = {
    "+": "Positive", "positive": "Positive", "pos": "Positive",
    "-": "Negative", "negative": "Negative", "neg": "Negative",
    "variable": "Variable", "var": "Variable"
}

# Sensitivity lexicon for disk tests
SENS_MAP = {
    "sensitive": "Positive", "susceptible": "Positive",
    "resistant": "Negative", "insensitive": "Negative"
}

def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return default

def _canon_value(token: str) -> str:
    t = token.strip().lower()
    if t in PNV_MAP:
        return PNV_MAP[t]
    if t in SENS_MAP:
        return SENS_MAP[t]
    return token.strip()

def _aliases_for(field: str, field_aliases: Dict[str, str]) -> List[str]:
    # include canonical and any keys that map to it
    vals = {field}
    for k, v in field_aliases.items():
        if v.lower() == field.lower():
            vals.add(k)
    return sorted(vals, key=len, reverse=True)

def parse_text_extended(text: str) -> Dict[str, str]:
    """
    Returns {"parsed_fields": {...}, "source": "extended_parser"}
    Only returns tests that exist in extended_schema.json (status any).
    """
    ext_schema = _load_json(EXT_SCHEMA_PATH, {})
    alias_maps = _load_json(ALIAS_MAPS_PATH, {"field_aliases": {}, "value_aliases_pnv": {}})
    field_aliases = alias_maps.get("field_aliases", {})
    t = text or ""
    out: Dict[str, str] = {}

    # generic patterns:
    #   "<test> ... positive/negative/variable/+/−"
    #   "<test> ... sensitive/susceptible/resistant" (maps to P/N)
    # Keep a modest window to catch "test is positive" etc.
    for canon_field in ext_schema.keys():
        for alias in _aliases_for(canon_field, field_aliases):
            # strict word boundary around alias
            pattern = rf"\b{re.escape(alias)}\b[^.\n]{{0,80}}?\b(positive|negative|variable|\+|\-|susceptible|sensitive|resistant)\b"
            m = re.search(pattern, t, re.IGNORECASE)
            if m:
                val = _canon_value(m.group(1))
                out[canon_field] = val
                break  # stop at first match per field

    return {"parsed_fields": out, "source": "extended_parser"}
