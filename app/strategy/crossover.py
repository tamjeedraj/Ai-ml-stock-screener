import math


def _valid_number(value):

    try:

        value = float(value)

        if not math.isfinite(value):
            return False

        return True

    except Exception:

        return False


def detect_crossover(
    previous,
    current
):

    # ------------------------------------------
    # First observation
    # ------------------------------------------

    if previous is None:
        return None

    if not isinstance(
        previous,
        dict
    ):
        return None

    if not isinstance(
        current,
        dict
    ):
        return None

    # ------------------------------------------
    # Read indicators
    # ------------------------------------------

    previous_20 = previous.get(
        "smma20"
    )

    previous_120 = previous.get(
        "smma120"
    )

    current_20 = current.get(
        "smma20"
    )

    current_120 = current.get(
        "smma120"
    )

    # ------------------------------------------
    # Validate values
    # ------------------------------------------

    if not all(
        _valid_number(value)
        for value in [
            previous_20,
            previous_120,
            current_20,
            current_120,
        ]
    ):
        return None

    previous_20 = float(
        previous_20
    )

    previous_120 = float(
        previous_120
    )

    current_20 = float(
        current_20
    )

    current_120 = float(
        current_120
    )

    # ------------------------------------------
    # BUY crossover
    #
    # Previous:
    # SMMA20 <= SMMA120
    #
    # Current:
    # SMMA20 > SMMA120
    # ------------------------------------------

    if (
        previous_20 <= previous_120
        and
        current_20 > current_120
    ):

        return "BUY"

    # ------------------------------------------
    # SELL crossover
    #
    # Previous:
    # SMMA20 >= SMMA120
    #
    # Current:
    # SMMA20 < SMMA120
    # ------------------------------------------

    if (
        previous_20 >= previous_120
        and
        current_20 < current_120
    ):

        return "SELL"

    # ------------------------------------------
    # No new crossover
    # ------------------------------------------

    return None