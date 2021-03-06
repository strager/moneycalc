#!/usr/bin/env python2.7

from decimal import Decimal
from moneycalc.money import money
from moneycalc.tax import TaxEffect
import abc
import collections
import datetime
import moneycalc.account
import moneycalc.tax
import moneycalc.time
import moneycalc.timeline
import moneycalc.util
import sys
import traceback

def iter_salary_funcs(timeline, start_date, to_account):
    def receive_income(date, gross_income):
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

    def iter_base_salary_income_funcs():
        now = start_date
        while True:
            yield (now, lambda date: receive_income(date, money('7553.31')))
            now += datetime.timedelta(days=2 * 7)

    def iter_half_bonus_income_funcs():
        year = start_date.year
        while True:
            q1 = datetime.date(year=year, month=1, day=1)
            q3 = datetime.date(year=year, month=7, day=1)
            for now in [q1, q3]:
                if now >= start_date:
                    yield (now, lambda date: receive_income(date, money('14728.95')))
            year += 1

    def iter_quarter_bonus_income_funcs():
        year = start_date.year
        while True:
            q1 = datetime.date(year=year, month=1, day=1)
            q2 = datetime.date(year=year, month=4, day=1)
            q3 = datetime.date(year=year, month=7, day=1)
            q4 = datetime.date(year=year, month=10, day=1)
            for now in [q1, q2, q3, q3]:
                if now >= start_date:
                    yield (now, lambda date: receive_income(date, money('18750.00')))
            year += 1

    return moneycalc.util.iter_merge_sort([iter_base_salary_income_funcs(), iter_half_bonus_income_funcs(), iter_quarter_bonus_income_funcs()], key=lambda (date, func): date)

def iter_tax_payment_funcs(timeline, start_date, account):
    def tax_payment_func(date):
        tax_year = date.year - 1
        tax_period = moneycalc.time.Period(datetime.date(year=tax_year, month=1, day=1), datetime.date(year=tax_year + 1, month=1, day=1))
        due = moneycalc.tax.tax_due(events=[event for event in timeline if event.date in tax_period and event.tax_effect != moneycalc.tax.TaxEffect.NONE], year=tax_year)
        if due < 0:
            # TODO(strager): Treat as income.
            account.deposit(timeline=timeline, date=date, amount=-due, description='Tax refund')
        else:
            account.withdraw(timeline=timeline, date=date, amount=due, description='Taxes', tax_effect=TaxEffect.DEDUCTIBLE)
    year = start_date.year
    while True:
        yield (datetime.date(year=year, month=4, day=1), tax_payment_func)
        year += 1

def iter_expenses_funcs(timeline, start_date, account):
    def iter_misc_expenses_funcs():
        def expenses_func(date):
            account.withdraw(timeline=timeline, date=date, amount=money('1873.61'), description='Expenses')
        now = datetime.date(year=start_date.year, month=start_date.month, day=15)
        while True:
            yield (now, expenses_func)
            now = moneycalc.time.add_month(now)

    def iter_auto_funcs():
        # TODO(strager): Model as a loan.
        def auto_func(date):
            account.withdraw(timeline=timeline, date=date, amount=money('2225.70'), description='Auto')
        period = moneycalc.time.Period(
            datetime.date(year=2016, month=7, day=19),
            datetime.date(year=2021, month=7, day=19),
        )
        now = datetime.date(year=start_date.year, month=start_date.month, day=19)
        while now <= period.end_date:
            if now in period:
                yield (now, auto_func)
            now = moneycalc.time.add_month(now)

    return moneycalc.util.iter_merge_sort([iter_misc_expenses_funcs(), iter_auto_funcs()], key=lambda (date, func): date)

def iter_property_expense_funcs(timeline, start_date, account, home_value):
    def iter_tax_funcs():
        year = start_date.year
        tax_rate = Decimal('0.0074')
        def tax_func(date):
            amount = money(home_value * tax_rate / 2)
            account.withdraw(timeline=timeline, date=date, amount=amount, description='Property tax', tax_effect=TaxEffect.DEDUCTIBLE)
        while True:
            h1 = datetime.date(year=year, month=4, day=10)
            h2 = datetime.date(year=year, month=12, day=10)
            for now in [h1, h2]:
                if now >= start_date:
                    yield (now, tax_func)
            year += 1

    def iter_insurance_funcs():
        def insurance_func(date):
            account.withdraw(timeline=timeline, date=date, amount=money('1000.00'), description='Home insurance')
        now = datetime.date(year=start_date.year, month=start_date.month, day=1)
        while True:
            yield (now, insurance_func)
            now = moneycalc.time.add_month(now)

    return moneycalc.util.iter_merge_sort([iter_tax_funcs(), iter_insurance_funcs()], key=lambda (date, func): date)

class Scenario(object):
    def __init__(self):
        # timeline should not be used outside play.
        self.timeline = None

    def play(self):
        start_date = datetime.date(year=2017, month=1, day=1)
        end_date = datetime.date(year=2047, month=1, day=1)
        home_purchase_date = datetime.date(2017, 1, 1)
        home_purchase_amount = money('1200000.00')
        home_loan_amount = money('975000.00')
        home_appraisal_amount = home_purchase_amount

        self.timeline = moneycalc.timeline.Timeline()

        funcs = [
            self.__iter_year_summary_funcs(timeline=self.timeline, start_date=start_date),
            [(home_purchase_date, lambda date: self.purchase_home(date, home_loan_amount))],
            iter_tax_payment_funcs(timeline=self.timeline, start_date=start_date, account=self.primary_account),
            iter_salary_funcs(timeline=self.timeline, start_date=start_date, to_account=self.primary_account),
            iter_expenses_funcs(timeline=self.timeline, start_date=start_date, account=self.primary_account),
            iter_property_expense_funcs(timeline=self.timeline, start_date=start_date, account=self.primary_account, home_value=home_appraisal_amount),
            self.iter_activity_funcs(),
        ]
        for (date, func) in moneycalc.util.iter_merge_sort(funcs, key=lambda (date, func): date):
            if date > end_date:
                break
            try:
                func(date)
            except NotImplementedError:
                traceback.print_exc()
                break

        print_timeline = False
        if print_timeline:
            sys.stdout.write('Timeline:\n\n')
            for event in self.timeline:
                sys.stdout.write('{}\n'.format(event))

        self.timeline = None

    def __iter_year_summary_funcs(self, timeline, start_date):
        def year_summary_func(date):
            assert date.month == 1
            assert date.day == 1
            year = date.year - 1
            sys.stdout.write('Year {}:\n'.format(year))
            events = [e for e in timeline if e.date.year == year]
            for account in self.all_accounts:
                account_events = [e for e in events if e.account is account]
                sys.stdout.write('  {account}: {balance} balance ({deposited} deposited, {withdrawn} withdrawn)\n'.format(
                    account=account,
                    balance=account.balance,
                    deposited=sum(e.amount for e in account_events if e.amount > 0),
                    withdrawn=sum(e.amount for e in account_events if e.amount < 0),
                ))
                grouped_events = collections.defaultdict(list)
                for event in account_events:
                    grouped_events[event.description].append(event)
                for (description, event_group) in grouped_events.iteritems():
                    sys.stdout.write('    {description}: {amount}\n'.format(
                        amount=sum(e.amount for e in event_group),
                        description=description,
                    ))
        year = start_date.year
        while True:
            yield (datetime.date(year=year, month=1, day=1), year_summary_func)
            year += 1

    @property
    @abc.abstractmethod
    def all_accounts(self):
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def primary_account(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def purchase_home(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def activity_funcs(self):
        raise NotImplementedError()

class HELOCScenario(Scenario):
    def __init__(self):
        super(HELOCScenario, self).__init__()
        self.__heloc = moneycalc.account.LineOfCreditAccount(
            name='HELOC',
            interest_rate=moneycalc.account.VariableDailyInterestRate(
                prime_rate=moneycalc.account.YearlySteppingPrimeRate(
                    start_yearly_rate=Decimal('0.0425'),
                    start_year=2017,
                    yearly_increase=Decimal('0.005'),
                )
            ),
            draw_term=moneycalc.time.Period(datetime.date(2017, 1, 1), datetime.date(2032, 1, 1)),
            repayment_term=moneycalc.time.Period(datetime.date(2032, 1, 1), datetime.date(2047, 1, 1)),
        )

    @property
    def all_accounts(self):
        return [self.__heloc]

    @property
    def primary_account(self):
        return self.__heloc

    def purchase_home(self, date, amount):
        self.__heloc.withdraw(timeline=self.timeline, date=date, amount=amount, description='Purchase')

    def iter_activity_funcs(self):
        return []

class FixedRateMortgageScenario(Scenario):
    def __init__(self):
        super(FixedRateMortgageScenario, self).__init__()
        self.__checking = moneycalc.account.CheckingAccount(name='Checking')
        self.__home_loan = None

    @property
    def all_accounts(self):
        accounts = [self.__checking]
        if self.__home_loan is not None:
            accounts.append(self.__home_loan)
        return accounts

    @property
    def primary_account(self):
        return self.__checking

    def purchase_home(self, date, amount):
        if self.__home_loan is not None:
            raise NotImplementedError()
        self.__home_loan = moneycalc.account.AmortizedMonthlyLoan(
            name='Mortgage',
            amount=amount,
            interest_rate=moneycalc.account.FixedMonthlyInterestRate(yearly_rate=Decimal('0.04125')),
            term=moneycalc.time.Period(date, datetime.date(year=date.year + 30, month=date.month, day=date.day)),
        )

    def iter_activity_funcs(self):
        yield (datetime.date(2017, 1, 1), lambda date: self.__checking.deposit(timeline=self.timeline, date=date, amount=money('5000.00'), description='Tooth fairy'))
        def mortgage_payment_func(date):
            payment = self.__home_loan.minimum_deposit(date=date)
            moneycalc.account.transfer(timeline=self.timeline, date=date, from_account=self.__checking, to_account=self.__home_loan, amount=payment, description='{} payment'.format(self.__home_loan))
        now = datetime.date(2017, 1, 1) # FIXME(strager)
        while now < datetime.date(2047, 1, 1): # FIXME(strager)
            yield (now, mortgage_payment_func)
            now = moneycalc.time.add_month(now)

def main():
    for scenario in [HELOCScenario(), FixedRateMortgageScenario()]:
        sys.stdout.write(' === {} ===\n'.format(scenario))
        scenario.play()
        sys.stdout.write('\n\n')

if __name__ == '__main__':
    main()
