"""
Main entry point for telecom simulation.
"""
import time
from tariff import Tariff
from network import Network
from base_station import BaseStation
from subscriber import Subscriber
from equipment import UserEquipment
from network.visualizer import LiveVisualizer
from network.reporting import plot_coverage_gradient
import matplotlib.pyplot as plt


if __name__ == "__main__":
    tariff_1 = Tariff("Basic", 1)
    core_network = Network()
    bs1 = BaseStation("BS-01", 1, 500, 500)
    bs2 = BaseStation("BS-02", 1, 300, 300)
    core_network.add_base_station(bs1)
    core_network.add_base_station(bs2)
    sub_ivan = Subscriber("Иван", "Иванов", "1234567890", UserEquipment("UE-01", 400, 500), "ivan@example.com", "1234567890", tariff_1, 0.002, 5)
    sub_maria = Subscriber("Мария", "Петрова", "1234567891", UserEquipment("UE-02", 700, 500), "maria@example.com", "1234567891", tariff_1, 0.001, 10)
    sub_ivan.top_up(100)
    sub_maria.top_up(100)
    core_network.add_subscriber(sub_ivan)
    core_network.add_subscriber(sub_maria)
    core_network.connect_call(sub_ivan, 5, time.time())
    visualizer = LiveVisualizer(core_network)
    for second in range(1, 3600):
        sub_ivan.act(core_network)
        sub_maria.act(core_network)
        core_network.tick()
        print(f"Время: {second} секунда")
        # visualizer.update(sub_ivan.id_number)
    core_network.get_report()
    core_network.print_cdr_report()
    core_network.audit_network_revenue()
    core_network.get_calls_by_phone(sub_ivan.phone)
    core_network.get_calls_by_phone(sub_maria.phone)
    core_network.print_subscriber_trace("1234567890")
    core_network.plot_subscriber_movement("1234567890")
    # visualizer.finalize()
    plot_coverage_gradient(core_network)
    plt.show(block=True)


