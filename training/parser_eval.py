# training/parser_eval.py
# ------------------------------------------------------------
# Stage 10A: Parser evaluation (Rules, Extended, LLM, Fusion)
#
# This evaluates all gold tests using:
#   - Rule parser
#   - Extended parser
#   - LLM parser (Cloudflare)
#   - Fusion parser (extended > rules > llm)
#
# Produces:
#   - summary metrics (accuracy, coverage)
#   - per-field statistics
#   - detailed mismatch logs
#   - hallucinated-field logs
#   - improvement suggestions for alias maps / schema
#
# ------------------------------------------------------------

import json
import os
from statistics import mean, median
from typing import Dict, Any
from datetime import datetime

from engine.parser_rules import parse_text_rules
from engine.parser_ext import parse_text_extended, CORE_FIELDS
from engine.parser_llm import parse_text_llm
from engine.parser_fusion import parse_text_fused

GOLD_PATH = "training/gold_tests.json"   # you already have this file
REPORT_DIR = "data/reports"


def _safe(val: str):
    """Normalize for comparison."""
    if val is None:
        return "Unknown"
    val = str(val).strip()
    if not val:
        return "Unknown"
    # normalize case
    v = val.lower()
    if v in ["pos", "positive", "+"]:
        return "Positive"
    if v in ["neg", "negative", "-"]:
        return "Negative"
    if v in ["variable", "var"]:
        return "Variable"
    return val


def compare_expected_to_parsed(expected: Dict[str, str], parsed: Dict[str, str]):
    """Compute accuracy for a single test case."""
    correct = 0
    wrong = 0
    missing = 0
    hallucinated = []

    for field, exp_val in expected.items():
        exp_val_norm = _safe(exp_val)
        parsed_val = _safe(parsed.get(field, "Unknown"))

        if exp_val_norm == parsed_val:
            correct += 1
        else:
            wrong += 1

    # detect hallucinated fields: parsed fields NOT part of expected
    for field in parsed.keys():
        if field not in expected:
            hallucinated.append((field, parsed[field]))

    total = max(1, len(expected))
    accuracy = correct / total

    return {
        "correct": correct,
        "wrong": wrong,
        "missing": missing,
        "accuracy": accuracy,
        "hallucinated": hallucinated,
        "total": total,
    }


def run_parser_eval() -> Dict[str, Any]:
    """Run full parser evaluation on all gold tests."""

    os.makedirs(REPORT_DIR, exist_ok=True)

    with open(GOLD_PATH, "r", encoding="utf-8") as f:
        gold_tests = json.load(f)

    results_summary = {
        "rule_accuracy": [],
        "extended_accuracy": [],
        "llm_accuracy": [],
        "fusion_accuracy": [],
        "rule_failures": 0,
        "extended_failures": 0,
        "llm_failures": 0,
        "fusion_failures": 0,
        "hallucinated_fields": {},
        "per_field_stats": {},
        "timestamp": datetime.now().isoformat(),
        "n_tests": len(gold_tests),
        "paths": {},
    }

    detailed_log_path = os.path.join(REPORT_DIR, "parser_eval_detailed.jsonl")
    llm_error_path = os.path.join(REPORT_DIR, "parser_llm_errors.jsonl")

    with open(detailed_log_path, "w", encoding="utf-8") as detailed_log, \
         open(llm_error_path, "w", encoding="utf-8") as llm_errlog:

        for test in gold_tests:
            text = test.get("input", "")
            expected = test.get("expected", {})
            name = test.get("name", "Unnamed")

            # --- Rule parser ---
            rule_out = parse_text_rules(text)
            rule_fields = rule_out.get("parsed_fields", {})
            rule_eval = compare_expected_to_parsed(expected, rule_fields)

            # --- Extended parser ---
            ext_out = parse_text_extended(text)
            ext_fields = ext_out.get("parsed_fields", {})
            ext_eval = compare_expected_to_parsed(expected, ext_fields)

            # --- LLM parser ---
            llm_out = parse_text_llm(text)
            if "error" in llm_out:
                llm_eval = {
                    "correct": 0,
                    "wrong": len(expected),
                    "missing": 0,
                    "total": len(expected),
                    "accuracy": 0.0,
                    "hallucinated": [],
                }
                llm_errlog.write(json.dumps({
                    "name": name,
                    "input": text,
                    "error": llm_out.get("error"),
                    "raw": llm_out.get("raw")
                }) + "\n")
            else:
                llm_fields = llm_out.get("parsed_fields", {})
                llm_eval = compare_expected_to_parsed(expected, llm_fields)

            # --- FUSION parser ---
            fusion_out = parse_text_fused(text)
            fused_fields = fusion_out.get("fused_fields", {})
            fusion_eval = compare_expected_to_parsed(expected, fused_fields)

            # --- Accumulate summary ---
            results_summary["rule_accuracy"].append(rule_eval["accuracy"])
            results_summary["extended_accuracy"].append(ext_eval["accuracy"])
            results_summary["llm_accuracy"].append(llm_eval["accuracy"])
            results_summary["fusion_accuracy"].append(fusion_eval["accuracy"])

            # Collect hallucinations (LLM mainly)
            for field, val in llm_eval["hallucinated"]:
                results_summary["hallucinated_fields"].setdefault(field, 0)
                results_summary["hallucinated_fields"][field] += 1

            # Detailed line-by-line log
            detailed_log.write(json.dumps({
                "name": name,
                "input": text,
                "expected": expected,
                "rules": rule_eval,
                "extended": ext_eval,
                "llm": llm_eval,
                "fusion": fusion_eval,
            }) + "\n")

    # Compute summary metrics
    results_summary["rule_accuracy_mean"] = mean(results_summary["rule_accuracy"])
    results_summary["extended_accuracy_mean"] = mean(results_summary["extended_accuracy"])
    results_summary["llm_accuracy_mean"] = mean(results_summary["llm_accuracy"])
    results_summary["fusion_accuracy_mean"] = mean(results_summary["fusion_accuracy"])

    # Save summary
    summary_path = os.path.join(REPORT_DIR, "parser_eval_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2)

    results_summary["paths"]["summary"] = summary_path
    results_summary["paths"]["detailed"] = detailed_log_path
    results_summary["paths"]["llm_errors"] = llm_error_path

    return results_summary
