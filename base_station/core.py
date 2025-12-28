"""
Base Station module.
"""
import math
from .constants import HANDOVER_HYSTERESIS
from .types import Sector
from session.core import CallSession
from utils.config import load_config
from network.physics import get_path_loss, get_angle_attenuation

# base_station/core.py
from .resource_manager import GsmResourceManager, NrResourceManager

config = load_config("config.yaml")     

class BaseStation:
    def __init__(self, site_config):
        self.id = site_config['id']
        self.site = site_config['site']
        self.technologies = site_config['technologies']
        self.cells = []
        
        # Extract site coordinates
        site_coords = (self.site['x'], self.site['y'])
        
        # Load network_defaults from global config
        network_defaults = config.get('network_defaults', {})
        
        for tech_cfg in site_config['technologies']:
            tech_type = tech_cfg.get('type', '')
            # Create cell for each sector in this technology
            for sector_cfg in tech_cfg.get('sectors', []):
                # Add network_defaults to sector config for GsmCell
                sector_cfg_with_defaults = sector_cfg.copy()
                sector_cfg_with_defaults['network_defaults'] = network_defaults
                cell = CellFactory.create(tech_type, sector_cfg_with_defaults, site_coords)
                self.cells.append(cell)
        
        # Вывод информации о ячейках
        print(f"\n{self.id} - Cells ({len(self.cells)}):")
        for i, cell in enumerate(self.cells, 1):
            cell_info = f"  {i}. {cell.id} ({cell.tech_type})"
            cell_info += f" - azimuth: {cell.azimuth}°, antenna: {cell.antenna_type}"
            if hasattr(cell, 'bandwidth'):
                cell_info += f", bandwidth: {cell.bandwidth} MHz"
            if hasattr(cell, 'num_trx'):
                cell_info += f", TRX: {cell.num_trx}"
            if hasattr(cell, 'scs'):
                cell_info += f", SCS: {cell.scs} kHz"
            print(cell_info)
        # # Вывод информации о ячейках
        # print(f"\n{self.id} - Cells ({len(self.cells)}):")
        # for i, cell in enumerate(self.cells, 1):
        #     cell_info = f"  {i}. {cell.id} ({cell.tech_type})"
        #     cell_info += f" - azimuth: {cell.azimuth}°, antenna: {cell.antenna_type}"
        #     if hasattr(cell, 'bandwidth'):
        #         cell_info += f", bandwidth: {cell.bandwidth} MHz"
        #     if hasattr(cell, 'num_trx'):
        #         cell_info += f", TRX: {cell.num_trx}"
        #     if hasattr(cell, 'scs'):
        #         cell_info += f", SCS: {cell.scs} kHz"
        #     print(cell_info)

    def get_available_services(self):
        """Возвращает список доступных технологий на этой вышке."""
        return [cell.technology_type for cell in self.cells]

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
            base_stations[bs['id']] = BaseStation(bs)
        return base_stations

    def __repr__(self):
        return f"Site({self.id}, Cells={len(self.cells)})"

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

class CellFactory:
    @staticmethod
    def create(tech_type, sector_config, site_coords):
        if tech_type == "gsm":
            return GsmCell(sector_config, site_coords)
        elif tech_type == "5g_nr":
            return NrCell(sector_config, site_coords)
        raise ValueError(f"Unknown technology: {tech_type}")

class Cell:
    def __init__(self, config, tech_type, site_coords):
        self.id = config['cell_id']
        self.azimuth = config['azimuth']
        self.tech_type = tech_type
        self.site_coords = site_coords
        self.tx_power = 30  # dBm
        # Антенна всегда directional для секторов
        self.antenna_type = config.get('antenna_type', 'directional')
        # Store frequency for path loss calculation
        # Default frequency based on technology type
        default_freq = 3500 if tech_type == '5g_nr' else 900
        self.frequency_mhz = config.get('frequency_mhz', default_freq)
    
    def calculate_rsrp(self, ue_location):
        """
        Calculate RSRP (Reference Signal Received Power) for UE at given location.
        
        Args:
            ue_location: Tuple (x, y) of user equipment coordinates
        
        Returns:
            RSRP in dBm
        """
        # Calculate distance and path loss
        dist = math.sqrt(
            (ue_location[0] - self.site_coords[0])**2 + 
            (ue_location[1] - self.site_coords[1])**2
        )
        dist = max(dist, 1)
        # Use frequency-aware path loss
        path_loss = get_path_loss(dist, self.frequency_mhz)
        
        # Calculate angle-based attenuation
        angle_loss = get_angle_attenuation(ue_location, self.site_coords, self.azimuth)
        
        # Antenna gain (main lobe gain)
        from network.physics import get_antenna_gain
        antenna_gain = get_antenna_gain(self.antenna_type)
        
        # RSRP = TX Power - Path Loss + Angle Loss + Antenna Gain
        return self.tx_power - path_loss + angle_loss + antenna_gain

class GsmCell(Cell):
    def __init__(self, config, site_coords):
        super().__init__(config, "gsm", site_coords)
        self.num_trx = config['num_trx']
        # Полоса для физики (Link Budget) всегда 0.2 МГц
        self.bandwidth = config['num_trx'] * config['network_defaults']['gsm']['trx_bandwidth_mhz']
        self.resource_mgr = GsmResourceManager(self.num_trx)
    def connect(self, subscriber):
        return self.resource_mgr.allocate(subscriber.id)

class NrCell(Cell):
    def __init__(self, config, site_coords):
        super().__init__(config, "5g_nr", site_coords)
        self.bandwidth = config['bandwidth_mhz']
        self.scs = config.get('scs_khz', 30)
        self.resource_mgr = NrResourceManager(self.bandwidth)
    def connect(self, subscriber):
        return self.resource_mgr.allocate(subscriber.id)