"""
Base Station sector types.
"""
from dataclasses import dataclass


@dataclass
class Sector:
    """
    Represents a single sector (directional antenna) of a base station.
    
    Attributes:
        sector_id: Unique identifier within the base station (0, 1, 2)
        azimuth: Pointing direction in degrees (0 = East, 90 = North)
        antenna_type: Type of antenna ("directional" for sectors)
    """
    sector_id: int
    azimuth: float
    antenna_type: str = "directional"

