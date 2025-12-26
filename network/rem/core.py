import numpy as np
from network.physics import get_path_loss
from base_station.core import BaseStation
from equipment.core import UserEquipment


class CoverageMap:
    def __init__(self, width, height, base_stations):
        self.width = width
        self.height = height
        self.coverage_map = np.full((width, height, 3), -140.0)
        self.coverage_map[:, :, 1] = -1
        self.base_stations = base_stations
        self.bs_id_to_index = {bs_id: idx for idx, bs_id in enumerate(base_stations.keys())}


    def update_coverage_map(self):
        for bs_id, base_station in self.base_stations.items():
            bs_index = self.bs_id_to_index[bs_id]
            for x in range(self.width):
                for y in range(self.height):
                    distance = np.sqrt((x - base_station.location_x)**2 + (y - base_station.location_y)**2)
                    if distance < 1:
                        distance = 1
                    path_loss = get_path_loss(distance)
                    rsrp = base_station.tx_power - path_loss
                    self.coverage_map[x, y, 0] = rsrp
                    self.coverage_map[x, y, 1] = bs_index

if __name__ == "__main__":
    # Тестовый запуск
    test_map = CoverageMap(1000, 1000, BaseStation.get_all_base_stations())
    print("Тест пройден успешно!")
    print(test_map.coverage_map.shape)
    print(test_map.coverage_map)
    coverage_map_data = test_map.update_coverage_map()
    print(test_map.coverage_map)

