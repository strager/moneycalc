#!/usr/bin/env python2.7

from decimal import Decimal
import abc
import collections
import datetime
import decimal
import sys

money_context = decimal.BasicContext.copy()
money_context.prec = 20
money_context.rounding = decimal.ROUND_HALF_UP # FIXME(strager)

def money(amount):
    return Decimal(amount).quantize(Decimal('0.01'), context=money_context)

def add_month(date):
    if date.month == 12:
        return datetime.date(year=date.year + 1, month=1, day=date.day)
    else:
        return datetime.date(year=date.year, month=date.month + 1, day=date.day)

def sub_month(date):
    if date.month == 1:
        return datetime.date(year=date.year - 1, month=12, day=date.day)
    else:
        return datetime.date(year=date.year, month=date.month - 1, day=date.day)

class Period(object):
    def __init__(self, start_date, end_date):
        assert start_date <= end_date
        self.start_date = start_date
        self.end_date = end_date

    def __contains__(self, date):
        return self.start_date <= date and date < self.end_date

    def __repr__(self):
        return 'Period({}, {})'.format(repr(self.start_date), repr(self.end_date))

    @property
    def days(self):
        return (self.end_date - self.start_date).days

    @property
    def is_month(self):
        return self.start_date.day == 1 and self.end_date.day == 1 and add_month(self.start_date) == self.end_date

class InterestRate(object):
    @abc.abstractmethod
    def period_interest_rate(self, period):
        raise NotImplementedError()

    def period_interest(self, period, amount):
        return money(self.period_interest_rate(period) * amount)

class FixedMonthlyInterestRate(InterestRate):
    def __init__(self, yearly_rate):
        self.__yearly_rate = yearly_rate

    def period_interest_rate(self, period):
        if not period.is_month:
            raise NotImplementedError()
        return self.__yearly_rate / 12

class TaxEffect(object):
    CASH_INCOME = 'CASH_INCOME'
    CASH_WITHHELD = 'CASH_WITHHELD'
    DEDUCTIBLE = 'DEDUCTIBLE'
    NONE = 'NONE'

class Timeline(object):
    class Event(object):
        def __init__(self, date, account, amount, description, tax_effect=TaxEffect.NONE):
            self.date = date
            self.account = account
            self.amount = amount
            self.description = description
            self.tax_effect = tax_effect

        def __str__(self):
            return '{date}: {account} {amount:16} ({description})'.format(
                account=self.account,
                amount=self.amount,
                date=self.date,
                description=self.description)

    def __init__(self):
        self.__events = []

    def __iter__(self):
        return iter(self.__events)

    def add_event(self, event):
        self.__events.append(event)

    def add_withheld_cash(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=-amount, description=description, tax_effect=TaxEffect.CASH_WITHHELD))

    def add_income(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=amount, description=description, tax_effect=TaxEffect.CASH_INCOME))

    def add_generic_deposit(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=amount, description=description))

    def add_principal_deposit(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=amount, description=description))

    def add_interest_deposit(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=amount, description=description, tax_effect=TaxEffect.DEDUCTIBLE))

    def add_withdrawl(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=-amount, description=description))

    def iter_events_in_period(self, period):
        return (event for event in self if event.date in period)

class Account(object):
    def __init__(self, name):
        self.__name = name

    def __str__(self):
        return self.__name

class AmortizedMonthlyLoan(Account):
    def __init__(self, name, amount, interest_rate, term):
        super(AmortizedMonthlyLoan, self).__init__(name=name)
        assert amount == money(amount)
        self.balance = amount
        self.interest_rate = interest_rate
        self.term = term
        self.__next_payment_due = term.start_date
        self.__maturity_date = sub_month(self.term.end_date)

    def minimum_deposit(self, date):
        if date > self.__maturity_date:
            raise NotImplementedError()
        if date == self.__maturity_date:
            current_period = Period(date, add_month(date))
            interest = self.interest_rate.period_interest(current_period, self.balance)
            return money(interest + self.balance)
        else:
            # TODO(strager): Amortization.
            return 0

    def deposit(self, timeline, date, amount, description):
        assert amount >= 0
        assert amount == money(amount)
        if date != self.__next_payment_due:
            raise NotImplementedError()
        current_period = Period(date, add_month(date))
        interest = self.interest_rate.period_interest(current_period, self.balance)
        if amount < interest:
            raise NotImplementedError()
        # TODO(strager): Ensure minimum monthly payment is met.
        principal = money(amount - interest)
        if principal > self.balance:
            raise NotImplementedError()
        timeline.add_interest_deposit(date=date, account=self, amount=interest, description='{} (interest)'.format(description))
        timeline.add_principal_deposit(date=date, account=self, amount=principal, description='{} (principal)'.format(description))
        self.balance = money(self.balance - principal)
        self.__next_payment_due = current_period.end_date

class CheckingAccount(Account):
    def __init__(self, name):
        super(CheckingAccount, self).__init__(name=name)
        self.__balance = money(0)
        self.__last_update = None

    def deposit(self, timeline, date, amount, description):
        assert amount >= 0
        assert amount == money(amount)
        assert self.__last_update is None or date >= self.__last_update
        timeline.add_generic_deposit(date=date, account=self, amount=amount, description=description)
        self.__balance = money(self.__balance + amount)
        self.__last_update = date

    def withdraw(self, timeline, date, amount, description):
        assert amount >= 0
        assert amount == money(amount)
        assert self.__last_update is None or date >= self.__last_update
        if amount > self.__balance:
            raise NotImplementedError()
        timeline.add_withdrawl(date=date, account=self, amount=amount, description=description)
        self.__balance = money(self.__balance - amount)
        self.__last_update = date

class OverdraftError(ValueError):
    pass

class Income(Account):
    def __init__(self):
        super(Income, self).__init__(name='Income')
        self.__last_update = None

    def earn_cash(self, timeline, to_account, date, gross_amount, net_amount, description):
        assert gross_amount >= 0
        assert gross_amount == money(gross_amount)
        assert net_amount >= 0
        assert net_amount == money(net_amount)
        assert gross_amount >= net_amount
        assert self.__last_update is None or date >= self.__last_update
        timeline.add_income(date=date, account=self, amount=gross_amount, description='{} (net)'.format(description))
        withheld_amount = gross_amount - net_amount
        if withheld_amount > 0:
            timeline.add_withheld_cash(date=date, account=self, amount=withheld_amount, description='{} (withholding)'.format(description))
        to_account.deposit(timeline=timeline, date=date, amount=net_amount, description=description)
        self.__last_update = date

def transfer(timeline, date, from_account, to_account, amount, description):
    from_account.withdraw(timeline=timeline, date=date, amount=amount, description=description)
    to_account.deposit(timeline=timeline, date=date, amount=amount, description=description)

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
    gross_cash_income = sum(event.amount for event in events if event.tax_effect == TaxEffect.CASH_INCOME)
    withheld_cash = sum(-event.amount for event in events if event.tax_effect == TaxEffect.CASH_WITHHELD)
    deductible = sum(event.amount for event in events if event.tax_effect == TaxEffect.DEDUCTIBLE)
    tax_rate = us_tax_rate(year=year, amount=gross_cash_income) + ca_tax_rate(year=year, amount=gross_cash_income)
    taxable_income = max((gross_cash_income - deductible, money(0)))
    total_due = money(taxable_income * tax_rate)
    net_due = total_due - withheld_cash
    return net_due

def iter_merge_sort(iterables, key):
    iterators = list(map(iter, iterables))
    cur_values = list(map(lambda iterator: next(iterator, None), iterators))
    active_indexes = set(index for (index, value) in enumerate(cur_values) if value is not None)
    while active_indexes:
        index = min(active_indexes, key=lambda index: key(cur_values[index]))
        assert cur_values[index] is not None
        yield cur_values[index]
        new_value = next(iterators[index], None)
        cur_values[index] = new_value
        if new_value is None:
            active_indexes.remove(index)

def main():
    timeline = Timeline()
    loan = AmortizedMonthlyLoan(
        name='Mortgage',
        amount=money('975000.00'),
        interest_rate=FixedMonthlyInterestRate(yearly_rate=Decimal('0.04125')),
        term=Period(datetime.date(2017, 1, 1), datetime.date(2047, 1, 1)))
    checking = CheckingAccount(name='Checking')
    income = Income()

    begin_date = datetime.date(year=2016, month=1, day=1)
    end_date = datetime.date(year=2060, month=1, day=1)

    mortgage_payment_funcs = []
    def mortgage_payment_func(date):
        payment = money('4725.33')
        minimum_deposit = loan.minimum_deposit(date=date)
        if payment < minimum_deposit:
            payment = minimum_deposit
        transfer(timeline=timeline, date=date, from_account=checking, to_account=loan, amount=payment, description='Mortgage payment')
    now = loan.term.start_date
    while now < loan.term.end_date:
        mortgage_payment_funcs.append((now, mortgage_payment_func))
        now = add_month(now)

    tax_payment_funcs = []
    def tax_payment_func(date):
        tax_year = date.year - 1
        tax_period = Period(datetime.date(year=tax_year, month=1, day=1), datetime.date(year=tax_year + 1, month=1, day=1))
        due = tax_due(events=[event for event in timeline if event.date in tax_period and event.tax_effect != TaxEffect.NONE], year=tax_year)
        if due < 0:
            raise NotImplementedError()
        else:
            checking.withdraw(timeline=timeline, date=date, amount=due, description='Taxes')
    tax_payment_funcs = ((datetime.date(year=year, month=4, day=1), tax_payment_func) for year in xrange(begin_date.year, end_date.year + 1))

    def income_func(date):
        income.earn_cash(timeline=timeline, to_account=checking, date=date, gross_amount=money('999999.99'), net_amount=money('999999.99'), description='Life')
    income_funcs = ((datetime.date(year=year, month=1, day=1), income_func) for year in xrange(begin_date.year, end_date.year + 1))

    for (date, func) in iter_merge_sort([mortgage_payment_funcs, tax_payment_funcs, income_funcs], key=lambda (date, func): date):
        func(date)

    sys.stdout.write('Timeline:\n\n')
    for event in timeline:
        sys.stdout.write('{}\n'.format(event))

if __name__ == '__main__':
    main()
