"""
Network physics calculations (link budget, path loss).
"""
import math


def get_distance(user_equipment, base_station):
    """Calculate distance between subscriber UE and base station."""
    return math.sqrt(
        (user_equipment.location_x - base_station.location_x)**2 + 
        (user_equipment.location_y - base_station.location_y)**2
    )


def check_connection_quality(subscriber_or_ue, base_station):
    """
    Calculate link budget and connection quality.
    Returns (is_good_link, rsrp_dbm).
    """
    # Extract user_equipment if subscriber is passed
    user_equipment = subscriber_or_ue.user_equipment if hasattr(subscriber_or_ue, 'user_equipment') else subscriber_or_ue
    
    dist = get_distance(user_equipment, base_station)
    if dist < 1:
        dist = 1
    
    # Get frequency from base_station (Cell has frequency_mhz, CoverageBaseStation has frequency)
    frequency = getattr(base_station, 'frequency_mhz', getattr(base_station, 'frequency', 900))
    path_loss = get_path_loss(dist, frequency)
    
    # Get antenna gain
    antenna_type = getattr(base_station, 'antenna_type', 'directional')
    antenna_gain = get_antenna_gain(antenna_type)
    
    # DOWNLINK (Base Station -> UE)
    dl_signal = base_station.tx_power - path_loss + antenna_gain
    downlink_ok = dl_signal > user_equipment.rx_sensitivity
    
    # UPLINK (UE -> Base Station)
    ul_signal = user_equipment.tx_power - path_loss
    uplink_ok = ul_signal > base_station.rx_sensitivity
    
    return (downlink_ok and uplink_ok), dl_signal

def get_path_loss(distance, frequency_mhz=900):
    """
    Universal path loss formula with frequency dependency.
    
    Formula: L = 32.44 + 20*log10(f_MHz) + 20*log10(d_km) + Clutter_Loss
    Where Clutter_Loss = 25 dB for < 2000 MHz, 30 dB for >= 2000 MHz
    (higher frequencies have more penetration loss in urban environments).
    
    Args:
        distance: Distance in meters
        frequency_mhz: Frequency in MHz (default 900 for GSM)
        
    Returns:
        Path loss in dB
    """
    dist_km = max(distance, 1) / 1000.0
    # Free Space Path Loss (FSPL)
    fspl = 32.44 + 20 * math.log10(frequency_mhz) + 20 * math.log10(dist_km)
    # Urban clutter loss: higher frequencies (5G) have more penetration loss
    clutter_loss = 30 if frequency_mhz >= 2000 else 25
    return fspl + clutter_loss


def get_angle_attenuation(ue_coords, site_coords, antenna_azimuth, beamwidth=65):
    """
    Calculate signal attenuation based on angle between antenna direction and UE position.
    
    Args:
        ue_coords: Tuple (x, y) of user equipment coordinates
        site_coords: Tuple (x, y) of base station site coordinates
        antenna_azimuth: Antenna pointing direction in degrees (0 = East, 90 = North)
        beamwidth: Antenna beamwidth in degrees (default 65 for standard sector antenna)
    
    Returns:
        Attenuation in dB (negative value, to be added to signal strength)
    """
    # Calculate angle from site to UE
    dx = ue_coords[0] - site_coords[0]
    dy = ue_coords[1] - site_coords[1]
    
    # Angle in degrees (0 = East, 90 = North)
    angle_to_ue = math.degrees(math.atan2(dy, dx))
    angle_to_ue = (angle_to_ue + 360) % 360
    
    # Calculate shortest angular difference (accounting for wrap-around)
    diff = abs(antenna_azimuth - angle_to_ue)
    diff = min(diff, 360 - diff)
    
    # Gaussian pattern approximation: loss = -12 * (diff / beamwidth)^2
    loss = -12 * (diff / beamwidth) ** 2
    
    # Cap rear attenuation at -25 dB
    return max(loss, -25)

def get_signal_strength(tx_power, path_loss, antenna_type):
    rsrp = tx_power + get_antenna_gain(antenna_type) - path_loss
    print(f"RSRP: {rsrp}")
    return rsrp

def get_antenna_gain(antenna_type):
    """
    Antenna gain for different antenna types.
    Directional sector antennas typically have 15-18 dBi gain.
    """
    if antenna_type == "omni":
        return 0
    elif antenna_type == "directional":
        return 18  # Increased for realism (typical sector antenna gain)
    else:
        return 0

def noise_calculation(bandwidth):
    return -174 + 10 * math.log10(bandwidth*10**6)



def interference_calculation(base_station, frequency, bandwidth):
    interference = 0
    for bs in base_station.neighbors:
        if bs.frequency == frequency:
            dist = get_distance(base_station, bs)
            # Use frequency for path loss calculation
            path_loss = get_path_loss(dist, frequency)
            interference += 10 ** (bs.tx_power - path_loss / 10)
    print(f"Interference: {interference}")
    return interference + noise_calculation(bandwidth)






