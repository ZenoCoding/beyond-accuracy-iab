"""Rebuild initial translation features after claim corrections.

Feature definitions follow ``scripts/analyze_reasoning_features.py`` and
``scripts/remake_size6_auc.py``.  The original input and feature table are
checked on every call before corrected claims are applied, so a changed source
schema or definition cannot silently rewrite the frozen baseline.

The helper changes the eight claim-derived initial columns and the two
first-introduction counts that depend on the full claim sequence in size-6
rows. Outcome fields, initial-answer fields, and other later-debate features
remain as supplied in ``base_features_dataframe``.
"""

from pathlib import Path

import numpy as np
import pandas as pd


SUPPORT_DIR = Path(__file__).resolve().parent
FROZEN_CLAIMS_CSV = SUPPORT_DIR / "control-inputs" / "claims.csv"
FROZEN_FEATURES_CSV = SUPPORT_DIR / "debate-features.csv"

KEY = ["condition_id", "task_id", "repetition"]
COMMITMENTS = ["assert", "endorse", "reject"]
SCORED = ["truth_aligned", "misleading", "redundant", "contradictory"]
INITIAL_FEATURES = [
    "initial_distinct",
    "initial_true",
    "initial_false",
    "initial_precision",
    "initial_true_bits",
    "initial_false_bits",
    "initial_net_bits",
    "initial_correct_propositions",
]
INTRODUCTION_FEATURES = [
    "post_initial_distinct",
    "post_initial_distinct_before_final",
]
REBUILT_FEATURES = [*INITIAL_FEATURES, *INTRODUCTION_FEATURES]
EXPECTED_SIZE6_DEBATES = 80
BASELINE_RTOL = 1e-10
BASELINE_ATOL = 1e-10

CLAIM_COLUMNS = [
    *KEY,
    "stage_order",
    "commitment",
    "information_type",
    "effective_expression",
    "expression",
    "information_bits",
    "target_truth",
]


def _key_set(frame: pd.DataFrame, source_name: str) -> set[tuple]:
    missing = [column for column in KEY if column not in frame.columns]
    if missing:
        raise ValueError(f"{source_name} is missing debate key columns: {missing}")
    if frame[KEY].isna().any(axis=None):
        raise ValueError(f"{source_name} has null values in debate keys {KEY}")
    return set(map(tuple, frame[KEY].drop_duplicates().itertuples(index=False, name=None)))


def _validate_unique_debates(frame: pd.DataFrame, source_name: str) -> None:
    if frame.duplicated(KEY).any():
        examples = frame.loc[frame.duplicated(KEY, keep=False), KEY].head(4)
        raise ValueError(
            f"{source_name} must have one row per debate key; duplicates include "
            f"{examples.to_dict(orient='records')}"
        )


def _claims_with_expression(claims_dataframe: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in CLAIM_COLUMNS if column not in claims_dataframe.columns]
    if missing:
        raise ValueError(f"Claims data is missing required columns: {missing}")

    claims = claims_dataframe.copy()
    claims["stage_order"] = pd.to_numeric(claims["stage_order"], errors="coerce")
    if claims["stage_order"].isna().any():
        raise ValueError("Claims data contains null or non-numeric stage_order values")

    claims = claims.loc[
        claims.commitment.isin(COMMITMENTS) & claims.information_type.isin(SCORED)
    ].copy()
    # This is the source generator's effective-expression rule: use the
    # effective expression when present, otherwise fall back to the expression.
    claims["expr"] = claims.effective_expression.fillna(claims.expression)
    return claims


def _derive_initial_features(claims_dataframe: pd.DataFrame) -> pd.DataFrame:
    """Apply archived initial-supply and first-introduction definitions."""
    claims = _claims_with_expression(claims_dataframe)
    initial = claims.loc[claims.stage_order.eq(0)].copy()

    rows = []
    for key, group in initial.groupby(KEY):
        # Match the original initial_features() generator: deduplicate exact
        # effective expressions within the debate, then take each expression's
        # first information type and information_bits value.
        props = group.groupby("expr").agg(
            kind=("information_type", "first"),
            bits=("information_bits", "first"),
        )
        counts = props.kind.value_counts()
        bits = props.groupby("kind").bits.sum()
        n_true = int(counts.get("truth_aligned", 0))
        n_false = int(counts.get("misleading", 0))
        signed = n_true + n_false
        true_bits = float(bits.get("truth_aligned", 0.0))
        false_bits = float(bits.get("misleading", 0.0))
        rows.append(
            dict(
                zip(KEY, key),
                initial_distinct=int(len(props)),
                initial_true=n_true,
                initial_false=n_false,
                initial_precision=n_true / signed if signed else np.nan,
                initial_true_bits=true_bits,
                initial_false_bits=false_bits,
                initial_net_bits=true_bits - false_bits,
            )
        )

    initial_features = pd.DataFrame(
        rows,
        columns=[
            *KEY,
            "initial_distinct",
            "initial_true",
            "initial_false",
            "initial_precision",
            "initial_true_bits",
            "initial_false_bits",
            "initial_net_bits",
        ],
    )

    # Both source scripts count on one first-occurrence row per exact effective
    # expression across the full debate. Thus initial_correct_propositions
    # counts only expressions first introduced at stage 0; a later expression
    # cannot increase it. The two post-initial counts do depend on initial rows:
    # changing an initial assertion can move a duplicate expression's first
    # occurrence from one side of the initial/later boundary to the other.
    first = claims.sort_values("stage_order").drop_duplicates(KEY + ["expr"])
    correct = (
        first.loc[first.stage_order.eq(0) & first.target_truth.eq(1)]
        .groupby(KEY)
        .size()
        .rename("initial_correct_propositions")
        .reset_index()
    )

    post_initial = first.loc[first.stage_order.gt(0)].groupby(KEY).size()
    post_initial.name = "post_initial_distinct"
    post_initial = post_initial.reset_index()
    post_initial_before_final = first.loc[
        first.stage_order.gt(0) & first.stage.ne("final_decision")
    ].groupby(KEY).size()
    post_initial_before_final.name = "post_initial_distinct_before_final"
    post_initial_before_final = post_initial_before_final.reset_index()

    features = claims[KEY].drop_duplicates().merge(
        initial_features, on=KEY, how="left", validate="one_to_one"
    )
    features = features.merge(correct, on=KEY, how="left", validate="one_to_one")
    features = features.merge(post_initial, on=KEY, how="left", validate="one_to_one")
    features = features.merge(
        post_initial_before_final, on=KEY, how="left", validate="one_to_one"
    )
    features["initial_correct_propositions"] = (
        features.initial_correct_propositions.fillna(0).astype(int)
    )
    for column in INTRODUCTION_FEATURES:
        features[column] = features[column].fillna(0).astype(int)
    return features


def _numeric_values(series: pd.Series, column: str, source_name: str) -> np.ndarray:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    invalid = series.notna().to_numpy() & np.isnan(values)
    if invalid.any():
        raise ValueError(f"{source_name}.{column} contains non-numeric feature values")
    return values


def _compare_feature_tables(
    observed: pd.DataFrame,
    expected: pd.DataFrame,
    *,
    observed_name: str,
    rtol: float = BASELINE_RTOL,
    atol: float = BASELINE_ATOL,
) -> None:
    missing = [column for column in [*KEY, *REBUILT_FEATURES] if column not in observed]
    if missing:
        raise ValueError(f"{observed_name} is missing frozen feature columns: {missing}")
    _validate_unique_debates(observed, observed_name)

    expected_keys = _key_set(expected, "Recomputed frozen features")
    observed_keys = _key_set(observed, observed_name)
    if observed_keys != expected_keys:
        missing_keys = sorted(expected_keys - observed_keys)[:4]
        extra_keys = sorted(observed_keys - expected_keys)[:4]
        raise ValueError(
            f"{observed_name} debate keys differ from the 80-debate frozen source; "
            f"missing={missing_keys}, extra={extra_keys}"
        )

    compared = observed[[*KEY, *REBUILT_FEATURES]].merge(
        expected[[*KEY, *REBUILT_FEATURES]],
        on=KEY,
        how="inner",
        suffixes=("_observed", "_expected"),
        validate="one_to_one",
    )
    problems = []
    for column in REBUILT_FEATURES:
        left = _numeric_values(compared[f"{column}_observed"], column, observed_name)
        right = _numeric_values(compared[f"{column}_expected"], column, "Recomputed")
        matches = np.isclose(
            left, right, rtol=rtol, atol=atol, equal_nan=True
        )
        if not matches.all():
            rows = compared.loc[~matches, KEY + [f"{column}_observed", f"{column}_expected"]]
            examples = rows.head(3).to_dict(orient="records")
            problems.append(f"{column}: {int((~matches).sum())} mismatches; {examples}")
    if problems:
        raise ValueError(
            f"Frozen-feature validation failed for {observed_name} at tolerance "
            f"rtol={rtol:g}, atol={atol:g}: " + "; ".join(problems)
        )


def _verify_original_frozen_baseline(
    base_features_dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, set[tuple]]:
    """Check the archived claims CSV against the frozen table before rebuilding."""
    if not FROZEN_CLAIMS_CSV.is_file():
        raise FileNotFoundError(f"Frozen claims input is missing: {FROZEN_CLAIMS_CSV}")
    if not FROZEN_FEATURES_CSV.is_file():
        raise FileNotFoundError(f"Frozen debate-feature table is missing: {FROZEN_FEATURES_CSV}")

    frozen_claims = pd.read_csv(FROZEN_CLAIMS_CSV, low_memory=False)
    frozen_features = pd.read_csv(FROZEN_FEATURES_CSV, low_memory=False)
    claim_keys = _key_set(frozen_claims, str(FROZEN_CLAIMS_CSV))
    if len(claim_keys) != EXPECTED_SIZE6_DEBATES:
        raise ValueError(
            "Frozen claims input must contain exactly the 80 size-6 debate keys; "
            f"found {len(claim_keys)}"
        )
    frozen_features6 = frozen_features.loc[
        frozen_features[KEY].apply(tuple, axis=1).isin(claim_keys)
    ].copy()
    frozen_feature_keys = _key_set(frozen_features6, str(FROZEN_FEATURES_CSV))
    if len(frozen_features6) != EXPECTED_SIZE6_DEBATES or frozen_feature_keys != claim_keys:
        raise ValueError(
            "Frozen feature table does not contain exactly the 80 size-6 debate "
            f"keys from {FROZEN_CLAIMS_CSV}; matched rows={len(frozen_features6)}, "
            f"matched keys={len(frozen_feature_keys)}"
        )

    recomputed = _derive_initial_features(frozen_claims)
    # Align the recomputed metrics to every frozen size-6 key before checking.
    recomputed = frozen_features6[KEY].merge(
        recomputed, on=KEY, how="left", validate="one_to_one"
    )
    recomputed["initial_correct_propositions"] = (
        recomputed.initial_correct_propositions.fillna(0).astype(int)
    )
    for column in INTRODUCTION_FEATURES:
        recomputed[column] = recomputed[column].fillna(0).astype(int)
    missing_metrics = [
        column
        for column in REBUILT_FEATURES
        if column not in recomputed.columns
    ]
    if missing_metrics:
        raise ValueError(f"Could not recompute frozen initial features: {missing_metrics}")

    # First validate the checked-in frozen table against its original claims.
    _compare_feature_tables(
        frozen_features6,
        recomputed,
        observed_name="checked-in frozen debate-features.csv",
    )

    # Then require the caller's base table to contain those same original rows
    # and values before any corrected claims are applied.
    base_keys = _key_set(base_features_dataframe, "base_features_dataframe")
    if not claim_keys.issubset(base_keys):
        absent = sorted(claim_keys - base_keys)[:4]
        raise ValueError(
            "base_features_dataframe is missing frozen size-6 debates; "
            f"examples: {absent}"
        )
    base_size6 = base_features_dataframe.loc[
        base_features_dataframe[KEY].apply(tuple, axis=1).isin(claim_keys)
    ].copy()
    if len(base_size6) != EXPECTED_SIZE6_DEBATES:
        raise ValueError(
            "base_features_dataframe must contain each frozen size-6 debate exactly "
            f"once; found {len(base_size6)} rows"
        )
    _compare_feature_tables(
        base_size6,
        frozen_features6,
        observed_name="base_features_dataframe size-6 rows",
    )
    return frozen_features6, claim_keys


def rebuild_features(
    base_features_dataframe: pd.DataFrame,
    claims_dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Rebuild initial features and later first-introduction counts for size 6.

    The frozen input claims and frozen feature table are revalidated first.
    ``claims_dataframe`` must retain the same debate keys as that frozen source;
    it may contain corrected claim rows for those debates. All other base rows
    and columns are preserved.
    """
    # This is deliberately the first operation: verify the original 80-row
    # feature baseline from the preserved input claims before using corrections.
    _, frozen_keys = _verify_original_frozen_baseline(base_features_dataframe)

    corrected_keys = _key_set(claims_dataframe, "claims_dataframe")
    if corrected_keys != frozen_keys:
        missing = sorted(frozen_keys - corrected_keys)[:4]
        extra = sorted(corrected_keys - frozen_keys)[:4]
        raise ValueError(
            "Corrected claims must preserve the exact frozen size-6 debate keys; "
            f"missing={missing}, extra={extra}"
        )

    rebuilt = _derive_initial_features(claims_dataframe)
    rebuilt = base_features_dataframe[KEY].merge(
        rebuilt, on=KEY, how="left", validate="one_to_one"
    )
    rebuilt["initial_correct_propositions"] = (
        rebuilt.initial_correct_propositions.fillna(0).astype(int)
    )

    result = base_features_dataframe.copy()
    target_rows = result[KEY].apply(tuple, axis=1).isin(frozen_keys)
    target_indices = np.flatnonzero(target_rows.to_numpy())
    updates = result.loc[target_rows, KEY].merge(
        rebuilt[[*KEY, *REBUILT_FEATURES]],
        on=KEY,
        how="left",
        validate="one_to_one",
        sort=False,
    )
    if len(target_indices) != EXPECTED_SIZE6_DEBATES or len(updates) != len(target_indices):
        raise ValueError(
            "Internal size-6 feature join failed: expected exactly 80 matched rows, "
            f"found {len(target_indices)} base rows and {len(updates)} updated rows"
        )
    for column in REBUILT_FEATURES:
        result.loc[target_rows, column] = updates[column].to_numpy()
    return result


if __name__ == "__main__":
    base_features = pd.read_csv(FROZEN_FEATURES_CSV, low_memory=False)
    original_claims = pd.read_csv(FROZEN_CLAIMS_CSV, low_memory=False)
    rebuilt = rebuild_features(base_features, original_claims)
    for column in REBUILT_FEATURES:
        old = pd.to_numeric(base_features[column], errors="coerce").to_numpy(float)
        new = pd.to_numeric(rebuilt[column], errors="coerce").to_numpy(float)
        if not np.isclose(old, new, rtol=BASELINE_RTOL, atol=BASELINE_ATOL, equal_nan=True).all():
            raise AssertionError(f"Original claims failed round-trip for {column}")
    print(
        "Frozen baseline verified: 80/80 size-6 debates, all ten rebuilt "
        f"features within rtol={BASELINE_RTOL:g}, atol={BASELINE_ATOL:g}."
    )
