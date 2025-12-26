"""
Subscriber management module.
"""
import random
import time


class Subscriber:
    def __init__(self, first_name, last_name, id_number, user_equipment, email, phone, tariff, arrival_rate, avg_duration):
        self.first_name = first_name
        self.last_name = last_name
        self.id_number = id_number
        self.user_equipment = user_equipment
        self.email = email
        self.phone = phone
        self.balance = 0
        self.subscribed = False
        self.bonus_balance = 0
        self.tariff = tariff
        self.arrival_rate = arrival_rate
        self.avg_duration = avg_duration
        self.retrial_timer = 0
        self.pending_duration = 0

    def top_up(self, amount):
        self.balance += amount
        return self.balance

    def withdraw(self, amount):
        self.balance -= amount
        return self.balance

    def subscribe(self):
        self.subscribed = True
        return self.subscribed

    def unsubscribe(self):
        self.subscribed = False
        return self.subscribed

    def get_balance(self):
        return self.balance

    def get_bonus_balance(self):
        return self.bonus_balance
    
    def make_call(self, duration):
        cost_per_min = self.tariff.get_cost_per_minute()
        total_cost = duration * cost_per_min
        if self.balance < total_cost:
            print(f"Недостаточно денег на балансе: нужно {total_cost} руб., на балансе {self.balance} руб.")
            return False
        self.balance -= total_cost
        self.bonus_balance += total_cost * 0.05
        return True

    def act(self, network):
        if self.is_busy(network):
            return
        
        if self.retrial_timer > 0:
            self.retrial_timer -= 1
            if self.retrial_timer == 0:
                print(f"--- {self.first_name} делает ПОВТОРНУЮ попытку ---")
                success = network.connect_call(self, self.pending_duration, time.time())
                if not success:
                    self.retrial_timer = random.randint(5, 15)
            return

        if random.random() < self.arrival_rate:
            duration = max(1, int(random.expovariate(1/self.avg_duration)))
            success = network.connect_call(self, duration, time.time())

            if not success:
                self.pending_duration = duration
                self.retrial_timer = random.randint(5, 15)

    def is_busy(self, network):
        return any(session.subscriber == self for session in network.active_sessions)

