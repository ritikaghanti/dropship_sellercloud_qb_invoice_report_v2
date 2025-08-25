# decimal_rounding.py (kept)
from decimal import Decimal, ROUND_HALF_UP


def round_to_decimal(number):
    decimal_number = Decimal(str(number))
    rounded_number = decimal_number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(rounded_number)
