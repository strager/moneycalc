from decimal import Decimal
from moneycalc.money import money
from moneycalc.time import Period
from moneycalc.time import add_month
from moneycalc.time import sub_month
import abc
import math
import moneycalc.time

class OverdraftError(ValueError):
    pass

class InterestRate(object):
    @abc.abstractmethod
    def period_interest_rate(self, period):
        raise NotImplementedError()

class FixedMonthlyInterestRate(InterestRate):
    def __init__(self, yearly_rate):
        self.__yearly_rate = yearly_rate

    def period_interest_rate(self, period):
        if not period.is_month:
            raise NotImplementedError()
        return self.__yearly_rate / 12

class YearlyVariableMonthlyInterestRate(InterestRate):
    def __init__(self, yearly_rate_func):
        self.__yearly_rate_func = yearly_rate_func

    def period_interest_rate(self, period):
        if not period.is_month:
            raise NotImplementedError()
        return self.__yearly_rate_func(period.start_date.year) / 12

def yearly_stepping_rate_func(start_yearly_rate, start_year, yearly_increase):
    def func(year):
        years_since_start = year - start_year
        return start_yearly_rate + yearly_increase * years_since_start
    return func

class AdjustableRateMortgageInterestRate(InterestRate):
    def __init__(self, fixed_period, fixed_yearly_rate, variable_yearly_rate_func):
        self.__fixed_period = fixed_period
        self.__fixed_interest_rate = FixedMonthlyInterestRate(fixed_yearly_rate)
        self.__variable_interest_rate = YearlyVariableMonthlyInterestRate(variable_yearly_rate_func)

    def period_interest_rate(self, period):
        if period.intersects(self.__fixed_period):
            if period not in self.__fixed_period:
                raise NotImplementedError()
            return self.__fixed_interest_rate.period_interest_rate(period)
        if period.start_date < self.__fixed_period.start_date:
            raise KeyError('Interest for period not defined')
        assert period.start_date >= self.__fixed_period.end_date
        return self.__variable_interest_rate.period_interest_rate(period)

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
        if date != self.__next_payment_due:
            raise NotImplementedError()
        current_period = Period(date, add_month(date))
        interest_rate = self.interest_rate.period_interest_rate(current_period)
        if date == self.__maturity_date:
            interest = money(interest_rate * self.balance)
            return money(interest + self.balance)
        else:
            months_remaining = moneycalc.time.diff_months(self.term.end_date, current_period.start_date)
            tmp = Decimal(math.pow(Decimal(1) + interest_rate, months_remaining))
            return money(self.balance * (interest_rate * tmp) / (tmp - Decimal(1)))

    def deposit(self, timeline, date, amount, description):
        assert amount >= 0
        assert amount == money(amount)
        if date != self.__next_payment_due:
            raise NotImplementedError()
        current_period = Period(date, add_month(date))
        interest_rate = self.interest_rate.period_interest_rate(current_period)
        interest = money(interest_rate * self.balance)
        if amount < interest:
            raise NotImplementedError()
        # TODO(strager): Ensure minimum monthly payment is met.
        principal = money(amount - interest)
        if principal > self.balance:
            raise NotImplementedError()
        timeline.add_interest_deposit(date=date, account=self, amount=interest, description='{} (interest ({:.5}%))'.format(description, interest_rate * Decimal(12) * Decimal(100)))
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
