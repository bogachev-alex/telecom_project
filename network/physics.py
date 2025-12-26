"""
Network physics calculations (link budget, path loss).
"""
import math


def get_distance(subscriber, base_station):
    """Calculate distance between subscriber UE and base station."""
    return math.sqrt(
        (subscriber.user_equipment.location_x - base_station.location_x)**2 + 
        (subscriber.user_equipment.location_y - base_station.location_y)**2
    )


def check_connection_quality(subscriber, base_station):
    """
    Calculate link budget and connection quality.
    Returns (is_good_link, rsrp_dbm).
    """
    dist = get_distance(subscriber, base_station)
    if dist < 1:
        dist = 1
    
    # Path Loss: L = 40 + 30 * log10(d)
    path_loss = 40 + 30 * math.log10(dist)
    
    # DOWNLINK (Base Station -> UE)
    dl_signal = base_station.tx_power - path_loss
    downlink_ok = dl_signal > subscriber.user_equipment.rx_sensitivity
    
    # UPLINK (UE -> Base Station)
    ul_signal = subscriber.user_equipment.tx_power - path_loss
    uplink_ok = ul_signal > base_station.rx_sensitivity
    
    return (downlink_ok and uplink_ok), dl_signal

