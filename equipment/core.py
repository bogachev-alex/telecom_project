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
        # Handover state for Event A3
        self.handover_trigger_count = 0  # Time-to-Trigger counter
        self.current_serving_bs_id = None  # Currently connected BS ID
        self.handover_history = []  # List of handover events: [(x, y, from_bs, to_bs, timestamp)]

    def log_state(self, timestamp, rsrp, base_station_id, sim_step=None):
        self.history.append({
            'time': timestamp,
            'sim_step': sim_step,
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
        """Move UE by velocity vector."""
        self.location_x += self.velocity_x
        self.location_y += self.velocity_y
        
        if self.location_x < 0 or self.location_x > 1000:
            self.velocity_x *= -1
        if self.location_y < 0 or self.location_y > 1000:
            self.velocity_y *= -1

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

    def check_handover_a3(self, coverage_data, coverage_map, hysteresis_db=3.0, time_to_trigger=3):
        """
        Check Event A3 handover condition using coverage map data.
        
        Event A3: Candidate_RSRP > Serving_RSRP + Hysteresis
        Must be true for Time-to-Trigger consecutive measurements.
        
        Args:
            coverage_data: Dictionary from coverage_map.lookup()
            coverage_map: CoverageMap instance to resolve BS IDs
            hysteresis_db: Hysteresis in dB to prevent ping-pong (default 3.0)
            time_to_trigger: Number of consecutive measurements required (default 3)
            
        Returns:
            Tuple (should_handover: bool, target_bs_id: str or None)
        """
        serving_rsrp = coverage_data['serving_rsrp']
        serving_bs_id = coverage_data['serving_bs_id']
        candidate_rsrp = coverage_data['candidate_rsrp']
        candidate_bs_id = coverage_data['candidate_bs_id']
        
        # Check if serving BS changed (but not yet handovered)
        if serving_bs_id != self.current_serving_bs_id:
            # Reset counter if serving BS changed
            self.handover_trigger_count = 0
        
        # Check Event A3 condition: Candidate_RSRP > Serving_RSRP + Hysteresis
        if candidate_bs_id is not None and candidate_rsrp > -140:
            condition_met = candidate_rsrp > (serving_rsrp + hysteresis_db)
            
            if condition_met:
                self.handover_trigger_count += 1
            else:
                # Reset counter if condition not met
                self.handover_trigger_count = 0
            
            # Check if Time-to-Trigger reached
            if self.handover_trigger_count >= time_to_trigger:
                # Get actual BS ID from numeric ID
                if candidate_bs_id is not None:
                    # Find BS by numeric ID
                    for bs_id, bs in coverage_map.base_stations.items():
                        numeric_id = coverage_map.bs_id_to_numeric.get(bs_id, 0)
                        if int(candidate_bs_id) == numeric_id:
                            self.handover_trigger_count = 0  # Reset after handover
                            return True, bs_id
        else:
            # No valid candidate, reset counter
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

