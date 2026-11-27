"""Training-only PCA and financially ordered K-Means semantics."""

import warnings
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import RobustScaler, StandardScaler

from finhealth.core.exceptions import ModelPipelineError
from finhealth.ml.preprocessing import FinancialPreprocessor
from finhealth.ml.splitter import RATIO_FEATURE_COLUMNS

CLUSTER_LABELS: tuple[str, ...] = (
    "Strong Financial Health",
    "Stable / Moderate Leverage",
    "Elevated Leverage / Watchlist",
    "Financial Distress / High Risk",
)


class FinancialHealthClusterer:
    """Rank clusters by original-feature scaled health, never by arbitrary K-Means IDs."""

    def __init__(
        self,
        feature_columns: Sequence[str] = RATIO_FEATURE_COLUMNS,
        n_components: int = 3,
        n_clusters: int = 4,
        random_seed: int = 42,
    ) -> None:
        """Initialize deterministic unsupervised stages and validate supported cluster count."""
        if not 1 <= n_clusters <= 4 or n_components < 1:
            raise ModelPipelineError("Require 1..4 clusters and at least one PCA component")
        self.feature_columns = tuple(feature_columns)
        self.n_components, self.n_clusters, self.random_seed = n_components, n_clusters, random_seed
        self.preprocessor = FinancialPreprocessor(self.feature_columns, 0.05, 0.95)
        self.scaler = RobustScaler()
        self.standard_scaler = StandardScaler()
        self.pca_: PCA | None = None
        self.kmeans_: KMeans | None = None
        self.cluster_mapping_: dict[int, int] = {}
        self.diagnostics_: dict[str, Any] = {}

    def fit(self, df_train: pd.DataFrame) -> "FinancialHealthClusterer":
        """Fit preprocessing/PCA/K-Means exclusively on supplied training feature rows."""
        self.preprocessor.fit(df_train)
        values = self.preprocessor.transform(df_train)
        scaled = self.standard_scaler.fit_transform(self.scaler.fit_transform(values))
        self.effective_n_components_ = min(self.n_components, *scaled.shape)
        self.effective_n_clusters_ = min(
            self.n_clusters, len(scaled), len(np.unique(scaled, axis=0))
        )
        self.pca_ = PCA(n_components=self.effective_n_components_, random_state=self.random_seed)
        # PCA's variance fractions are undefined for constant/single-row training data.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", category=RuntimeWarning, module="sklearn.decomposition"
            )
            self.pca_.fit(scaled)
        variance = np.nan_to_num(self.pca_.explained_variance_ratio_)
        coordinates = self.pca_.transform(scaled)
        self.kmeans_ = KMeans(
            n_clusters=self.effective_n_clusters_, n_init=10, random_state=self.random_seed
        ).fit(coordinates)
        labels = self.kmeans_.labels_
        profiles: dict[int, dict[str, Any]] = {}
        for raw in sorted(set(labels.tolist())):
            mask = labels == raw
            profile = dict(
                zip(self.feature_columns, scaled[mask].mean(axis=0).tolist(), strict=True)
            )
            score = sum(
                profile.get(column, 0) for column in ("roa", "roe", "ocf_ratio", "current_ratio")
            )
            score -= sum(profile.get(column, 0) for column in ("debt_ratio", "debt_to_equity"))
            profiles[raw] = {
                "health_score": score,
                "scaled_centroid": profile,
                "centroid": dict(
                    zip(self.feature_columns, values[mask].mean(axis=0).tolist(), strict=True)
                ),
            }
        ordered = sorted(
            profiles,
            key=lambda raw: (
                -profiles[raw]["health_score"],
                tuple(profiles[raw]["scaled_centroid"].values()),
                raw,
            ),
        )
        self.cluster_mapping_ = {raw: rank for rank, raw in enumerate(ordered)}
        count = len(set(labels))
        silhouette = silhouette_score(coordinates, labels) if 1 < count < len(values) else 0.0
        self.diagnostics_ = {
            "explained_variance_ratio": variance.tolist(),
            "cumulative_variance_ratio": float(variance.sum()),
            "silhouette_score": float(silhouette),
            "cluster_profiles": {
                self.cluster_mapping_[raw]: profile for raw, profile in profiles.items()
            },
            "standardized_feature_variance": dict(
                zip(self.feature_columns, np.var(scaled, axis=0).tolist(), strict=True)
            ),
        }
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return three PCA coordinates and ordered health semantics aligned to input indices."""
        if self.pca_ is None or self.kmeans_ is None:
            raise ModelPipelineError("Clusterer must be fitted before transform")
        scaled = self.scaler.transform(self.preprocessor.transform(df))
        if getattr(self, "standard_scaler", None) is not None:
            scaled = self.standard_scaler.transform(scaled)
        coordinates = self.pca_.transform(scaled)
        raw = self.kmeans_.predict(coordinates)
        result = pd.DataFrame(index=df.index)
        for i in range(3):
            result[f"pca_comp_{i + 1}"] = coordinates[:, i] if i < coordinates.shape[1] else 0.0
        result["cluster_id"] = [self.cluster_mapping_[int(label)] for label in raw]
        result["cluster_label"] = [CLUSTER_LABELS[label] for label in result["cluster_id"]]
        return result
