import os

import joblib
import pandas as pd


class MLPredictor:

    def __init__(
        self,
        model_path
    ):

        self.model_path = model_path
        self.bundle = None

        if os.path.exists(
            model_path
        ):

            try:

                self.bundle = joblib.load(
                    model_path
                )

            except Exception as error:

                print(
                    "Model load error:",
                    error
                )

                self.bundle = None

    def predict(
        self,
        features
    ):

        if self.bundle is None:

            return {
                "probability": None,
                "decision": "MODEL_NOT_READY",
                "reason": (
                    "ML model is waiting for "
                    "profitable and losing crossover samples."
                )
            }

        try:

            model = self.bundle["model"]

            columns = self.bundle["features"]

            values = []

            for column in columns:

                value = features.get(
                    column,
                    0
                )

                try:

                    value = float(value)

                except Exception:

                    value = 0.0

                values.append(value)

            X = pd.DataFrame(
                [values],
                columns=columns
            )

            probabilities = (
                model.predict_proba(
                    X
                )[0]
            )

            classes = model.classes_

            probability_map = dict(
                zip(
                    classes,
                    probabilities
                )
            )

            profitable_probability = float(
                probability_map.get(
                    1,
                    0
                )
            )

            if profitable_probability >= 0.65:

                decision = "ACCEPT"

                reason = (
                    "ML confidence is above "
                    "the 65% acceptance threshold."
                )

            else:

                decision = "AVOID"

                reason = (
                    "ML confidence is below "
                    "the 65% acceptance threshold."
                )

            return {
                "probability":
                    profitable_probability,

                "decision":
                    decision,

                "reason":
                    reason
            }

        except Exception as error:

            return {
                "probability": None,
                "decision": "MODEL_NOT_READY",
                "reason": (
                    "ML prediction error: "
                    + str(error)
                )
            }