"""
Mobility Management Entity module.
"""


class MME:
    def __init__(self, network):
        self.network = network

    def select_best_base_station(self, subscriber, base_stations):
        """
        Selects best base station based on measurement reports.
        Returns list of tuples (signal, bs_object), sorted by signal strength.
        """
        candidates = []
        
        for bs in self.network.base_stations.values():
            is_good_link, rsrp = self.network.check_connection_quality(subscriber, bs)
            
            if is_good_link:
                candidates.append((rsrp, bs))
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates

