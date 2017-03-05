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

def iter_salary_funcs(timeline, start_date, to_account):
    def salary_func(date):
        base_salary_income = money('7135.87')
        bonus_income = money(0) # TODO(strager)
        gross_income = base_salary_income + bonus_income

        withheld_401k = money(0) # TODO(strager)
        taxable_income = gross_income - withheld_401k
        withheld_us_income_tax = money(taxable_income * Decimal(0.215)) # FIXME(strager)
        withheld_ca_income_tax = money(taxable_income * Decimal(0.080)) # FIXME(strager)
        other_tax = money(taxable_income * Decimal(0.15)) # FIXME(strager)
        net_income = gross_income - withheld_401k - withheld_us_income_tax - withheld_ca_income_tax - other_tax
        # TODO(strager): 401k.

        timeline.add_withheld_cash(date=date, amount=withheld_us_income_tax, description='Salary (withheld US tax)')
        timeline.add_withheld_cash(date=date, amount=withheld_ca_income_tax, description='Salary (withheld CA tax)')
        timeline.add_income(date=date, amount=taxable_income, description='Salary (taxable)')
        to_account.deposit(timeline=timeline, date=date, amount=net_income, description='Salary (net)')

    now = start_date
    while True:
        yield (now, salary_func)
        now += datetime.timedelta(days=2 * 7)

def main():
    timeline = moneycalc.timeline.Timeline()
    heloc = moneycalc.account.LineOfCreditAccount(
        name='HELOC',
        interest_rate=moneycalc.account.VariableDailyInterestRate(
            prime_rate=moneycalc.account.YearlySteppingPrimeRate(
                start_yearly_rate=Decimal('0.0425'),
                start_year=2017,
                yearly_increase=Decimal('0.005'),
            )
        ),
        draw_term=moneycalc.time.Period(datetime.date(2017, 1, 1), datetime.date(2027, 1, 1)),
        repayment_term=moneycalc.time.Period(datetime.date(2027, 1, 1), datetime.date(2047, 1, 1)),
    )
    heloc.withdraw(timeline=timeline, date=datetime.date(2017, 1, 1), amount=money('975000.00'), description='Purchase')

    start_date = datetime.date(year=2017, month=1, day=1)
    end_date = datetime.date(year=2027, month=1, day=1)

    tax_payment_funcs = []
    def tax_payment_func(date):
        tax_year = date.year - 1
        tax_period = moneycalc.time.Period(datetime.date(year=tax_year, month=1, day=1), datetime.date(year=tax_year + 1, month=1, day=1))
        due = moneycalc.tax.tax_due(events=[event for event in timeline if event.date in tax_period and event.tax_effect != moneycalc.tax.TaxEffect.NONE], year=tax_year)
        if due < 0:
            # TODO(strager): Treat as income.
            heloc.deposit(timeline=timeline, date=date, amount=-due, description='Tax refund')
        else:
            heloc.withdraw(timeline=timeline, date=date, amount=due, description='Taxes')
    tax_payment_funcs = ((datetime.date(year=year, month=4, day=1), tax_payment_func) for year in xrange(start_date.year, end_date.year + 1))

    salary_funcs = iter_salary_funcs(timeline=timeline, start_date=start_date, to_account=heloc)

    for (date, func) in moneycalc.util.iter_merge_sort([tax_payment_funcs, salary_funcs], key=lambda (date, func): date):
        if date > end_date:
            break
        func(date)

    sys.stdout.write('Timeline:\n\n')
    for event in timeline:
        sys.stdout.write('{}\n'.format(event))

if __name__ == '__main__':
    main()
