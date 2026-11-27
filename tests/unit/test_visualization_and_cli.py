"""Real training CLI, 300-DPI PNG codecs, training boundaries, and artifact round trips."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from PIL import Image

from finhealth.core.config import Settings
from finhealth.core.exceptions import ModelPipelineError
from finhealth.ml.benchmark_data import build_benchmark_panel
from finhealth.ml.registry import load_bundle
from finhealth.ml.splitter import TemporalSplitter, build_next_period_panel
from finhealth.ml.train_cli import (
    load_cached_panel,
    main,
    render_benchmark_report,
    run_training,
)
from finhealth.ml.visualization import PLOT_FILENAMES, EvaluationPlotGenerator


def test_visualization_and_cli_artifacts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Run actual CLI training and validate every physical PNG, JSON report, and saved estimator."""
    assert main(["--offline", "--data-dir", str(tmp_path), "--model-version", "test-v1"]) == 0
    output = capsys.readouterr().out
    assert all(
        name in output
        for name in (
            "DISTRESS CLASSIFICATION",
            "ROC-AUC",
            "PR-AUC",
            "MAE",
            "Silhouette Score",
            "TREESHAP",
            "Synthetic rows",
        )
    )
    destination = tmp_path / "artifacts/models/test-v1"
    report = json.loads((destination / "evaluation_report.json").read_text())
    assert report["data_provenance"]["source_counts"] == {"synthetic_benchmark": 640}
    assert report["split_summary"]["validation_rows"] == 80
    assert report["split_summary"]["min_test_feature_year"] == 2022
    assert report["split_summary"]["max_train_target_year"] <= 2020
    assert report["split_summary"]["threshold_source"].startswith("validation_")
    assert (destination / "BENCHMARK_REPORT.md").is_file()
    benchmark = (destination / "BENCHMARK_REPORT.md").read_text()
    assert "not observed bankruptcy" in benchmark
    assert (
        output.split("DATASET AND TEMPORAL SPLITS", 1)[1].split("\n\nArtifacts:")[0].strip()
        in benchmark
    )
    for name in PLOT_FILENAMES:
        path = tmp_path / "artifacts/figures" / name
        assert path.stat().st_size > 20000
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert min(image.size) > 800
            assert image.info["dpi"][0] == pytest.approx(300, abs=0.1)
            assert np.asarray(image.convert("RGB")).std() > 10
        with Image.open(path) as image:
            image.verify()
    bundle = load_bundle(destination)
    latest = json.loads((tmp_path / "artifacts/models/latest.json").read_text())
    assert latest["model_version"] == bundle.model_version == "test-v1"
    assert bundle.classifier.optimal_threshold_ == report["classification_xgboost"]["threshold"]
    assert bundle.evaluation_report["global_shap_importance"]
    parquet = pd.read_parquet(tmp_path / "processed/parquet/benchmark_panel.parquet")
    assert len(parquet) == 640
    assert parquet["company_id"].nunique() == 80
    settings = Settings(
        _env_file=None, data_dir=tmp_path, sec_user_agent="Offline/1.0 (offline@example.invalid)"
    )
    with pytest.raises(ModelPipelineError, match="version exists"):
        run_training(settings, model_version="test-v1", offline=True)


def test_benchmark_reproducibility_and_cached_sec_etl(tmp_path: Path) -> None:
    """Synthetic accounting identities hold and genuine cached inputs retain separate provenance."""
    first = build_benchmark_panel(n_companies=4)
    second = build_benchmark_panel(n_companies=4)
    pd.testing.assert_frame_equal(first, second)
    assert set(first["fiscal_year"]) == set(range(2016, 2024))
    assert first["data_source"].eq("synthetic_benchmark").all()
    np.testing.assert_allclose(
        first["total_assets"], first["total_liabilities"] + first["stockholders_equity"]
    )
    np.testing.assert_allclose(first["roa"], first["net_income"] / first["total_assets"])
    settings = Settings(
        _env_file=None, data_dir=tmp_path, sec_user_agent="Offline/1.0 (offline@example.invalid)"
    )
    directory = settings.raw_sec_dir / "companyfacts"
    directory.mkdir(parents=True)
    fixture = (
        Path(__file__).resolve().parents[1] / "fixtures/sec_companyfacts_0000320193_sample.json"
    )
    (directory / "CIK0000320193.json").write_bytes(fixture.read_bytes())
    cached = load_cached_panel(settings)
    assert len(cached) == 2
    assert cached["data_source"].eq("cached_sec").all()
    assert cached.loc[cached["fiscal_year"] == 2023, "net_income"].iloc[0] == 96995000000
    next_panel = build_next_period_panel(first)
    assert next_panel.loc[next_panel["fiscal_year"] == 2023, "next_roa"].isna().all()


def test_reliability_curve_plots_raw_and_calibrated_bins(tmp_path: Path) -> None:
    """Verify _reliability() renders reference y=x plus non-empty raw and calibrated curves."""
    assert main(["--offline", "--data-dir", str(tmp_path), "--model-version", "rel-v1"]) == 0
    bundle = load_bundle(tmp_path / "artifacts/models/rel-v1")
    panel = build_next_period_panel(
        pd.read_parquet(tmp_path / "processed/parquet/benchmark_panel.parquet")
    )
    parts = TemporalSplitter().split(panel, 2020, 2021)
    plotter = EvaluationPlotGenerator(
        bundle, parts["train"], parts["test"], tmp_path / "artifacts/figures"
    )
    figure = plotter._reliability()
    try:
        axis = figure.axes[0]
        assert len(axis.lines) >= 3
        labels = [str(line.get_label()) for line in axis.lines]
        assert any("Raw" in label for label in labels)
        assert any("Calibrated" in label for label in labels)
        bins = bundle.evaluation_report["test_reliability_bins"]
        raw_bins = [row for row in bins if row.get("model") == "raw" and row.get("n", 0) > 0]
        cal_bins = [
            row for row in bins if row.get("model") == "calibrated" and row.get("n", 0) > 0
        ]
        assert raw_bins and cal_bins
        raw_line = next(line for line in axis.lines if "Raw" in str(line.get_label()))
        cal_line = next(line for line in axis.lines if "Calibrated" in str(line.get_label()))
        np.testing.assert_allclose(
            raw_line.get_xdata(), [row["mean_probability"] for row in raw_bins]
        )
        np.testing.assert_allclose(
            raw_line.get_ydata(), [row["observed_prevalence"] for row in raw_bins]
        )
        np.testing.assert_allclose(
            cal_line.get_xdata(), [row["mean_probability"] for row in cal_bins]
        )
        np.testing.assert_allclose(
            cal_line.get_ydata(), [row["observed_prevalence"] for row in cal_bins]
        )
    finally:
        plt.close(figure)


def test_render_benchmark_report_kaggle_provenance(tmp_path: Path) -> None:
    """Kaggle BENCHMARK_REPORT.md must describe observed bankruptcy labels, not synthetic rows."""
    destination = tmp_path / "artifacts" / "models" / "kaggle-v1"
    destination.mkdir(parents=True)
    fig = tmp_path / "artifacts" / "figures" / "01_roc_pr_curves.png"
    kaggle_md = render_benchmark_report(
        model_version="kaggle-v1",
        dataset="kaggle",
        real_only=False,
        live_status="not applicable (Kaggle US Company Bankruptcy dataset)",
        train_end_year=2014,
        validation_end_year=2016,
        tables="METRIC TABLE",
        paths=[fig],
        destination=destination,
    )
    assert "Kaggle US Company Bankruptcy dataset" in kaggle_md
    assert "observed corporate bankruptcy outcomes" in kaggle_md
    assert "Synthetic rows" not in kaggle_md
    assert "simulated accounting records" not in kaggle_md
    assert "not observed bankruptcy outcomes" not in kaggle_md

    real_md = render_benchmark_report(
        model_version="sec-v1",
        dataset="sec",
        real_only=True,
        live_status="not attempted",
        train_end_year=2021,
        validation_end_year=2022,
        tables="METRIC TABLE",
        paths=[fig],
        destination=destination,
    )
    assert "only real SEC EDGAR annual financial statements" in real_md
    assert "Synthetic rows" not in real_md


