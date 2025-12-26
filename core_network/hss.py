"""
Home Subscriber Server module.
"""


class HSS:
    def __init__(self):
        self.subscribers = {}
    
    def add_subscriber(self, id_number, subscriber):
        self.subscribers[id_number] = subscriber
        
    def get_subscriber(self, id_number):
        return self.subscribers.get(id_number)

