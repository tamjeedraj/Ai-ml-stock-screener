import os

from dotenv import load_dotenv

load_dotenv()


class Settings:

    ANGEL_API_KEY = os.getenv(
        "ANGEL_API_KEY"
    )

    ANGEL_CLIENT_CODE = os.getenv(
        "ANGEL_CLIENT_CODE"
    )

    ANGEL_PASSWORD = os.getenv(
        "ANGEL_PASSWORD"
    )

    ANGEL_TOTP = os.getenv(
        "ANGEL_TOTP"
    )

    APP_ENV = os.getenv(
        "APP_ENV",
        "development"
    )

    MIN_LTP = 30.0
    MAX_LTP = 500.0

    MIN_BID_QTY = 1_000_000
    MIN_ASK_QTY = 1_000_000

    MODEL_PATH = (
        "data/models/crossover_model.joblib"
    )


settings = Settings()