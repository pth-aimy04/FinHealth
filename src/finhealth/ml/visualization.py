"""Headless 300-DPI evaluation figures computed from real fitted models and held-out predictions."""

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from sklearn.metrics import (
    average_precision_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

from finhealth.core.exceptions import ModelPipelineError
from finhealth.ml.evaluator import evaluate_binary_classification, evaluate_multitarget_regression
from finhealth.ml.explainer import ShapExplainer
from finhealth.ml.registry import ModelArtifactBundle
from finhealth.ml.splitter import FORECAST_TARGET_COLUMNS, RATIO_FEATURE_COLUMNS

PLOT_FILENAMES: tuple[str, ...] = (
    "01_correlation_heatmap.png",
    "02_pca_scree_and_clusters.png",
    "03_roc_pr_curves_comparison.png",
    "04_confusion_matrices.png",
    "05_forecasting_actual_vs_predicted.png",
    "06_shap_global_importance.png",
    "07_reliability_calibration.png",
)
MODEL_NAMES: dict[str, str] = {
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "random_forest": "Random Forest",
    "logistic_regression": "Hồi quy logistic",
    "altman_z_baseline": "Altman Z",
}
CLUSTER_NAMES = (
    "Tài chính vững mạnh",
    "Ổn định, đòn bẩy vừa phải",
    "Đòn bẩy cao, cần theo dõi",
    "Khó khăn tài chính, rủi ro cao",
)
FEATURE_NAMES = {
    "roa": "Sinh lời trên tài sản (ROA)",
    "roe": "Sinh lời trên vốn chủ sở hữu (ROE)",
    "eps": "Lợi nhuận mỗi cổ phiếu (EPS)",
    "debt_ratio": "Nợ phải trả / tài sản",
    "debt_to_equity": "Nợ phải trả / vốn chủ sở hữu",
    "ocf_ratio": "Dòng tiền hoạt động / nợ phải trả",
    "current_ratio": "Hệ số thanh toán hiện hành",
    "operating_margin": "Biên lợi nhuận hoạt động",
    "working_capital_ratio": "Vốn lưu động / tài sản",
    "retained_earnings_ratio": "Lợi nhuận giữ lại / tài sản",
    "ebit_to_assets": "Lợi nhuận hoạt động / tài sản",
    "asset_turnover": "Vòng quay tài sản",
    "cash_ratio": "Hệ số thanh toán bằng tiền",
    "interest_coverage": "Khả năng trả lãi vay",
    "fcf_to_liabilities": "Dòng tiền tự do / nợ phải trả",
    "roa_yoy_delta": "Thay đổi ROA so với năm trước",
    "roe_yoy_delta": "Thay đổi ROE so với năm trước",
    "debt_ratio_yoy_delta": "Thay đổi tỷ lệ nợ so với năm trước",
    "ocf_ratio_yoy_delta": "Thay đổi tỷ lệ dòng tiền hoạt động so với năm trước",
    "negative_ocf_streak": "Số năm liên tiếp có dòng tiền hoạt động âm",
}


def classification_scores(bundle: ModelArtifactBundle, test: pd.DataFrame) -> dict[str, np.ndarray]:
    """Obtain actual positive-risk scores from all fitted models on identical rows."""
    candidates = getattr(bundle, "candidates", None)
    if candidates:
        scores = {name: clf.predict_proba(test) for name, clf in candidates.items()}
    else:
        model_name = getattr(bundle.classifier, "model_type", "xgboost")
        scores = {model_name: bundle.classifier.predict_proba(test)}
    return {**scores, **bundle.baselines.predict_probabilities(test)}


class EvaluationPlotGenerator:
    """Render publication-ready charts without fitting estimators on evaluation data."""

    def __init__(
        self,
        bundle: ModelArtifactBundle,
        df_train: pd.DataFrame,
        df_test: pd.DataFrame,
        output_dir: Path,
    ) -> None:
        """Retain immutable training/test inputs and an explicit artifact destination."""
        self.bundle, self.train, self.test = bundle, df_train.copy(), df_test.copy()
        self.output_dir = output_dir
        self.labeled = self.test.dropna(subset=["next_is_distressed"])
        if self.train.empty or self.labeled.empty:
            raise ModelPipelineError("Evaluation figures require training and labeled test rows")
        self.y = self.labeled["next_is_distressed"].astype(int).to_numpy()

    def _save(self, figure: Figure, filename: str) -> Path:
        """Save a tightly laid-out 300-DPI PNG and always release the figure resource."""
        target = self.output_dir / filename
        try:
            source_counts = self.bundle.evaluation_report.get("data_provenance", {}).get(
                "source_counts", {}
            )
            if source_counts.get("synthetic_benchmark", 0):
                figure.text(
                    0.5,
                    -0.02,
                    "Đánh giá trên dữ liệu mô phỏng và nhãn đại diện",
                    ha="center",
                    fontsize=8,
                    color="#555555",
                )
            figure.savefig(
                target,
                dpi=300,
                bbox_inches="tight",
                facecolor="white",
                metadata={"Software": "FinHealth evaluation"},
            )
        finally:
            plt.close(figure)
        return target

    def _heatmap(self) -> Figure:
        """Show pairwise Tương quan Pearsons from the training ratios only."""
        matrix = self.train[list(RATIO_FEATURE_COLUMNS)].corr().to_numpy()
        figure, axis = plt.subplots(figsize=(12, 10), layout="constrained")
        heat = axis.imshow(np.ma.masked_invalid(matrix), cmap="RdBu_r", vmin=-1, vmax=1)
        labels = [FEATURE_NAMES.get(name, name) for name in RATIO_FEATURE_COLUMNS]
        axis.set_xticks(range(len(labels)), labels, rotation=55, ha="right")
        axis.set_yticks(range(len(labels)), labels)
        for row in range(len(labels)):
            for col in range(len(labels)):
                value = matrix[row, col]
                axis.text(
                    col,
                    row,
                    f"{value:.2f}" if np.isfinite(value) else "—",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if np.isfinite(value) and abs(value) > 0.65 else "black",
                )
        figure.colorbar(heat, ax=axis, label="Tương quan Pearson")
        axis.set_title("Tương quan Pearson giữa các tỷ số trên tập huấn luyện")
        return figure

    def _pca(self) -> Figure:
        """Plot fitted training variance and held-out semantic cluster assignments."""
        figure, axes = plt.subplots(1, 2, figsize=(14, 5), layout="constrained")
        ratios = np.array(self.bundle.clusterer.diagnostics_["explained_variance_ratio"])
        x = np.arange(1, len(ratios) + 1)
        axes[0].bar(x, ratios, label="Phương sai từng thành phần", color="#2563eb")
        axes[0].plot(x, ratios.cumsum(), "o-", label="Phương sai tích lũy", color="#d97706")
        axes[0].set(
            xlabel="Thành phần chính",
            ylabel="Tỷ lệ phương sai giải thích được",
            title="Phương sai PCA trên tập huấn luyện",
            ylim=(0, 1.05),
            xticks=x,
        )
        axes[0].legend()
        points = self.bundle.clusterer.transform(self.test)
        for index, label in enumerate(CLUSTER_NAMES):
            subset = points.loc[points["cluster_id"] == index]
            if not subset.empty:
                axes[1].scatter(
                    subset["pca_comp_1"],
                    subset["pca_comp_2"],
                    label=label,
                    s=24,
                    alpha=0.7,
                    color=("#15803d", "#2563eb", "#d97706", "#b91c1c")[index],
                )
        axes[1].set(
            xlabel="Thành phần chính 1",
            ylabel="Thành phần chính 2",
            title="Phân cụm doanh nghiệp ngoài giai đoạn huấn luyện",
        )
        axes[1].legend(fontsize=7, loc="best")
        return figure

    def _curves(self, scores: dict[str, np.ndarray]) -> Figure:
        """Compare actual ROC and precision-recall curves without assuming two test classes."""
        figure, axes = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
        for name, probabilities in scores.items():
            if len(np.unique(self.y)) == 2:
                fpr, tpr, _ = roc_curve(self.y, probabilities)
                axes[0].plot(
                    fpr,
                    tpr,
                    label=f"{MODEL_NAMES[name]} (AUC={roc_auc_score(self.y, probabilities):.3f})",
                )
            else:
                axes[0].text(
                    0.1,
                    0.5,
                    "Tập kiểm định chỉ có một lớp, không tính được ROC",
                    transform=axes[0].transAxes,
                )
            if self.y.any():
                precision, recall, _ = precision_recall_curve(self.y, probabilities)
                ap = average_precision_score(self.y, probabilities)
                axes[1].plot(recall, precision, label=f"{MODEL_NAMES[name]} (AP={ap:.3f})")
        axes[0].plot([0, 1], [0, 1], "--", color="gray", label="Phân loại ngẫu nhiên")
        axes[1].axhline(
            self.y.mean(), linestyle="--", color="gray", label="Tỷ lệ ca dương trong tập kiểm định"
        )
        for axis in axes:
            axis.set(xlim=(0, 1), ylim=(0, 1.03))
            axis.legend(fontsize=8)
        axes[0].set(
            xlabel="Tỷ lệ dương tính giả", ylabel="Tỷ lệ dương tính thật", title="So sánh đường ROC"
        )
        axes[1].set(
            xlabel="Độ nhạy",
            ylabel="Tỷ lệ dự báo dương đúng",
            title="So sánh độ chính xác và độ nhạy",
        )
        return figure

    def _confusions(self, scores: dict[str, np.ndarray]) -> Figure:
        """Render count matrices using the exact evaluated model-specific decision rules."""
        count = len(scores)
        cols = 3
        rows = math.ceil(count / cols)
        figure, axes = plt.subplots(
            rows, cols, figsize=(13, 4.5 * rows), layout="constrained"
        )
        axes_list = list(np.asarray(axes).flat)
        candidates = getattr(self.bundle, "candidates", None) or {}
        for axis, (name, probabilities) in zip(axes_list, scores.items(), strict=False):
            if name in candidates:
                threshold = candidates[name].optimal_threshold_
            elif name == getattr(self.bundle.classifier, "model_type", "xgboost"):
                threshold = self.bundle.classifier.optimal_threshold_
            elif name == "altman_z_baseline":
                threshold = float(np.nextafter(0.5, 1))
            else:
                threshold = 0.5
            report = evaluate_binary_classification(self.y, probabilities, threshold)
            counts = report["confusion_matrix"]
            matrix = np.array([[counts["tn"], counts["fp"]], [counts["fn"], counts["tp"]]])
            axis.imshow(matrix, cmap="Blues", vmin=0, vmax=max(len(self.y), 1))
            for (row, col), label in zip(np.ndindex(2, 2), ("TN", "FP", "FN", "TP"), strict=True):
                axis.text(col, row, f"{label}\n{matrix[row, col]}", ha="center", va="center")
            axis.set(
                xticks=[0, 1],
                yticks=[0, 1],
                xticklabels=["Không khó khăn", "Khó khăn tài chính"],
                yticklabels=["Không khó khăn", "Khó khăn tài chính"],
                xlabel="Dự báo",
                ylabel="Thực tế",
                title=f"{MODEL_NAMES[name]}\nNgưỡng {threshold:.2f}",
            )
        for unused in axes_list[count:]:
            unused.set_visible(False)
        return figure

    def _forecasts(self) -> Figure:
        """Plot each observed next-period target against its actual model forecast."""
        predicted = self.bundle.forecaster.predict(self.test)
        metrics = evaluate_multitarget_regression(self.test, predicted)
        figure, axes = plt.subplots(2, 3, figsize=(14, 8), layout="constrained")
        for axis, target in zip(axes.flat, FORECAST_TARGET_COLUMNS, strict=False):
            paired = pd.concat([self.test[f"next_{target}"], predicted[f"pred_{target}"]], axis=1)
            paired = paired.replace([np.inf, -np.inf], np.nan).dropna()
            if not paired.empty:
                axis.scatter(paired.iloc[:, 0], paired.iloc[:, 1], alpha=0.6, s=20)
                low, high = paired.to_numpy().min(), paired.to_numpy().max()
                axis.plot(
                    [low, high], [low, high], "--", color="gray", label="Dự báo trùng thực tế"
                )
                row = metrics[target]
                axis.set_title(
                    f"{FEATURE_NAMES.get(target, target)}\nMAE={row['mae']:.3g}, "
                    f"RMSE={row['rmse']:.3g}, R²={row['r2']:.3g}"
                    if row["r2"] is not None
                    else f"{FEATURE_NAMES.get(target, target)} | chưa tính được R²",
                    fontsize=9,
                )
                axis.legend(fontsize=7)
            axis.set(xlabel="Giá trị thực tế kỳ tới", ylabel="Giá trị dự báo kỳ tới")
        axes.flat[-1].set_visible(False)
        return figure

    def _shap(self) -> Figure:
        """Compute real held-out TreeSHAP mean absolute contributions in log-odds units."""
        importance = ShapExplainer(self.bundle.classifier).compute_global_importance(self.labeled)
        pairs = list(reversed(list(importance.items())))
        figure, axis = plt.subplots(figsize=(12, 7), layout="constrained")
        axis.barh(
            [FEATURE_NAMES.get(key, key) for key, _ in pairs],
            [value for _, value in pairs],
            color="#2563eb",
        )
        axis.set(
            xlabel="Trung bình trị tuyệt đối đóng góp TreeSHAP (log-odds)",
            title="Mức độ ảnh hưởng của đặc trưng ngoài giai đoạn huấn luyện",
        )
        return figure

    def _reliability(self) -> Figure:
        """Plot empirical calibration reliability bins (raw vs calibrated) against y = x."""
        bins = self.bundle.evaluation_report.get("test_reliability_bins", [])
        figure, axis = plt.subplots(figsize=(7, 6), layout="constrained")
        axis.plot([0, 1], [0, 1], "--", color="gray", label="Hiệu chuẩn lý tưởng (y = x)")
        for score_kind, label, color, marker in (
            ("raw", "Trước hiệu chuẩn (Raw)", "#d97706", "s"),
            ("calibrated", "Sau hiệu chuẩn (Calibrated)", "#2563eb", "o"),
        ):
            subset = [
                row
                for row in bins
                if row.get("model") == score_kind and row.get("n", 0) > 0
            ]
            if subset:
                xs = [row["mean_probability"] for row in subset]
                ys = [row["observed_prevalence"] for row in subset]
                axis.plot(xs, ys, f"{marker}-", color=color, label=label, linewidth=2)
        selected_name = self.bundle.evaluation_report.get(
            "selected_model_name", getattr(self.bundle.classifier, "model_type", "xgboost")
        )
        axis.set(
            xlim=(0, 1),
            ylim=(0, 1.03),
            xlabel="Xác suất dự báo trung bình",
            ylabel="Tỷ lệ khó khăn tài chính thực tế",
            title=f"Đường hiệu chuẩn xác suất ({MODEL_NAMES.get(selected_name, selected_name)})",
        )
        axis.legend(loc="upper left")
        return figure

    def generate(self) -> list[Path]:
        """Write all seven figures from real training/test inputs and return their paths."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with plt.rc_context(
            {
                "font.family": "DejaVu Sans",
                "font.size": 10,
                "axes.spines.top": False,
                "axes.spines.right": False,
                "axes.titleweight": "bold",
                "savefig.dpi": 300,
            }
        ):
            scores = classification_scores(self.bundle, self.labeled)
            figures = (
                self._heatmap,
                self._pca,
                lambda: self._curves(scores),
                lambda: self._confusions(scores),
                self._forecasts,
                self._shap,
                self._reliability,
            )
            return [
                self._save(builder(), filename)
                for builder, filename in zip(figures, PLOT_FILENAMES, strict=True)
            ]
