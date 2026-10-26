"""Fold-contained, lineage-preserving preprocessing for Track A research models.

Key design guarantees:
1. Every data-dependent statistic (median, mean, standard deviation, categorical
   mode) is estimated strictly from the training fold supplied to ``fit``.
2. Categorical indicator columns follow the fixed registered vocabulary order
   (reference-dropped at ``codes[0]``), never data-discovered category order.
3. Optional stage fields always reserve an explicit ``<field>__missing`` column
   even when the training fold happens to be 100% complete (as in Cleveland
   ``chol``), preventing shape drift on external cohorts (such as Hungary) or
   partially populated clinician/lab intake payloads.
4. Every raw clinical/lab variable owns a contiguous, disjoint slice of encoded
   columns (``feature_slices``), enabling mathematically exact feature-level
   aggregation in LinearSHAP and Grouped Interventional TreeSHAP.
5. Serializes to and reloads from pure deterministic JSON (``preprocessing.json``)
   with SHA-256 verification — zero pickle dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any, Final, Mapping

import numpy as np

from ai.errors import PreprocessingContractError
from ai.panels import PanelFieldSpec, ResearchPanelContract, get_panel_contract

PREPROCESSING_SCHEMA_VERSION: Final[str] = "cardioassist.ai.preprocessing/v1"


@dataclass(frozen=True, slots=True)
class FittedFieldTransform:
    """Immutable fitted transformation state for a single panel field."""

    name: str
    role: str
    required: bool
    encoded_columns: tuple[str, ...]
    slice_indices: tuple[int, ...]
    # Numeric state
    impute_median: float | None = None
    scale_mean: float | None = None
    scale_std: float | None = None
    # Categorical state
    categorical_codes: tuple[int, ...] = ()
    impute_mode_code: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "required": self.required,
            "encoded_columns": list(self.encoded_columns),
            "slice_indices": list(self.slice_indices),
            "impute_median": self.impute_median,
            "scale_mean": self.scale_mean,
            "scale_std": self.scale_std,
            "categorical_codes": list(self.categorical_codes),
            "impute_mode_code": self.impute_mode_code,
        }


@dataclass(frozen=True, slots=True)
class FoldSafeClinicalPreprocessor:
    """Immutable fitted preprocessor bound to a specific ``ResearchPanelContract``."""

    panel_id: str
    panel_contract_sha256: str
    n_training_rows: int
    field_transforms: tuple[FittedFieldTransform, ...]
    encoded_feature_names: tuple[str, ...]

    @property
    def raw_feature_names(self) -> tuple[str, ...]:
        return tuple(ft.name for ft in self.field_transforms)

    @property
    def n_raw_features(self) -> int:
        return len(self.field_transforms)

    @property
    def n_encoded_features(self) -> int:
        return len(self.encoded_feature_names)

    @property
    def feature_slices(self) -> Mapping[str, tuple[int, ...]]:
        return MappingProxyType(
            {ft.name: ft.slice_indices for ft in self.field_transforms}
        )

    @classmethod
    def fit(
        cls,
        X_train: np.ndarray,
        panel: ResearchPanelContract,
    ) -> "FoldSafeClinicalPreprocessor":
        arr = np.asarray(X_train, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[1] != len(panel.fields):
            raise PreprocessingContractError(
                "invalid_training_shape",
                "Training matrix column count does not match panel contract.",
            )
        if arr.shape[0] < 2:
            raise PreprocessingContractError(
                "insufficient_training_rows",
                "Fold-safe preprocessing requires at least two training rows.",
            )
        if np.isinf(arr).any():
            raise PreprocessingContractError(
                "infinite_training_value",
                "Infinite values are forbidden in training matrices.",
            )

        transforms: list[FittedFieldTransform] = []
        encoded_names: list[str] = []
        cursor = 0

        for col_idx, spec in enumerate(panel.fields):
            col = arr[:, col_idx]
            is_nan = np.isnan(col)
            if spec.required and bool(is_nan.any()):
                raise PreprocessingContractError(
                    "missing_required_training_value",
                    f"Required clinical feature '{spec.name}' contains missing values in training fold.",
                    field=spec.name,
                )
            observed = col[~is_nan]
            if observed.size == 0:
                raise PreprocessingContractError(
                    "all_missing_training_column",
                    f"Training fold has zero observed measurements for '{spec.name}'.",
                    field=spec.name,
                )

            if spec.role == "numeric":
                median = float(np.median(observed))
                filled = np.where(is_nan, median, col)
                mean = float(np.mean(filled))
                std_raw = float(np.std(filled, ddof=0))
                scale_std = std_raw if std_raw > 1e-12 else 1.0

                cols_for_field = [f"{spec.name}__zscore"]
                if not spec.required:
                    cols_for_field.append(f"{spec.name}__missing")
                indices = tuple(range(cursor, cursor + len(cols_for_field)))
                cursor += len(cols_for_field)
                encoded_names.extend(cols_for_field)

                transforms.append(
                    FittedFieldTransform(
                        name=spec.name,
                        role="numeric",
                        required=spec.required,
                        encoded_columns=tuple(cols_for_field),
                        slice_indices=indices,
                        impute_median=median,
                        scale_mean=mean,
                        scale_std=scale_std,
                    )
                )
            elif spec.role == "categorical":
                obs_int = observed.astype(np.int64)
                if not np.all(obs_int == observed):
                    raise PreprocessingContractError(
                        "non_integer_categorical_code",
                        f"Categorical column '{spec.name}' contains non-integer values.",
                        field=spec.name,
                    )
                allowed = set(spec.categorical_codes)
                if not set(obs_int.tolist()).issubset(allowed):
                    raise PreprocessingContractError(
                        "unknown_categorical_training_code",
                        f"Categorical column '{spec.name}' contains unregistered codes.",
                        field=spec.name,
                    )
                # Deterministic mode: highest count in training fold, tie-broken by canonical code order
                best_code = spec.categorical_codes[0]
                best_count = -1
                for code in spec.categorical_codes:
                    cnt = int(np.sum(obs_int == code))
                    if cnt > best_count:
                        best_count = cnt
                        best_code = code

                cols_for_field = [
                    f"{spec.name}__eq_{code}" for code in spec.categorical_codes[1:]
                ]
                if not spec.required:
                    cols_for_field.append(f"{spec.name}__missing")
                indices = tuple(range(cursor, cursor + len(cols_for_field)))
                cursor += len(cols_for_field)
                encoded_names.extend(cols_for_field)

                transforms.append(
                    FittedFieldTransform(
                        name=spec.name,
                        role="categorical",
                        required=spec.required,
                        encoded_columns=tuple(cols_for_field),
                        slice_indices=indices,
                        categorical_codes=spec.categorical_codes,
                        impute_mode_code=best_code,
                    )
                )
            else:
                raise PreprocessingContractError(
                    "unsupported_field_role",
                    f"Unsupported role '{spec.role}' for '{spec.name}'.",
                    field=spec.name,
                )

        instance = cls(
            panel_id=panel.panel_id,
            panel_contract_sha256=panel.contract_sha256,
            n_training_rows=int(arr.shape[0]),
            field_transforms=tuple(transforms),
            encoded_feature_names=tuple(encoded_names),
        )
        instance._verify_lineage_invariants(panel)
        return instance

    def _verify_lineage_invariants(self, panel: ResearchPanelContract) -> None:
        if self.panel_id != panel.panel_id or self.panel_contract_sha256 != panel.contract_sha256:
            raise PreprocessingContractError(
                "panel_contract_mismatch",
                "Preprocessor panel binding does not match active panel contract.",
            )
        if self.raw_feature_names != panel.feature_names:
            raise PreprocessingContractError(
                "feature_order_mismatch",
                "Preprocessor feature order does not match panel contract order.",
            )
        covered: list[int] = []
        for ft in self.field_transforms:
            if not ft.slice_indices:
                raise PreprocessingContractError(
                    "empty_feature_slice",
                    f"Feature '{ft.name}' produced zero encoded columns.",
                    field=ft.name,
                )
            covered.extend(ft.slice_indices)
        if covered != list(range(self.n_encoded_features)):
            raise PreprocessingContractError(
                "non_contiguous_feature_slices",
                "Encoded feature slices must form an exact ordered partition of 0..P-1.",
            )

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform raw validated matrix ``(n, M)`` into encoded matrix ``(n, P)``."""
        arr = np.asarray(X, dtype=np.float64)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.ndim != 2 or arr.shape[1] != self.n_raw_features:
            raise PreprocessingContractError(
                "invalid_transform_shape",
                "Input matrix column count does not match fitted preprocessor.",
            )
        if np.isinf(arr).any():
            raise PreprocessingContractError(
                "infinite_transform_value",
                "Infinite values are forbidden at transform time.",
            )

        out = np.zeros((arr.shape[0], self.n_encoded_features), dtype=np.float64)
        for col_idx, ft in enumerate(self.field_transforms):
            col = arr[:, col_idx]
            is_nan = np.isnan(col)
            if ft.required and bool(is_nan.any()):
                raise PreprocessingContractError(
                    "missing_required_transform_value",
                    f"Required feature '{ft.name}' is missing at transform time.",
                    field=ft.name,
                )
            if ft.role == "numeric":
                assert ft.impute_median is not None
                assert ft.scale_mean is not None
                assert ft.scale_std is not None
                filled = np.where(is_nan, ft.impute_median, col)
                z = (filled - ft.scale_mean) / ft.scale_std
                out[:, ft.slice_indices[0]] = z
                if not ft.required:
                    out[:, ft.slice_indices[1]] = is_nan.astype(np.float64)
            else:
                assert ft.impute_mode_code is not None
                filled = np.where(is_nan, float(ft.impute_mode_code), col)
                filled_int = filled.astype(np.int64)
                if not np.all(filled_int == filled) or not set(
                    filled_int.tolist()
                ).issubset(set(ft.categorical_codes)):
                    raise PreprocessingContractError(
                        "unknown_categorical_transform_code",
                        f"Categorical column '{ft.name}' contains unregistered codes at transform time.",
                        field=ft.name,
                    )
                non_ref_codes = ft.categorical_codes[1:]
                for offset, code in enumerate(non_ref_codes):
                    out[:, ft.slice_indices[offset]] = (filled_int == code).astype(
                        np.float64
                    )
                if not ft.required:
                    out[:, ft.slice_indices[-1]] = is_nan.astype(np.float64)
        return out

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PREPROCESSING_SCHEMA_VERSION,
            "preprocessing_version": "1.0.0",
            "panel_id": self.panel_id,
            "panel_contract_sha256": self.panel_contract_sha256,
            "n_training_rows": self.n_training_rows,
            "encoded_feature_names": list(self.encoded_feature_names),
            "field_transforms": [ft.to_json_dict() for ft in self.field_transforms],
        }

    def to_canonical_json_bytes(self) -> bytes:
        return (
            json.dumps(
                self.to_json_dict(),
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")

    @property
    def state_sha256(self) -> str:
        return hashlib.sha256(self.to_canonical_json_bytes()).hexdigest()

    @classmethod
    def from_json_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        expected_panel: ResearchPanelContract | None = None,
    ) -> "FoldSafeClinicalPreprocessor":
        if not isinstance(payload, Mapping):
            raise PreprocessingContractError(
                "malformed_preprocessing_json",
                "Serialized preprocessor state must be a JSON object.",
            )
        if payload.get("schema_version") != PREPROCESSING_SCHEMA_VERSION:
            raise PreprocessingContractError(
                "unsupported_preprocessing_schema",
                "Unsupported preprocessing JSON schema version.",
            )
        panel_id = str(payload.get("panel_id", ""))
        panel = expected_panel if expected_panel is not None else get_panel_contract(panel_id)
        raw_transforms = payload.get("field_transforms")
        raw_encoded = payload.get("encoded_feature_names")
        if not isinstance(raw_transforms, list) or not isinstance(raw_encoded, list):
            raise PreprocessingContractError(
                "malformed_preprocessing_json",
                "Preprocessor JSON is missing field_transforms or encoded_feature_names.",
            )

        transforms: list[FittedFieldTransform] = []
        for entry in raw_transforms:
            if not isinstance(entry, Mapping):
                raise PreprocessingContractError(
                    "malformed_preprocessing_json",
                    "Invalid field_transform entry in preprocessing JSON.",
                )
            transforms.append(
                FittedFieldTransform(
                    name=str(entry["name"]),
                    role=str(entry["role"]),
                    required=bool(entry["required"]),
                    encoded_columns=tuple(str(c) for c in entry["encoded_columns"]),
                    slice_indices=tuple(int(i) for i in entry["slice_indices"]),
                    impute_median=(
                        None
                        if entry["impute_median"] is None
                        else float(entry["impute_median"])
                    ),
                    scale_mean=(
                        None
                        if entry["scale_mean"] is None
                        else float(entry["scale_mean"])
                    ),
                    scale_std=(
                        None
                        if entry["scale_std"] is None
                        else float(entry["scale_std"])
                    ),
                    categorical_codes=tuple(int(c) for c in entry["categorical_codes"]),
                    impute_mode_code=(
                        None
                        if entry["impute_mode_code"] is None
                        else int(entry["impute_mode_code"])
                    ),
                )
            )

        instance = cls(
            panel_id=panel_id,
            panel_contract_sha256=str(payload.get("panel_contract_sha256", "")),
            n_training_rows=int(payload.get("n_training_rows", 0)),
            field_transforms=tuple(transforms),
            encoded_feature_names=tuple(str(c) for c in raw_encoded),
        )
        instance._verify_lineage_invariants(panel)
        return instance
