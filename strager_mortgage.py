#!/usr/bin/env python2.7

from decimal import Decimal
import abc
import datetime
import decimal
import sys

money_context = decimal.BasicContext.copy()
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

class Timeline(object):
    class Event(object):
        def __init__(self, date, account, amount, description):
            self.date = date
            self.account = account
            self.amount = amount
            self.description = description

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

    def add_principal_deposit(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=amount, description=description))

    def add_interest_deposit(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=amount, description=description))

    def add_withdrawl(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=-amount, description=description))

class AmortizedMonthlyLoan(object):
    def __init__(self, name, amount, interest_rate, term):
        assert amount == money(amount)
        self.name = name
        self.balance = amount
        self.interest_rate = interest_rate
        self.term = term
        self.__next_payment_due = term.start_date
        self.__maturity_date = sub_month(self.term.end_date)

    def __str__(self):
        return self.name

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

    def deposit(self, timeline, date, amount):
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
        timeline.add_interest_deposit(date=date, account=self, amount=interest, description='Interest payment')
        timeline.add_principal_deposit(date=date, account=self, amount=principal, description='Principal payment')
        self.balance = money(self.balance - principal)
        self.__next_payment_due = current_period.end_date

def main():
    timeline = Timeline()
    loan = AmortizedMonthlyLoan(
        name='Mortgage',
        amount=money('975000.00'),
        interest_rate=FixedMonthlyInterestRate(yearly_rate=Decimal('0.04125')),
        term=Period(datetime.date(2017, 1, 1), datetime.date(2047, 1, 1)))

    now = datetime.date(2017, 1, 1)
    while loan.balance > 0:
        payment = money('4725.33')
        minimum_deposit = loan.minimum_deposit(date=now)
        if payment < minimum_deposit:
            payment = minimum_deposit
        loan.deposit(timeline=timeline, date=now, amount=payment)
        now = add_month(now)

    sys.stdout.write('Timeline:\n\n')
    for event in timeline:
        sys.stdout.write('{}\n'.format(event))

if __name__ == '__main__':
    main()
