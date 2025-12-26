"""
Online Charging System module.
"""


class OCS:
    def __init__(self):
        self.cdr_database = {}

    def check_balance(self, subscriber, estimated_cost):
        return subscriber.get_balance() >= estimated_cost

    def charge_subscriber(self, subscriber, amount):
        subscriber.withdraw(amount)
        return subscriber.get_balance()

