"""
Base Station module.
"""
from .constants import TX_POWER, RX_SENSITIVITY, HANDOVER_HYSTERESIS, DEFAULT_CAPACITY
from .types import Sector
from session.core import CallSession
from utils import load_config

config = load_config("config.yaml")     

class BaseStation:
    def __init__(self, id, capacity, location_x, location_y, frequency, bandwidth, antenna_type, azimuth=0, sectors=None):
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
        self.azimuth = azimuth  # Legacy: first sector azimuth for backward compatibility
        
        # Initialize 3 sectors with optimal allocation
        if sectors is None:
            self.sectors = self._create_default_sectors(azimuth)
        else:
            self.sectors = sectors

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
            azimuth = bs.get('azimuth', 0)
            base_stations[bs['id']] = BaseStation(
                bs['id'], 
                capacity,
                bs['x'], 
                bs['y'], 
                bs['frequency'], 
                bs['bandwidth'], 
                bs['antenna_type'],
                azimuth
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

    def _create_default_sectors(self, base_azimuth):
        """
        Create 3 sectors with 120° spacing.
        Standard configuration: -30°, 90°, 210° (or 0°, 120°, 240°).
        
        Args:
            base_azimuth: Base rotation angle in degrees
            
        Returns:
            List of 3 Sector objects
        """
        # Standard 3-sector pattern: -30°, 90°, 210° (rotated by base_azimuth)
        sector_azimuths = [
            (base_azimuth - 30) % 360,
            (base_azimuth + 90) % 360,
            (base_azimuth + 210) % 360
        ]
        return [
            Sector(sector_id=0, azimuth=sector_azimuths[0]),
            Sector(sector_id=1, azimuth=sector_azimuths[1]),
            Sector(sector_id=2, azimuth=sector_azimuths[2])
        ]
    
    def get_sector(self, sector_id):
        """Get sector by ID (0, 1, or 2)."""
        return self.sectors[sector_id] if 0 <= sector_id < len(self.sectors) else None
    
    def __repr__(self):
        return f"BS({self.id}, {self.current_calls}/{self.capacity}, sectors={len(self.sectors)})"

