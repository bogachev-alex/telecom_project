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
    
    # Path Loss: L = 40 + 30 * log10(d)
    path_loss = get_path_loss(dist)
    
    # DOWNLINK (Base Station -> UE)
    dl_signal = base_station.tx_power - path_loss
    downlink_ok = dl_signal > user_equipment.rx_sensitivity
    
    # UPLINK (UE -> Base Station)
    ul_signal = user_equipment.tx_power - path_loss
    uplink_ok = ul_signal > base_station.rx_sensitivity
    
    return (downlink_ok and uplink_ok), dl_signal

def get_path_loss(distance):
    return 40 + 30 * math.log10(distance)

def get_signal_strength(tx_power, path_loss, antenna_type):
    rsrp = tx_power + get_antenna_gain(antenna_type) - path_loss
    print(f"RSRP: {rsrp}")
    return rsrp

def get_antenna_gain(antenna_type):
    if antenna_type == "omni":
        return 0
    elif antenna_type == "directional":
        return 10
    else:
        return 0

def noise_calculation(bandwidth):
    return -174 + 10 * math.log10(bandwidth*10**6)



def interference_calculation(base_station, frequency, bandwidth):
    interference = 0
    for bs in base_station.neighbors:
        if bs.frequency == frequency:
            interference += 10 ** (bs.tx_power - get_path_loss(get_distance(base_station, bs)) / 10)
    print(f"Interference: {interference}")
    return interference + noise_calculation(bandwidth)




