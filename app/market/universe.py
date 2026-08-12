import os
import pandas as pd


class NSEUniverse:

    def __init__(
        self,
        csv_path="data/nse_symbols.csv"
    ):
        self.csv_path = csv_path
        self.df = None

    # ==================================================
    # LOAD NSE UNIVERSE
    # ==================================================

    def load(self):

        if not os.path.exists(
            self.csv_path
        ):
            raise FileNotFoundError(
                f"NSE symbol file not found: "
                f"{self.csv_path}"
            )

        try:

            self.df = pd.read_csv(
                self.csv_path
            )

        except Exception as error:

            raise RuntimeError(
                f"Unable to read NSE symbol file: "
                f"{error}"
            )

        # Normalize column names
        self.df.columns = [
            str(column)
            .strip()
            .lower()
            for column in self.df.columns
        ]

        required = {
            "symbol",
            "token",
            "exchange"
        }

        missing = (
            required
            - set(self.df.columns)
        )

        if missing:

            raise ValueError(
                "NSE CSV missing required "
                f"columns: {sorted(missing)}"
            )

        # ==================================================
        # CLEAN DATA
        # ==================================================

        self.df["exchange"] = (
            self.df["exchange"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        self.df["symbol"] = (
            self.df["symbol"]
            .astype(str)
            .str.strip()
        )

        self.df["token"] = (
            self.df["token"]
            .astype(str)
            .str.strip()
        )

        # ==================================================
        # NSE ONLY
        # ==================================================

        self.df = self.df[
            self.df["exchange"].eq("NSE")
        ].copy()

        # Remove empty rows
        self.df = self.df[
            (self.df["symbol"] != "")
            &
            (self.df["token"] != "")
            &
            (self.df["symbol"].str.lower() != "nan")
            &
            (self.df["token"].str.lower() != "nan")
        ].copy()

        # ==================================================
        # CLEAN TOKEN
        # ==================================================

        self.df["token"] = (
            self.df["token"]
            .str.replace(
                ".0",
                "",
                regex=False
            )
        )

        # ==================================================
        # REMOVE DUPLICATE TOKENS
        # ==================================================

        self.df = (
            self.df
            .drop_duplicates(
                subset=["token"],
                keep="first"
            )
            .reset_index(drop=True)
        )

        if self.df.empty:

            raise ValueError(
                "No NSE instruments found "
                "in the universe file."
            )

        print(
            "================================"
        )

        print(
            "NSE UNIVERSE LOADED"
        )

        print(
            "CSV:",
            self.csv_path
        )

        print(
            "NSE instruments:",
            len(self.df)
        )

        print(
            "================================"
        )

        return self.df

    # ==================================================
    # GET TOKENS
    # ==================================================

    def get_tokens(self):

        if self.df is None:
            self.load()

        return self.df.to_dict(
            "records"
        )

    # ==================================================
    # TOKEN -> SYMBOL
    # ==================================================

    def get_token_map(self):

        if self.df is None:
            self.load()

        return {
            str(row["token"]): str(
                row["symbol"]
            )
            for row in self.df.to_dict(
                "records"
            )
        }

    # ==================================================
    # SYMBOL -> TOKEN
    # ==================================================

    def get_symbol_map(self):

        if self.df is None:
            self.load()

        return {
            str(row["symbol"]): str(
                row["token"]
            )
            for row in self.df.to_dict(
                "records"
            )
        }

    # ==================================================
    # FIND SYMBOL
    # ==================================================

    def get_symbol(
        self,
        token
    ):

        if self.df is None:
            self.load()

        token = str(token)

        result = self.df[
            self.df["token"].eq(token)
        ]

        if result.empty:
            return None

        return str(
            result.iloc[0]["symbol"]
        )

    # ==================================================
    # FIND TOKEN
    # ==================================================

    def get_token(
        self,
        symbol
    ):

        if self.df is None:
            self.load()

        symbol = str(
            symbol
        ).strip()

        result = self.df[
            self.df["symbol"].eq(symbol)
        ]

        if result.empty:
            return None

        return str(
            result.iloc[0]["token"]
        )