from decimal import Decimal
from moneycalc.money import money

class TaxEffect(object):
    CASH_INCOME = 'CASH_INCOME'
    CASH_WITHHELD = 'CASH_WITHHELD'
    DEDUCTIBLE = 'DEDUCTIBLE'
    NONE = 'NONE'

def us_tax_rate(year, amount):
    # TODO(strager): Account for year.
    if amount < 9276:
        return Decimal('0.10')
    if amount < 37651:
        return Decimal('0.15')
    if amount < 91151:
        return Decimal('0.25')
    if amount < 190151:
        return Decimal('0.28')
    if amount < 413351:
        return Decimal('0.33')
    if amount < 415051:
        return Decimal('0.35')
    return Decimal('0.396')

def ca_tax_rate(year, amount):
    # TODO(strager): Account for year.
    if amount < 7749:
        return Decimal('0.01')
    if amount < 18371:
        return Decimal('0.02')
    if amount < 28995:
        return Decimal('0.04')
    if amount < 40250:
        return Decimal('0.06')
    if amount < 50689:
        return Decimal('0.08')
    if amount < 259844:
        return Decimal('0.093')
    if amount < 311812:
        return Decimal('0.103')
    if amount < 519867:
        return Decimal('0.113')
    if amount < 1000000:
        return Decimal('0.123')
    return Decimal('0.133')

def tax_due(events, year):
    taxable_cash_income = sum(event.amount for event in events if event.tax_effect == TaxEffect.CASH_INCOME)
    withheld_cash = sum(-event.amount for event in events if event.tax_effect == TaxEffect.CASH_WITHHELD)
    deductible = sum(event.amount for event in events if event.tax_effect == TaxEffect.DEDUCTIBLE)
    tax_rate = us_tax_rate(year=year, amount=taxable_cash_income) + ca_tax_rate(year=year, amount=taxable_cash_income)
    taxable_income = max((taxable_cash_income - deductible, money(0)))
    total_due = money(taxable_income * tax_rate)
    net_due = total_due - withheld_cash
    return net_due
