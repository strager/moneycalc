from moneycalc.tax import TaxEffect

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
                account='N/A' if self.account is None else self.account,
                amount=self.amount,
                date=self.date,
                description=self.description)

    def __init__(self):
        self.__events = []

    def __iter__(self):
        return iter(self.__events)

    def add_event(self, event):
        self.__events.append(event)

    def add_withheld_cash(self, date, amount, description):
        self.add_event(Timeline.Event(date=date, account=None, amount=-amount, description=description, tax_effect=TaxEffect.CASH_WITHHELD))

    def add_income(self, date, amount, description):
        self.add_event(Timeline.Event(date=date, account=None, amount=amount, description=description, tax_effect=TaxEffect.CASH_INCOME))

    def add_tax_deduction(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=amount, description=description, tax_effect=TaxEffect.DEDUCTIBLE))

    def add_generic_deposit(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=amount, description=description))

    def add_principal_deposit(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=amount, description=description))

    def add_interest_deposit(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=amount, description=description, tax_effect=TaxEffect.DEDUCTIBLE))

    def add_withdrawl(self, date, account, amount, description):
        self.add_event(Timeline.Event(date=date, account=account, amount=-amount, description=description))
