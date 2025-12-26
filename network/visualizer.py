import matplotlib.pyplot as plt
import math

class LiveVisualizer:
    def __init__(self, network):
        self.network = network
        plt.ion() # Включаем интерактивный режим
        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        
    def calculate_coverage_radius(self, bs):
        """Вычисляет радиус покрытия на основе Link Budget."""
        # Предел: rsrp == rx_sensitivity
        # tx_power - (40 + 30 * log10(dist)) = rx_sensitivity
        exponent = (bs.tx_power - 40 - bs.rx_sensitivity) / 30
        return 10 ** exponent

    def update(self, subscriber_id):
        sub = self.network.subscribers.get(subscriber_id)
        if not sub or not sub.user_equipment.history:
            return

        self.ax.clear()
        ue = sub.user_equipment
        history = ue.history
        
        # 1. Отрисовка вышек и зон покрытия
        for bs in self.network.base_stations.values():
            radius = self.calculate_coverage_radius(bs)
            circle = plt.Circle((bs.location_x, bs.location_y), radius, 
                                color='red', fill=True, alpha=0.05)
            self.ax.add_patch(circle)
            self.ax.plot(bs.location_x, bs.location_y, 'r^', markersize=12)
            self.ax.text(bs.location_x + 5, bs.location_y + 5, bs.id, color='red')

        # 2. Отрисовка пути (цвет зависит от RSRP)
        x_vals = [e['x'] for e in history]
        y_vals = [e['y'] for e in history]
        rsrp_vals = [e['rsrp'] for e in history]
        
        path = self.ax.scatter(x_vals, y_vals, c=rsrp_vals, cmap='RdYlGn', s=10, vmin=-110, vmax=-60)
        
        # 3. Текущая позиция и линия связи
        current_bs_id = history[-1]['base_station_id']
        current_bs = self.network.base_stations.get(current_bs_id)
        
        if current_bs:
            self.ax.plot([ue.location_x, current_bs.location_x], 
                         [ue.location_y, current_bs.location_y], 'b--', alpha=0.4)
        
        self.ax.plot(ue.location_x, ue.location_y, 'bo', markersize=8, label=sub.first_name)

        # Настройка осей
        self.ax.set_xlim(0, 1000)
        self.ax.set_ylim(0, 1000)
        self.ax.set_title(f"Симуляция: {sub.first_name} | BS: {current_bs_id} | RSRP: {history[-1]['rsrp']:.1f} dBm")
        self.ax.grid(True, alpha=0.3)
        
        plt.draw()
        plt.pause(0.001) # Короткая пауза для обновления кадра

    def finalize(self):
        plt.ioff()
        plt.show()