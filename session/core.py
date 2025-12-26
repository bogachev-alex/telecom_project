"""
Call session management module.
"""


class CallSession:
    def __init__(self, subscriber, base_station, duration, start_time):
        self.subscriber = subscriber
        self.base_station = base_station
        self.remaining_time = duration
        self.duration = duration
        self.start_time = start_time

