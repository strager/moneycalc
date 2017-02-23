#!/usr/bin/env python2.7

from decimal import Decimal
from moneycalc.money import money
import datetime
import moneycalc.account
import moneycalc.tax
import moneycalc.time
import moneycalc.timeline
import moneycalc.util
import sys

def main():
    timeline = moneycalc.timeline.Timeline()
    loan = moneycalc.account.AmortizedMonthlyLoan(
        name='Mortgage',
        amount=money('975000.00'),
        interest_rate=moneycalc.account.FixedMonthlyInterestRate(yearly_rate=Decimal('0.04125')),
        term=moneycalc.time.Period(datetime.date(2017, 1, 1), datetime.date(2047, 1, 1)))
    checking = moneycalc.account.CheckingAccount(name='Checking')
    income = moneycalc.account.Income()

    begin_date = datetime.date(year=2016, month=1, day=1)
    end_date = datetime.date(year=2060, month=1, day=1)

    mortgage_payment_funcs = []
    def mortgage_payment_func(date):
        payment = money('4725.33')
        minimum_deposit = loan.minimum_deposit(date=date)
        if payment < minimum_deposit:
            payment = minimum_deposit
        moneycalc.account.transfer(timeline=timeline, date=date, from_account=checking, to_account=loan, amount=payment, description='Mortgage payment')
    now = loan.term.start_date
    while now < loan.term.end_date:
        mortgage_payment_funcs.append((now, mortgage_payment_func))
        now = moneycalc.time.add_month(now)

    tax_payment_funcs = []
    def tax_payment_func(date):
        tax_year = date.year - 1
        tax_period = moneycalc.time.Period(datetime.date(year=tax_year, month=1, day=1), datetime.date(year=tax_year + 1, month=1, day=1))
        due = moneycalc.tax.tax_due(events=[event for event in timeline if event.date in tax_period and event.tax_effect != moneycalc.tax.TaxEffect.NONE], year=tax_year)
        if due < 0:
            raise NotImplementedError()
        else:
            checking.withdraw(timeline=timeline, date=date, amount=due, description='Taxes')
    tax_payment_funcs = ((datetime.date(year=year, month=4, day=1), tax_payment_func) for year in xrange(begin_date.year, end_date.year + 1))

    def income_func(date):
        income.earn_cash(timeline=timeline, to_account=checking, date=date, gross_amount=money('999999.99'), net_amount=money('999999.99'), description='Life')
    income_funcs = ((datetime.date(year=year, month=1, day=1), income_func) for year in xrange(begin_date.year, end_date.year + 1))

    for (date, func) in moneycalc.util.iter_merge_sort([mortgage_payment_funcs, tax_payment_funcs, income_funcs], key=lambda (date, func): date):
        func(date)

    sys.stdout.write('Timeline:\n\n')
    for event in timeline:
        sys.stdout.write('{}\n'.format(event))

if __name__ == '__main__':
    main()
