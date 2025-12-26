import time
import random
from tariff import Tariff
from network import Network
from base_station.core import BaseStation
from subscriber import Subscriber
from equipment import UserEquipment
import matplotlib.pyplot as plt
from network.reporting import plot_coverage_gradient
from network.physics import interference_calculation, get_signal_strength, get_antenna_gain, noise_calculation, check_connection_quality, get_path_loss
from utils import load_config

if __name__ == "__main__":
    config = load_config("config.yaml")
    core_network = Network()

    # 1. Загружаем тарифы (создаем словарь для быстрого поиска)
    tariffs = {t['name']: Tariff(t['name'], t['price_per_minute']) for t in config['tariffs']}

    # 2. Загружаем базовые станции
    for bs_data in config['base_stations']:
        bs = BaseStation(bs_data['id'], bs_data['frequency_band'], bs_data['x'], bs_data['y'], bs_data['frequency'], bs_data['bandwidth'], bs_data['antenna_type'])
        core_network.add_base_station(bs)

    # 3. Загружаем абонентов
    for sub_data in config['subscribers']:
        ue = UserEquipment(sub_data['id'], random.randint(0, 1000), random.randint(0, 1000))
        # Здесь используем тариф "Basic" из нашего словаря
        sub = Subscriber(
            sub_data['name'], sub_data['surname'], sub_data['phone'], 
            ue, sub_data['email'], sub_data['phone'], 
            tariffs['Basic'], 0.002, 5
        )
        sub.top_up(sub_data['initial_balance'])
        core_network.add_subscriber(sub)

    # 4. Запуск симуляции
    duration = config['simulation']['duration_seconds']
    for second in range(1, duration):
        for sub in core_network.subscribers.values(): 
            sub.act(core_network)
        core_network.tick()
        if second % 100 == 0:
            print(f"Прошло {second} секунд...")

    # Отчеты и графики
    core_network.plot_subscriber_movement("1234567890")
    # plot_coverage_gradient(core_network)
    print("Interference: ", interference_calculation(core_network.base_stations['BS-01'], core_network.base_stations['BS-01'].frequency, core_network.base_stations['BS-01'].bandwidth))
    print("Signal Strength: ", get_signal_strength(core_network.base_stations['BS-01'].tx_power, get_path_loss(100), core_network.base_stations['BS-01'].antenna_type))
    print("Antenna Gain: ", get_antenna_gain(core_network.base_stations['BS-01'].antenna_type))
    print("Noise: ", noise_calculation(core_network.base_stations['BS-01'].bandwidth))
    # print(check_connection_quality(core_network.subscribers['UE-01'].user_equipment, core_network.base_stations['BS-01']))

    print("Все расчеты завершены. Запускаю plt.show()...")
    
    # Блокирующий вызов
    # plt.show(block=True)
    # plt.show()