import datetime
import unittest

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

    def __contains__(self, value):
        if hasattr(value, 'start_date') and hasattr(value, 'end_date'):
            return self.start_date <= value.start_date and value.end_date <= self.end_date
        else:
            return self.start_date <= value and value < self.end_date

    def __repr__(self):
        return 'Period({}, {})'.format(repr(self.start_date), repr(self.end_date))

    @property
    def days(self):
        return (self.end_date - self.start_date).days

    @property
    def is_month(self):
        return self.start_date.day == 1 and self.end_date.day == 1 and add_month(self.start_date) == self.end_date

    def intersects(self, other):
        return self.start_date < other.end_date and other.start_date < self.end_date

class TestDateMath(unittest.TestCase):
    def test_add_month(self):
        self.assertEqual(add_month(datetime.date(2017, 1, 1)), datetime.date(2017, 2, 1))
        self.assertEqual(add_month(datetime.date(2017, 8, 5)), datetime.date(2017, 9, 5))
        self.assertEqual(add_month(datetime.date(2017, 11, 5)), datetime.date(2017, 12, 5))
        self.assertEqual(add_month(datetime.date(2017, 12, 5)), datetime.date(2018, 1, 5))
        # TODO(strager)
        # with self.assertRaises(Exception):
        #    datetime.date(2017, 1, 30)

class TestPeriod(unittest.TestCase):
    def test_intersects(self):
        jan_to_feb = Period(datetime.date(2017, 1, 1), datetime.date(2017, 2, 1))
        feb_to_march = Period(datetime.date(2017, 2, 1), datetime.date(2017, 3, 1))
        jan_to_march = Period(datetime.date(2017, 1, 1), datetime.date(2017, 3, 1))

        # intersects is reflexive.
        self.assertTrue(jan_to_feb.intersects(jan_to_feb))
        self.assertTrue(feb_to_march.intersects(feb_to_march))
        self.assertTrue(jan_to_march.intersects(jan_to_march))

        self.assertTrue(jan_to_feb.intersects(jan_to_march))
        self.assertFalse(jan_to_feb.intersects(feb_to_march))
        self.assertTrue(feb_to_march.intersects(jan_to_march))

        # intersects is commutative.
        self.assertTrue(jan_to_march.intersects(jan_to_feb))
        self.assertFalse(feb_to_march.intersects(jan_to_feb))
        self.assertTrue(jan_to_march.intersects(feb_to_march))
