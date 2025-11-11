# engine/schema.py
from typing import Dict, List, Any, Tuple

POS_NEG_VAR = ["Positive", "Negative", "Variable"]
POS_NEG_VAR_UNKNOWN = ["Positive", "Negative", "Variable", "Unknown"]
UNKNOWN = "Unknown"
MULTI_SEPARATOR = ";"

ENUMS = {
    "Gram Stain": ["Positive", "Negative", "Variable"],
    "Shape": ["Cocci", "Rods", "Bacilli", "Spiral", "Short Rods"],
    "Haemolysis Type": ["None", "Beta", "Gamma", "Alpha"],
}

SCHEMA: Dict[str, Dict[str, Any]] = {
    "Genus": {"type": "text", "required": True},
    "Species": {"type": "text", "required": False},

    "Gram Stain": {"type": "enum", "allowed": ENUMS["Gram Stain"]},
    "Shape": {"type": "enum", "allowed": ENUMS["Shape"]},
    "Colony Morphology": {"type": "multienum", "separator": MULTI_SEPARATOR},
    "Haemolysis": {"type": "enum", "allowed": POS_NEG_VAR},
    "Haemolysis Type": {"type": "multienum", "separator": MULTI_SEPARATOR, "allowed": ENUMS["Haemolysis Type"]},
    "Motility": {"type": "enum", "allowed": POS_NEG_VAR},
    "Capsule": {"type": "enum", "allowed": POS_NEG_VAR},
    "Spore Formation": {"type": "enum", "allowed": POS_NEG_VAR},

    "Growth Temperature": {"type": "range", "format": "low//high", "units": "°C"},
    "Oxygen Requirement": {"type": "text"},
    "Media Grown On": {"type": "multienum", "separator": MULTI_SEPARATOR},

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

    "NaCl Tolerant (>=6%)": {"type": "enum", "allowed": POS_NEG_VAR},

    "Lysine Decarboxylase": {"type": "enum", "allowed": POS_NEG_VAR},
    "Ornitihine Decarboxylase": {"type": "enum", "allowed": POS_NEG_VAR},
    "Arginine dihydrolase": {"type": "enum", "allowed": POS_NEG_VAR},

    "Gelatin Hydrolysis": {"type": "enum", "allowed": POS_NEG_VAR},
    "Esculin Hydrolysis": {"type": "enum", "allowed": POS_NEG_VAR},

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

    "Extra Notes": {"type": "text"},
}

FIELDS_ORDER: List[str] = list(SCHEMA.keys())

MULTI_FIELDS: List[str] = [
    k for k, v in SCHEMA.items() if v.get("type") == "multienum"
]

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
    if value is None or str(value).strip() == "":
        return UNKNOWN
    v = str(value).strip()

    if v.lower() == "unknown":
        return UNKNOWN

    meta = SCHEMA.get(field, {})
    ftype = meta.get("type")

    if ftype == "enum":
        allowed = meta.get("allowed", [])
        for a in allowed:
            if v.lower() == a.lower():
                return a
        if v.lower() in ["+", "positive", "pos"]:
            return "Positive" if "Positive" in allowed else v
        if v.lower() in ["-", "negative", "neg"]:
            return "Negative" if "Negative" in allowed else v
        if v.lower() in ["variable", "var", "v"]:
            return "Variable" if "Variable" in allowed else v
        return v

    if ftype == "multienum":
        parts = [p.strip() for p in v.split(MULTI_SEPARATOR) if p.strip()]
        allowed = meta.get("allowed")
        normed = []
        for p in parts:
            if not allowed:
                normed.append(p)
            else:
                hit = next((a for a in allowed if a.lower() == p.lower()), None)
                normed.append(hit if hit else p)
        return f" {MULTI_SEPARATOR} ".join(normed) if normed else UNKNOWN

    if ftype == "range":
        txt = v.replace(" ", "")
        return txt

    return v

def validate_record(rec: Dict[str, Any]) -> Tuple[bool, List[str]]:
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
            allowed = meta.get("allowed")
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

    ok = len(issues) == 0
    return ok, issues

def empty_record() -> Dict[str, str]:
    rec = {}
    for f, meta in SCHEMA.items():
        if f in ("Genus", "Species"):
            rec[f] = ""
        else:
            rec[f] = UNKNOWN
    return rec
