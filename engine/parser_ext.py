# engine/parser_ext.py
# ------------------------------------------------------------
# Data-driven parser for extended tests (not in core schema).
# Uses:
#   - data/extended_schema.json
#   - data/alias_maps.json
#
# Automatically extracts extended tests such as:
#   CAMP, PYR, Optochin, Novobiocin, Bacitracin, Bile Solubility, Hippurate, etc.
#
# Core tests (Gram, Catalase, DNase, Indole, etc.) are EXCLUDED.

import json
import os
import re
from typing import Dict, List

DATA_DIR = "data"
EXT_SCHEMA_PATH = os.path.join(DATA_DIR, "extended_schema.json")
ALIAS_MAPS_PATH = os.path.join(DATA_DIR, "alias_maps.json")

# -------------------------------------------------------------------------
# Hardcoded core test fields (NEVER to be parsed as extended)
# -------------------------------------------------------------------------
CORE_FIELDS = {
    "Genus", "Species",
    "Gram Stain", "Shape", "Colony Morphology", "Haemolysis", "Haemolysis Type",
    "Motility", "Capsule", "Spore Formation", "Growth Temperature", "Oxygen Requirement",
    "Media Grown On",
    "Catalase", "Oxidase", "Coagulase", "DNase", "Urease", "Citrate", "Methyl Red", "VP",
    "H2S", "ONPG", "Nitrate Reduction", "Lipase Test", "NaCl Tolerant (>=6%)",
    "Lysine Decarboxylase", "Ornitihine Decarboxylase", "Arginine dihydrolase",
    "Gelatin Hydrolysis", "Esculin Hydrolysis",
    "Glucose Fermentation", "Lactose Fermentation", "Sucrose Fermentation",
    "Mannitol Fermentation", "Sorbitol Fermentation", "Maltose Fermentation",
    "Xylose Fermentation", "Rhamnose Fermentation", "Arabinose Fermentation",
    "Raffinose Fermentation", "Trehalose Fermentation", "Inositol Fermentation"
}

# -------------------------------------------------------------------------
# Positive / Negative / Variable mapping
# -------------------------------------------------------------------------
PNV_MAP = {
    "+": "Positive", "positive": "Positive", "pos": "Positive",
    "-": "Negative", "negative": "Negative", "neg": "Negative",
    "variable": "Variable", "var": "Variable"
}

# -------------------------------------------------------------------------
# Sensitivity/Resistance mapping for disk diffusion tests
# (e.g., optochin, novobiocin, bacitracin)
# -------------------------------------------------------------------------
SENS_MAP = {
    "sensitive": "Positive",
    "susceptible": "Positive",
    "resistant": "Negative",
    "insensitive": "Negative"
}

# -------------------------------------------------------------------------
# JSON loaders
# -------------------------------------------------------------------------
def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

# -------------------------------------------------------------------------
# Canonical value mapping (+, -, variable, resistant, sensitive)
# -------------------------------------------------------------------------
def _canon_value(token: str) -> str:
    if token is None:
        return "Unknown"
    low = token.strip().lower()
    if low in PNV_MAP:
        return PNV_MAP[low]
    if low in SENS_MAP:
        return SENS_MAP[low]
    return token.strip()

# -------------------------------------------------------------------------
# Gather all alias names for a field
# -------------------------------------------------------------------------
def _aliases_for(field: str, field_aliases: Dict[str, str]) -> List[str]:
    """
    Returns all known aliases for this test, including the canonical name.
    Ordered longest→shortest to avoid partial matches.
    """
    aliases = {field}
    for k, v in field_aliases.items():
        if v.lower() == field.lower():
            aliases.add(k)
    return sorted(aliases, key=len, reverse=True)

# -------------------------------------------------------------------------
# Main Extended Parser
# -------------------------------------------------------------------------
def parse_text_extended(text: str) -> Dict[str, Dict]:
    """
    Parse ONLY tests listed in extended_schema.json.
    Excludes all core tests completely.
    Returns:
      {
        "parsed_fields": { TestName: "Positive"/"Negative"/"Variable" },
        "source": "extended_parser"
      }
    """
    ext_schema = _load_json(EXT_SCHEMA_PATH, {})
    alias_maps = _load_json(ALIAS_MAPS_PATH, {"field_aliases": {}, "value_aliases_pnv": {}})
    field_aliases = alias_maps.get("field_aliases", {})

    t = text or ""
    out: Dict[str, str] = {}

    # LOOP: For each extended test, search text for aliases + P/N/V patterns
    for canon_field in ext_schema.keys():

        # Safety: never allow extended parser to treat core tests as extended
        if canon_field in CORE_FIELDS:
            continue

        aliases = _aliases_for(canon_field, field_aliases)

        for alias in aliases:
            # Match: <alias> .... (positive|negative|variable|+|-|sensitive|resistant)
            regex = (
                rf"\b{re.escape(alias)}\b"
                r"[^.\n]{0,80}?"  # lookahead window
                r"\b(positive|negative|variable|\+|\-|susceptible|sensitive|resistant)\b"
            )

            m = re.search(regex, t, re.IGNORECASE)
            if m:
                out[canon_field] = _canon_value(m.group(1))
                break  # found best match for this field

    # Final cleanup: remove any forbidden core fields that slipped through
    dirty = [k for k in out.keys() if k in CORE_FIELDS]
    for d in dirty:
        del out[d]

    return {
        "parsed_fields": out,
        "source": "extended_parser"
    }
