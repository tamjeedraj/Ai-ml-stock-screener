import os

import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report
)


FEATURES = [
    "ltq_ratio",
    "etq_5m",
    "etq_20m",
    "etq_60m",
    "smma_distance",
    "order_imbalance",
    "ltp",
    "bid_qty",
    "ask_qty"
]


def train_model(
    df,
    model_path
):

    df = df.dropna(
        subset=FEATURES + ["label"]
    )

    if len(df) < 20:

        raise ValueError(
            "At least 20 completed "
            "crossover samples are required."
        )

    X = df[FEATURES].copy()

    y = (
        df["label"]
        .astype(int)
    )

    if y.nunique() < 2:

        raise ValueError(
            "Training data must contain "
            "both profitable and losing trades."
        )

    X_train, X_test, y_train, y_test = (
        train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42,
            stratify=y
        )
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )

    model.fit(
        X_train,
        y_train
    )

    predictions = model.predict(
        X_test
    )

    accuracy = accuracy_score(
        y_test,
        predictions
    )

    print(
        classification_report(
            y_test,
            predictions,
            zero_division=0
        )
    )

    directory = os.path.dirname(
        model_path
    )

    if directory:

        os.makedirs(
            directory,
            exist_ok=True
        )

    joblib.dump(
        {
            "model": model,
            "features": FEATURES,
            "accuracy": accuracy
        },
        model_path
    )

    print(
        "Model accuracy:",
        accuracy
    )

    return model, accuracy