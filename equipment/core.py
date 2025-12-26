"""
User Equipment module.
"""
import random
from .constants import TX_POWER, RX_SENSITIVITY


class UserEquipment:
    def __init__(self, ue_id, location_x, location_y):
        self.ue_id = ue_id
        self.location_x = random.randint(0, 1000)
        self.location_y = random.randint(0, 1000)
        self.velocity_x = random.uniform(-1, 1)
        self.velocity_y = random.uniform(-1, 1)
        self.tx_power = TX_POWER
        self.rx_sensitivity = RX_SENSITIVITY
        self.history = []

    def log_state(self, timestamp, rsrp, base_station_id):
        self.history.append({
            'time': timestamp,
            'x': self.location_x,
            'y': self.location_y,
            'rsrp': rsrp,
            'base_station_id': base_station_id
        })

    def get_id(self):
        return self.ue_id
    
    def get_location(self):
        return self.location_x, self.location_y
   
    def move(self):
        self.location_x += self.velocity_x
        self.location_y += self.velocity_y
        
        if self.location_x < 0 or self.location_x > 1000:
            self.velocity_x *= -1
        if self.location_y < 0 or self.location_y > 1000:
            self.velocity_y *= -1

    def generate_measurement_report(self, network, subscriber):
        """Returns list of visible base stations and their RSRP."""
        report = []
        for bs in network.base_stations.values():
            _, rsrp = network.check_connection_quality(subscriber, bs)
            if rsrp > self.rx_sensitivity:
                report.append({'bs_id': bs.id, 'rsrp': rsrp, 'bs_object': bs})
        
        report.sort(key=lambda x: x['rsrp'], reverse=True)
        return report

