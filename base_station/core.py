"""
Base Station module.
"""
from .constants import TX_POWER, RX_SENSITIVITY, HANDOVER_HYSTERESIS, DEFAULT_CAPACITY
from session.core import CallSession
from utils import load_config

config = load_config("config.yaml")     

class BaseStation:
    def __init__(self, id, capacity, location_x, location_y, frequency, bandwidth, antenna_type):
        self.id = id
        self.capacity = capacity
        self.current_calls = 0
        self.tx_power = TX_POWER
        self.rx_sensitivity = RX_SENSITIVITY
        self.location_x = location_x
        self.location_y = location_y
        self.neighbors = []
        self.frequency = frequency
        self.bandwidth = bandwidth
        self.antenna_type = antenna_type

    def connect_call(self, subscriber, duration, start_time):
        if self.current_calls < self.capacity:
            if subscriber.make_call(duration):
                self.current_calls += 1
                return CallSession(subscriber, self, duration, start_time)
            return None
        else:
            print("Вышка перегружена")
            return False


    @staticmethod
    def get_all_base_stations():
        """
        Load all base stations from config.yaml.
        
        Returns:
            Dictionary of BaseStation objects keyed by station ID
        """
        base_stations = {}
        for bs in config['base_stations']:
            capacity = bs.get('capacity', DEFAULT_CAPACITY)
            base_stations[bs['id']] = BaseStation(
                bs['id'], 
                capacity,
                bs['x'], 
                bs['y'], 
                bs['frequency'], 
                bs['bandwidth'], 
                bs['antenna_type']
            )
        return base_stations

    def get_current_calls(self):
        return self.current_calls

    def get_capacity(self):
        return self.capacity

    def evaluate_handover(self, current_rsrp, measurement_report):
        """
        Handover decision logic with hysteresis to prevent ping-pong effect.
        """
        if not measurement_report:
            return None
            
        best_candidate = measurement_report[0]
        
        if best_candidate['rsrp'] > (current_rsrp + HANDOVER_HYSTERESIS):
            if best_candidate['bs_id'] != self.id:
                return best_candidate['bs_object']
        
        return None

    def __repr__(self):
        return f"BS({self.id}, {self.current_calls}/{self.capacity})"

