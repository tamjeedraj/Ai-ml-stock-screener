import pyotp

from SmartApi import SmartConnect

from app.config import settings


class AngelOneClient:

    def __init__(self):
        self.smart_api = None
        self.auth_token = None
        self.feed_token = None

    def login(self):

        if not settings.ANGEL_API_KEY:
            raise RuntimeError(
                "ANGEL_API_KEY is missing"
            )

        self.smart_api = SmartConnect(
            api_key=settings.ANGEL_API_KEY
        )

        totp = pyotp.TOTP(
            settings.ANGEL_TOTP
        ).now()

        session = self.smart_api.generateSession(
            settings.ANGEL_CLIENT_CODE,
            settings.ANGEL_PASSWORD,
            totp
        )

        if not session.get("status"):
            raise RuntimeError(
                f"Angel One login failed: {session}"
            )

        data = session["data"]

        self.auth_token = data["jwtToken"]

        self.feed_token = (
            self.smart_api.getfeedToken()
        )

        return {
            "auth_token": self.auth_token,
            "feed_token": self.feed_token
        }

    def historical_data(
        self,
        exchange,
        symbol_token,
        interval,
        from_date,
        to_date
    ):

        params = {
            "exchange": exchange,
            "symboltoken": str(symbol_token),
            "interval": interval,
            "fromdate": from_date,
            "todate": to_date
        }

        return self.smart_api.getCandleData(
            params
        )

    def market_quote(
        self,
        exchange_tokens,
        mode="FULL"
    ):

        if not exchange_tokens:
            return {
                "fetched": [],
                "unfetched": []
            }

        response = self.smart_api.getMarketData(
            mode,
            {
                "NSE": [
                    str(token)
                    for token in exchange_tokens
                ]
            }
        )

        if not response:
            return {
                "fetched": [],
                "unfetched": []
            }

        return response.get(
            "data",
            {
                "fetched": [],
                "unfetched": []
            }
        )