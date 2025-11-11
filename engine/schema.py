# engine/schema.py
# BactAI-D canonical schema and helpers
# ------------------------------------------------------------

from typing import Dict, List, Any, Tuple

# Global label conventions
POS_NEG_VAR = ["Positive", "Negative", "Variable"]
POS_NEG_VAR_UNKNOWN = ["Positive", "Negative", "Variable", "Unknown"]
UNKNOWN = "Unknown"

# Multi-value fields use semicolon separators in UI/data
MULTI_SEPARATOR = ";"

# Enumerations
ENUMS = {
    "Gram Stain": ["Positive", "Negative", "Variable"],
    "Shape": ["Cocci", "Rods", "Bacilli", "Spiral", "Short Rods"],
    "Haemolysis Type": ["None", "Beta", "Gamma", "Alpha"],
    # Most test results use Positive/Negative/Variable; "Unknown" is allowed at input time
}

# Core schema (order preserved)
# type: "enum" | "multienum" | "text" | "range" (range uses "low//high" °C)
SCHEMA: Dict[str, Dict[str, Any]] = {
    # Identifiers
    "Genus": {"type": "text", "required": True},
    "Species": {"type": "text", "required": False},

    # Morphology & basic traits
    "Gram Stain": {"type": "enum", "allowed": ENUMS["Gram Stain"]},
    "Shape": {"type": "enum", "allowed": ENUMS["Shape"]},
    "Colony Morphology": {"type": "multienum", "separator": MULTI_SEPARATOR},
    "Haemolysis": {"type": "enum", "allowed": POS_NEG_VAR},
    "Haemolysis Type": {"type": "multienum", "separator": MULTI_SEPARATOR, "allowed": ENUMS["Haemolysis Type"]},
    "Motility": {"type": "enum", "allowed": POS_NEG_VAR},
    "Capsule": {"type": "enum", "allowed": POS_NEG_VAR},
    "Spore Formation": {"type": "enum", "allowed": POS_NEG_VAR},

    # Physiology / growth
    "Growth Temperature": {"type": "range", "format": "low//high", "units": "°C"},
    "Oxygen Requirement": {"type": "text"},  # free text labels like Aerobic, Facultative Anaerobe, Microaerophilic
    "Media Grown On": {"type": "multienum", "separator": MULTI_SEPARATOR},  # normalize to Capitalized + "Agar"

    # Enzymes & core biochem
    "Catalase": {"type": "enum", "allowed": POS_NEG_VAR},
    "Oxidase": {"type": "enum", "allowed": POS_NEG_VAR},
    "Indole": {"type": "enum", "allowed": POS_NEG_VAR},
    "Urease": {"type": "enum", "allowed": POS_NEG_VAR},
    "Citrate": {"type": "enum", "allowed": POS_NEG_VAR},
    "Methyl Red": {"type": "enum", "allowed": POS_NEG_VAR},
    "VP": {"type": "enum", "allowed": POS_NEG_VAR},
    "H2S": {"type": "enum", "allowed": POS_NEG_VAR},
    "DNase": {"type": "enum", "allowed": POS_NEG_VAR},
    "ONPG": {"type": "enum", "allowed": POS_NEG_VAR},
    "Coagulase": {"type": "enum", "allowed": POS_NEG_VAR},
    "Lipase Test": {"type": "enum", "allowed": POS_NEG_VAR},
    "Nitrate Reduction": {"type": "enum", "allowed": POS_NEG_VAR},

    # Salt tolerance (explicit ≥6% rule)
    "NaCl Tolerant (>=6%)": {"type": "enum", "allowed": POS_NEG_VAR},

    # Amino acid decarboxylases / dihydrolase
    "Lysine Decarboxylase": {"type": "enum", "allowed": POS_NEG_VAR},
    "Ornitihine Decarboxylase": {"type": "enum", "allowed": POS_NEG_VAR},
    "Arginine dihydrolase": {"type": "enum", "allowed": POS_NEG_VAR},

    # Hydrolyses
    "Gelatin Hydrolysis": {"type": "enum", "allowed": POS_NEG_VAR},
    "Esculin Hydrolysis": {"type": "enum", "allowed": POS_NEG_VAR},

    # Fermentations (carbohydrates)
    "Glucose Fermentation": {"type": "enum", "allowed": POS_NEG_VAR},
    "Lactose Fermentation": {"type": "enum", "allowed": POS_NEG_VAR},
    "Sucrose Fermentation": {"type": "enum", "allowed": POS_NEG_VAR},
    "Mannitol Fermentation": {"type": "enum", "allowed": POS_NEG_VAR},
    "Sorbitol Fermentation": {"type": "enum", "allowed": POS_NEG_VAR},
    "Maltose Fermentation": {"type": "enum", "allowed": POS_NEG_VAR},
    "Xylose Fermentation": {"type": "enum", "allowed": POS_NEG_VAR},
    "Rhamnose Fermentation": {"type": "enum", "allowed": POS_NEG_VAR},
    "Arabinose Fermentation": {"type": "enum", "allowed": POS_NEG_VAR},
    "Raffinose Fermentation": {"type": "enum", "allowed": POS_NEG_VAR},
    "Trehalose Fermentation": {"type": "enum", "allowed": POS_NEG_VAR},
    "Inositol Fermentation": {"type": "enum", "allowed": POS_NEG_VAR},

    # Notes
    "Extra Notes": {"type": "text"},
}

# Lists useful to the app/engine
FIELDS_ORDER: List[str] = list(SCHEMA.keys())

# Which fields accept multiple values (semicolon-separated)
MULTI_FIELDS: List[str] = [
    k for k, v in SCHEMA.items() if v.get("type") == "multienum"
]

# Which fields are simple enum Positive/Negative/Variable
PNV_FIELDS: List[str] = [
    k for k, v in SCHEMA.items()
    if v.get("type") == "enum" and v.get("allowed") == POS_NEG_VAR
]

def is_enum_field(field: str) -> bool:
    return SCHEMA.get(field, {}).get("type") == "enum"

def is_multienum_field(field: str) -> bool:
    return SCHEMA.get(field, {}).get("type") == "multienum"

def is_range_field(field: str) -> bool:
    return SCHEMA.get(field, {}).get("type") == "range"

def normalize_value(field: str, value: str) -> str:
    """Standardize capitalization and enforce allowed enum labels. Unknown passes through as 'Unknown'."""
    if value is None or str(value).strip() == "":
        return UNKNOWN
    v = str(value).strip()

    # Allow Unknown globally
    if v.lower() == "unknown":
        return UNKNOWN

    meta = SCHEMA.get(field, {})
    ftype = meta.get("type")

    if ftype == "enum":
        allowed = meta.get("allowed", [])
        # Case-insensitive match to allowed labels
        for a in allowed:
            if v.lower() == a.lower():
                return a
        # If it's one of the generic result labels, map sensibly
        if v.lower() in ["+", "positive", "pos"]:
            return "Positive" if "Positive" in allowed else v
        if v.lower() in ["-", "negative", "neg"]:
            return "Negative" if "Negative" in allowed else v
        if v.lower() in ["variable", "var", "v"]:
            return "Variable" if "Variable" in allowed else v
        # Fallback: return as-is (validator may flag)
        return v

    if ftype == "multienum":
        parts = [p.strip() for p in v.split(MULTI_SEPARATOR) if p.strip()]
        # Normalize known allowed labels; keep free text for open sets
        allowed = meta.get("allowed")  # may be None (open set like Media/Colony)
        normed = []
        for p in parts:
            if not allowed:
                normed.append(p)
            else:
                # case-insensitive mapping for allowed lists
                hit = next((a for a in allowed if a.lower() == p.lower()), None)
                normed.append(hit if hit else p)
        return f" {MULTI_SEPARATOR} ".join(normed) if normed else UNKNOWN

    if ftype == "range":
        # Expect "low//high" floats; tolerate spaces
        txt = v.replace(" ", "")
        return txt  # detailed validation in validate_record

    # text fields: return trimmed with canonical casing for Agar names later in parser
    return v

def validate_record(rec: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate a record against the schema.
    Returns (ok, issues). Unknown is allowed; strict enum mismatches are flagged.
    """
    issues: List[str] = []
    for field in FIELDS_ORDER:
        meta = SCHEMA[field]
        if field not in rec:
            continue
        val = rec[field]

        if meta["type"] == "enum":
            allowed = meta.get("allowed", [])
            if str(val) not in allowed + [UNKNOWN]:
                issues.append(f"{field}: '{val}' not in {allowed + [UNKNOWN]}")

        elif meta["type"] == "multienum":
            if val == UNKNOWN:
                continue
            parts = [p.strip() for p in str(val).split(MULTI_SEPARATOR) if p.strip()]
            allowed = meta.get("allowed")  # may be None (open set)
            if allowed:
                bad = [p for p in parts if p not in allowed]
                if bad:
                    issues.append(f"{field}: invalid values {bad}; allowed {allowed}")

        elif meta["type"] == "range":
            if val == UNKNOWN:
                continue
            txt = str(val).replace(" ", "")
            if "//" not in txt:
                issues.append(f"{field}: expected 'low//high' got '{val}'")
            else:
                try:
                    low, high = [float(x) for x in txt.split("//")]
                    if low > high:
                        issues.append(f"{field}: low {low} > high {high}")
                except Exception:
                    issues.append(f"{field}: non-numeric bounds '{val}'")

        # text: no strict validation here

    ok = len(issues) == 0
    return ok, issues

def empty_record() -> Dict[str, str]:
    """Default record with 'Unknown' for all non-identifier fields."""
    rec = {}
    for f, meta in SCHEMA.items():
        if f in ("Genus", "Species"):
            rec[f] = ""
        else:
            rec[f] = UNKNOWN
    return rec
