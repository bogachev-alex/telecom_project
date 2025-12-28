"""
Optimal sector allocation for 3-sector base stations.
"""
import numpy as np
from typing import Dict, List
from .core import BaseStation
from .types import Sector


def calculate_optimal_sectors(base_stations: Dict[str, BaseStation]) -> Dict[str, List[Sector]]:
    """
    Calculate optimal sector orientations for all base stations.
    
    Strategy:
    1. For each BS, calculate sector orientations to minimize interference
    2. Use standard 120° spacing with optimal rotation
    3. Rotate sectors to avoid pointing directly at neighboring BS
    
    Args:
        base_stations: Dictionary of BaseStation objects
        
    Returns:
        Dictionary mapping BS ID to list of 3 Sector objects
    """
    allocations = {}
    
    for bs_id, bs in base_stations.items():
        # Calculate optimal base azimuth
        base_azimuth = _calculate_optimal_base_azimuth(bs, base_stations)
        allocations[bs_id] = _create_sectors(base_azimuth)
    
    return allocations


def _calculate_optimal_base_azimuth(bs: BaseStation, all_bs: Dict[str, BaseStation]) -> float:
    """
    Calculate optimal base azimuth to minimize interference.
    
    Args:
        bs: Base station to optimize
        all_bs: All base stations in network
        
    Returns:
        Optimal base azimuth in degrees
    """
    # Find nearby BS on same frequency (main interference sources)
    nearby_bs = []
    for other_id, other_bs in all_bs.items():
        if other_id == bs.id:
            continue
        if other_bs.frequency != bs.frequency:
            continue
        
        distance = np.sqrt(
            (bs.location_x - other_bs.location_x)**2 +
            (bs.location_y - other_bs.location_y)**2
        )
        if distance < 500:  # Consider BS within 500m as nearby
            angle_to_neighbor = np.degrees(
                np.arctan2(
                    other_bs.location_y - bs.location_y,
                    other_bs.location_x - bs.location_x
                )
            ) % 360
            nearby_bs.append((distance, angle_to_neighbor))
    
    if not nearby_bs:
        # No nearby BS: use default orientation (0° = East)
        return 0.0
    
    # Find angles to avoid (pointing directly at neighbors)
    avoid_angles = [angle for _, angle in nearby_bs]
    
    # Try different base azimuths and find one that minimizes overlap
    best_azimuth = 0.0
    best_score = float('inf')
    
    for test_azimuth in np.arange(0, 360, 15):  # Test every 15°
        sector_azimuths = [
            (test_azimuth - 30) % 360,
            (test_azimuth + 90) % 360,
            (test_azimuth + 210) % 360
        ]
        
        # Calculate penalty: sectors pointing at neighbors
        penalty = 0.0
        for sector_az in sector_azimuths:
            for avoid_angle in avoid_angles:
                angle_diff = min(
                    abs(sector_az - avoid_angle),
                    360 - abs(sector_az - avoid_angle)
                )
                # Penalize if sector points within 30° of neighbor
                if angle_diff < 30:
                    penalty += (30 - angle_diff) / 30.0
        
        if penalty < best_score:
            best_score = penalty
            best_azimuth = test_azimuth
    
    return float(best_azimuth)


def _create_sectors(base_azimuth: float) -> List[Sector]:
    """
    Create 3 sectors with 120° spacing.
    
    Args:
        base_azimuth: Base rotation angle in degrees
        
    Returns:
        List of 3 Sector objects
    """
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
