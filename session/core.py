"""
Call session management module.
"""


class CallSession:
    def __init__(self, subscriber, base_station, duration, start_time):
        self.subscriber = subscriber
        self.base_station = base_station
        self.cell = base_station  # Alias for backward compatibility
        self.duration = duration
        self.start_time = start_time
        self.remaining_time = duration

    def tick(self):
        """Уменьшает время жизни сессии на 1 секунду."""
        self.remaining_time -= 1
        return self.remaining_time > 0