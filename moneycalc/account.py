from decimal import Decimal
from moneycalc.money import money
from moneycalc.time import Period
from moneycalc.time import add_month
from moneycalc.time import sub_month
import abc
import datetime
import math
import moneycalc.time

class OverdraftError(ValueError):
    pass

class PrimeRate(object):
    @abc.abstractmethod
    def prime_rate_and_change_date(self, date):
        '''
        Returns a tuple of the prime rate at the given date (as
        a Decimal yearly interest rate) and the next date the
        prime rate could change.
        '''
        raise NotImplementedError()

class YearlySteppingPrimeRate(PrimeRate):
    def __init__(self, start_yearly_rate, start_year, yearly_increase):
        self.__start_yearly_rate = start_yearly_rate
        self.__start_year = start_year
        self.__yearly_increase = yearly_increase

    def prime_rate_and_change_date(self, date):
        years_since_start = date.year - self.__start_year
        if years_since_start < 0:
            raise NotImplementedError()
        rate = self.__start_yearly_rate + self.__yearly_increase * years_since_start
        return (rate, datetime.date(year=date.year + 1, month=1, day=1))

class YearlySampledPrimeRate(PrimeRate):
    def __init__(self, base_prime_rate, sample_date):
        self.__base_prime_rate = base_prime_rate
        self.__sample_month = sample_date.month
        self.__sample_day = sample_date.day

    def prime_rate_and_change_date(self, date):
        (prime_rate, _change_date) = self.__base_prime_rate.prime_rate_and_change_date(datetime.date(year=date.year, month=self.__sample_month, day=self.__sample_day))
        return (prime_rate, datetime.datetime(year=date.year + 1, month=self.__sample_month, day=self.__sample_day))

class InterestRate(object):
    @abc.abstractmethod
    def period_interest_rate(self, period):
        raise NotImplementedError()

class FixedDailyInterstRate(InterestRate):
    def __init__(self, yearly_rate):
        self.__yearly_rate = yearly_rate

    def period_interest_rate(self, period):
        if not period.is_day:
            raise NotImplementedError()
        return self.__yearly_rate / moneycalc.time.days_in_year(period.start_date.year)

class FixedMonthlyInterestRate(InterestRate):
    def __init__(self, yearly_rate):
        self.__yearly_rate = yearly_rate

    def period_interest_rate(self, period):
        if not period.is_month:
            raise NotImplementedError()
        return self.__yearly_rate / 12

class VariableDailyInterestRate(InterestRate):
    def __init__(self, prime_rate):
        self.__prime_rate = prime_rate

    def period_interest_rate(self, period):
        if not period.is_day:
            raise NotImplementedError()
        (prime_rate, next_prime_rate_change) = self.__prime_rate.prime_rate_and_change_date(period.start_date)
        if next_prime_rate_change < period.end_date:
            raise NotImplementedError()
        return prime_rate / moneycalc.time.days_in_year(period.start_date.year)

class VariableMonthlyInterestRate(InterestRate):
    def __init__(self, prime_rate):
        self.__prime_rate = prime_rate

    def period_interest_rate(self, period):
        if not period.is_month:
            raise NotImplementedError()
        (prime_rate, next_prime_rate_change) = self.__prime_rate.prime_rate_and_change_date(period.start_date)
        if next_prime_rate_change < period.end_date:
            raise NotImplementedError()
        return prime_rate / 12

class AdjustableRateMortgageInterestRate(InterestRate):
    def __init__(self, fixed_period, fixed_yearly_rate, prime_rate):
        self.__fixed_period = fixed_period
        self.__fixed_interest_rate = FixedMonthlyInterestRate(fixed_yearly_rate)
        self.__variable_interest_rate = VariableMonthlyInterestRate(prime_rate)

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

class LineOfCreditAccount(Account):
    '''
    A line of credit (e.g. credit card or HELOC) where:

    * Interest payments are due monthly,
    * Interest accrues daily, and
    * A draw term comes before an optional repayment-only term.
    '''
    def __init__(self, name, interest_rate, draw_term, repayment_term):
        super(LineOfCreditAccount, self).__init__(name=name)
        self.__interest_rate = interest_rate
        self.__draw_term = draw_term
        self.__repayment_term = repayment_term
        self.__balance = money(0)
        self.__period_finance_charge = money(0)
        self.__due_finance_charge = money(0)
        self.__last_update = None

    def deposit(self, timeline, date, amount, description):
        assert amount >= 0
        assert amount == money(amount)
        assert self.__last_update is None or date >= self.__last_update
        self.__update_finance_charge(date)
        principal_amount = amount
        if self.__due_finance_charge > money(0):
            # Pay the finance charge due before paying the principal.
            finance_charge_payment = min(self.__due_finance_charge, amount)
            if finance_charge_payment > money(0):
                timeline.add_interest_deposit(date=date, account=self, amount=finance_charge_payment, description='{} (interest)'.format(description))
                self.__due_finance_charge -= finance_charge_payment
                principal_amount -= finance_charge_payment
        timeline.add_generic_deposit(date=date, account=self, amount=principal_amount, description=description)
        self.__balance = money(self.__balance + principal_amount)
        self.__last_update = date

    def withdraw(self, timeline, date, amount, description):
        assert amount >= 0
        assert amount == money(amount)
        assert self.__last_update is None or date >= self.__last_update
        if date not in self.__draw_term:
            raise OverdraftError()
        self.__update_finance_charge(date)
        timeline.add_withdrawl(date=date, account=self, amount=amount, description=description)
        self.__balance = money(self.__balance - amount)
        self.__last_update = date

    def __update_finance_charge(self, date):
        '''
        Accrue finance charges for all days before (but not including) the
        given date.

        Also, mark finance charges as due as necessary.
        '''
        if self.__last_update is None:
            assert self.__balance == money(0)
            return
        now = self.__last_update
        while now < date:
            if now.day == 1:
                # TODO(strager): Ensure __due_finance_charge is paid within the payment window.
                if self.__due_finance_charge != money(0):
                    raise NotImplementedError()
                self.__due_finance_charge = self.__period_finance_charge
                self.__period_finance_charge = money(0)
            tomorrow = now + datetime.timedelta(days=1)
            if self.__balance < money(0):
                if now in self.__draw_term:
                    interest_rate = self.__interest_rate.period_interest_rate(Period(now, tomorrow))
                    finance_charge = money(interest_rate * -self.__balance)
                    self.__period_finance_charge += finance_charge
                elif now in self.__repayment_term:
                    raise NotImplementedError()
                else:
                    raise NotImplementedError()
            self.__last_update = tomorrow
            now = tomorrow
        assert self.__last_update == date

def transfer(timeline, date, from_account, to_account, amount, description):
    from_account.withdraw(timeline=timeline, date=date, amount=amount, description=description)
    to_account.deposit(timeline=timeline, date=date, amount=amount, description=description)
