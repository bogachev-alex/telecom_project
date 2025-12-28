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
        self.velocity_x = random.uniform(-2, 2)  # Increased speed for more handovers
        self.velocity_y = random.uniform(-2, 2)
        self.tx_power = TX_POWER
        self.rx_sensitivity = RX_SENSITIVITY
        self.history = []
        # Handover state for Event A3
        self.handover_trigger_count = 0  # Time-to-Trigger counter
        self.current_serving_bs_id = None  # Currently connected BS ID
        self.handover_history = []  # List of handover events: [(x, y, from_bs, to_bs, timestamp)]

    def log_state(self, timestamp, rsrp, base_station_id, sim_step=None, event_type=None):
        """Log UE state with optional event type (HANDOVER, RESELECTION, or None)."""
        self.history.append({
            'time': timestamp,
            'sim_step': sim_step,
            'x': self.location_x,
            'y': self.location_y,
            'rsrp': rsrp,
            'base_station_id': base_station_id,
            'event': event_type
        })

    def get_id(self):
        return self.ue_id
    
    def get_location(self):
        return self.location_x, self.location_y
   
    def move(self):
        """Move UE by velocity vector with smooth direction changes."""
        # Add small random variation to direction (more realistic movement)
        if random.random() < 0.1:  # 10% chance to change direction slightly
            self.velocity_x += random.uniform(-0.2, 0.2)
            self.velocity_y += random.uniform(-0.2, 0.2)
            # Normalize velocity to maintain consistent speed
            speed = (self.velocity_x**2 + self.velocity_y**2)**0.5
            if speed > 0:
                self.velocity_x = self.velocity_x / speed * random.uniform(0.5, 1.5)
                self.velocity_y = self.velocity_y / speed * random.uniform(0.5, 1.5)
        
        self.location_x += self.velocity_x
        self.location_y += self.velocity_y
        
        # Smooth boundary handling - turn around gradually instead of instant bounce
        if self.location_x < 0:
            self.location_x = 0
            self.velocity_x = abs(self.velocity_x) * random.uniform(0.5, 1.0)
        elif self.location_x > 1000:
            self.location_x = 1000
            self.velocity_x = -abs(self.velocity_x) * random.uniform(0.5, 1.0)
            
        if self.location_y < 0:
            self.location_y = 0
            self.velocity_y = abs(self.velocity_y) * random.uniform(0.5, 1.0)
        elif self.location_y > 1000:
            self.location_y = 1000
            self.velocity_y = -abs(self.velocity_y) * random.uniform(0.5, 1.0)

    def step(self, coverage_map):
        """
        Move and read coverage data from pre-calculated map.
        UE becomes "cheap" - just consumes data, no calculations needed.
        
        Args:
            coverage_map: CoverageMap instance with pre-calculated data
            
        Returns:
            Dictionary with coverage data at current location
        """
        # 1. Move
        self.move()
        
        # 2. Lookup coverage data at current position
        # Convert coordinates to array indices
        coverage_data = coverage_map.lookup(self.location_x, self.location_y)
        
        return coverage_data

    def check_handover_a3(self, current_connected_rsrp, coverage_data, coverage_map, current_bs_id=None, hysteresis_db=3.0, time_to_trigger=3):
        """
        Check Event A3 handover condition using coverage map data.
        
        Event A3: Target_RSRP > Current_Connected_RSRP + Hysteresis
        Must be true for Time-to-Trigger consecutive measurements.
        
        Args:
            current_connected_rsrp: Real RSRP from current connected BS (computed in Network.tick)
            coverage_data: Dictionary from coverage_map.lookup() where 'serving' = best signal in point
            coverage_map: CoverageMap instance to resolve BS IDs
            current_bs_id: ID of current call BS (to avoid handover to same BS)
            hysteresis_db: Hysteresis in dB to prevent ping-pong (default 3.0)
            time_to_trigger: Number of consecutive measurements required (default 3)
            
        Returns:
            Tuple (should_handover: bool, target_bs_id: str or None)
        """
        # Best cell in current location (Target)
        target_rsrp = coverage_data['serving_rsrp']
        target_bs_id = coverage_data['serving_bs_id']
        
        # If already on best cell - no handover needed
        if current_bs_id and target_bs_id == current_bs_id:
            self.handover_trigger_count = 0
            return False, None
        
        # Check Event A3 condition: Target_RSRP > Current_Connected_RSRP + Hysteresis
        if target_bs_id is not None and target_rsrp > -140:
            condition_met = target_rsrp > (current_connected_rsrp + hysteresis_db)
            
            if condition_met:
                self.handover_trigger_count += 1
            else:
                # Reset counter if condition not met
                self.handover_trigger_count = 0
            
            # Check if Time-to-Trigger reached
            if self.handover_trigger_count >= time_to_trigger:
                self.handover_trigger_count = 0
                return True, target_bs_id
        else:
            # No valid target, reset counter
            self.handover_trigger_count = 0
        
        return False, None

    def generate_measurement_report(self, network, subscriber):
        """Returns list of visible base stations and their RSRP."""
        report = []
        for bs in network.base_stations.values():
            _, rsrp = network.check_connection_quality(subscriber, bs)
            if rsrp > self.rx_sensitivity:
                report.append({'bs_id': bs.id, 'rsrp': rsrp, 'bs_object': bs})
        
        report.sort(key=lambda x: x['rsrp'], reverse=True)
        return report

