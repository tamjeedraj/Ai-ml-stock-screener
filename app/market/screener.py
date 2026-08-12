from app.config import settings


def qualifies(tick):

    ltp = tick["ltp"]

    bid_qty = tick["bid_qty"]

    ask_qty = tick["ask_qty"]

    if not (
        settings.MIN_LTP
        <= ltp
        <= settings.MAX_LTP
    ):
        return False

    if bid_qty <= settings.MIN_BID_QTY:
        return False

    if ask_qty <= settings.MIN_ASK_QTY:
        return False

    return True


