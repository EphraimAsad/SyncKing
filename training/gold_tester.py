# training/gold_tester.py
# ----------------------------------------------------
# Runs gold tests through the parser, computes metrics,
# and logs unknown fields/values to extended_proposals.jsonl.

import json, os, time, csv
from collections import defaultdict, Counter
from typing import Dict, List, Tuple
from engine.schema import SCHEMA, UNKNOWN, normalize_value, is_enum_field
from engine.parser_rules import parse_text_rules
# Later we can import LLM parser and combine results:
# from engine.parser_llm import parse_text_llm

REPORTS_DIR = "reports"
PROPOSALS_PATH = os.path.join("data", "extended_proposals.jsonl")
GOLD_PATH = os.path.join("training", "gold_tests.json")

def load_gold() -> List[Dict]:
    with open(GOLD_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def compare_records(pred: Dict[str, str], exp: Dict[str, str]) -> Tuple[int, int, Dict[str, Tuple[str, str]]]:
    """
    Returns (num_correct, num_total, per_field_errors)
    per_field_errors[field] = (pred_val, exp_val)
    """
    correct = 0
    total = 0
    errors = {}
    for field, exp_val in exp.items():
        # Only compare fields present in expected
        total += 1
        p = pred.get(field, UNKNOWN)
        if p == exp_val:
            correct += 1
        else:
            errors[field] = (p, exp_val)
    return correct, total, errors

def append_proposal(record: Dict):
    os.makedirs(os.path.dirname(PROPOSALS_PATH), exist_ok=True)
    with open(PROPOSALS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def run_gold_tests(mode: str = "rules") -> Dict:
    """
    mode: "rules" for rule parser only (default).
          "llm"   to switch to LLM parser later.
          "combo" to merge both (later).
    """
    tests = load_gold()
    ts = time.strftime("%Y%m%d_%H%M%S")

    per_field_counts = Counter()
    per_field_correct = Counter()
    per_field_coverage = Counter()  # how often a parser produced *anything* for that field
    unknown_fields: Counter = Counter()
    unknown_values: Counter = Counter()

    detailed_rows = []  # for CSV
    cases_with_misses = 0

    for case in tests:
        name = case.get("name", "")
        text = case.get("input", "")
        expected = case.get("expected", {})

        # 1) get parsed fields
        if mode == "rules":
            out = parse_text_rules(text)
        else:
            out = parse_text_rules(text)  # placeholder; later combine with LLM

        parsed = out.get("parsed_fields", {})
        # 2) normalize against schema (Unknown passes through)
        normalized_pred: Dict[str, str] = {}
        for field, val in parsed.items():
            if field not in SCHEMA:
                unknown_fields[field] += 1
                append_proposal({
                    "type": "unknown_field",
                    "field": field,
                    "value": val,
                    "case_name": name,
                    "source": "gold_tests.json",
                    "timestamp": ts
                })
                continue
            normalized_pred[field] = normalize_value(field, val)

            # If enum but value not in allowed, propose
            if is_enum_field(field):
                allowed = SCHEMA[field].get("allowed", [])
                if normalized_pred[field] not in allowed + [UNKNOWN]:
                    unknown_values[(field, normalized_pred[field])] += 1
                    append_proposal({
                        "type": "unknown_value",
                        "field": field,
                        "value": normalized_pred[field],
                        "allowed": allowed,
                        "case_name": name,
                        "source": "gold_tests.json",
                        "timestamp": ts
                    })

        # 3) coverage & accuracy vs expected
        correct, total, errors = compare_records(normalized_pred, expected)
        if errors:
            cases_with_misses += 1

        for f in expected.keys():
            per_field_counts[f] += 1
            if f in normalized_pred and normalized_pred[f] != UNKNOWN:
                per_field_coverage[f] += 1
            if f not in errors:
                per_field_correct[f] += 1

        # 4) stash row for CSV
        detailed_rows.append({
            "name": name,
            "parsed": json.dumps(normalized_pred, ensure_ascii=False),
            "expected": json.dumps(expected, ensure_ascii=False),
            "correct_fields": correct,
            "total_fields": total
        })

    # 5) aggregate metrics
    per_field_metrics = []
    for f, tot in per_field_counts.items():
        acc = per_field_correct[f] / tot if tot else 0.0
        cov = per_field_coverage[f] / tot if tot else 0.0
        per_field_metrics.append({
            "field": f,
            "accuracy": round(acc, 4),
            "coverage": round(cov, 4),
            "n": tot
        })
    per_field_metrics.sort(key=lambda x: x["field"])

    micro_acc = (sum(per_field_correct.values()) / sum(per_field_counts.values())) if per_field_counts else 0.0

    # 6) write reports
    os.makedirs(REPORTS_DIR, exist_ok=True)
    json_report_path = os.path.join(REPORTS_DIR, f"gold_report_{mode}_{ts}.json")
    csv_cases_path = os.path.join(REPORTS_DIR, f"gold_cases_{mode}_{ts}.csv")
    csv_fields_path = os.path.join(REPORTS_DIR, f"gold_fields_{mode}_{ts}.csv")

    report = {
        "mode": mode,
        "timestamp": ts,
        "num_tests": len(tests),
        "micro_accuracy": round(micro_acc, 4),
        "cases_with_misses": cases_with_misses,
        "per_field": per_field_metrics,
        "unknown_fields": dict(unknown_fields),
        "unknown_values": {f"{k[0]}::{k[1]}": v for k, v in unknown_values.items()},
        "proposals_path": PROPOSALS_PATH
    }
    with open(json_report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # per-case CSV
    with open(csv_cases_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "parsed", "expected", "correct_fields", "total_fields"])
        w.writeheader()
        for r in detailed_rows:
            w.writerow(r)

    # per-field CSV
    with open(csv_fields_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["field", "accuracy", "coverage", "n"])
        w.writeheader()
        for r in per_field_metrics:
            w.writerow(r)

    return {
        "summary": report,
        "paths": {
            "json_report": json_report_path,
            "csv_cases": csv_cases_path,
            "csv_fields": csv_fields_path
        }
    }
