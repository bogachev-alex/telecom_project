"""
Tariff management module.
"""


class Tariff:
    def __init__(self, tariff_name, cost_per_minute):
        self.tariff_name = tariff_name
        self.cost_per_minute = cost_per_minute

    def get_tariff_name(self):
        return self.tariff_name

    def get_cost_per_minute(self):
        return self.cost_per_minute

    def set_cost_per_minute(self, cost_per_minute):
        self.cost_per_minute = cost_per_minute

