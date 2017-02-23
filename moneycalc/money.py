from decimal import Decimal
import decimal

money_context = decimal.BasicContext.copy()
money_context.prec = 20
money_context.rounding = decimal.ROUND_HALF_UP # FIXME(strager)

def money(amount):
    return Decimal(amount).quantize(Decimal('0.01'), context=money_context)
