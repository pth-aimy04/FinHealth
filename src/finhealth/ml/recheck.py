"""Evaluate isolated historical windows without replacing the active model."""

import argparse
import json
from pathlib import Path

import pandas as pd

from finhealth.core.config import get_settings
from finhealth.ml.registry import train_and_evaluate_pipeline


def main() -> int:
    """Compare two independently fitted windows on the same audited SEC panel."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    settings = get_settings()
    source = settings.parquet_path / "sec_real_panel.parquet"
    panel = pd.read_parquet(source)
    if not panel["data_source"].eq("cached_sec").all():
        raise ValueError("Expected only cached SEC observations")
    results = []
    for train, validation in ((2020, 2021), (2021, 2022)):
        bundle = train_and_evaluate_pipeline(
            panel, train, f"recheck-{train}", settings.random_seed, validation_end_year=validation
        )
        report = bundle.evaluation_report
        results.append({
            "train_end_year": train, "validation_end_year": validation,
            "split": report["split_summary"],
            "classification_xgboost": report["classification_xgboost"],
            "classification_baselines": report["classification_baselines"],
            "forecasting_paired": report["forecasting_paired"],
        })
    args.output.write_text(json.dumps({
        "source": source.name, "rows": len(panel), "company_count": int(panel["cik"].nunique()),
        "label": "SEC annual accounting distress proxy",
        "evaluation_policy": "Expanding holdouts can overlap. Each fit uses its own time cutoff.",
        "windows": results,
    }, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Wrote {len(results)} evaluation windows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
