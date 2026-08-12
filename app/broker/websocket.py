from SmartApi.smartWebSocketV2 import SmartWebSocketV2


class AngelWebSocket:

    def __init__(
        self,
        auth_token,
        api_key,
        client_code,
        feed_token,
        on_tick
    ):

        self.on_tick_callback = on_tick
        self.tokens = []

        self.ws = SmartWebSocketV2(
            auth_token,
            api_key,
            client_code,
            feed_token,
            max_retry_attempt=3,
            retry_strategy=0,
            retry_delay=10,
            retry_duration=60
        )

        self.ws.on_data = self.on_data
        self.ws.on_open = self.on_open
        self.ws.on_error = self.on_error
        self.ws.on_close = self.on_close

    def on_open(self, wsapp):

        print(
            "Angel One WebSocket connected"
        )

        if self.tokens:
            self._subscribe()

    def on_data(self, wsapp, message):

        if not isinstance(message, dict):
            return

        try:
            self.on_tick_callback(message)

        except Exception as error:

            print(
                "Tick callback error:",
                error
            )

    def on_error(self, wsapp, error):

        print(
            "WebSocket error:",
            error
        )

    def on_close(self, wsapp):

        print(
            "WebSocket closed"
        )

    def _subscribe(self):

        if not self.tokens:
            return

        token_list = [
            {
                "exchangeType": 1,
                "tokens": self.tokens
            }
        ]

        try:

            self.ws.subscribe(
                "nse-screener",
                self.ws.SNAP_QUOTE,
                token_list
            )

            print(
                "Subscribed tokens:",
                len(self.tokens)
            )

        except Exception as error:

            print(
                "Subscription error:",
                error
            )

    def subscribe(self, tokens):

        self.tokens = [
            str(token)
            for token in tokens
        ]

        if (
            getattr(self.ws, "wsapp", None)
            is not None
        ):

            self._subscribe()

    def connect(self):

        print(
            "Connecting to Angel One WebSocket..."
        )

        self.ws.connect()

    def close(self):

        try:
            self.ws.close_connection()
        except Exception:
            pass