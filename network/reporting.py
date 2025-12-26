"""
Network reporting and visualization module.
"""
import datetime
import matplotlib.pyplot as plt
import math
import numpy as np


def get_report(network):
    """Generate network statistics report."""
    print("\n" + "="*30)
    print("--- ДЕТАЛЬНЫЙ ОТЧЕТ СЕТИ ---")
    print(f"Всего попыток: {network.total_attempts}")
    print(f"Успешных звонков: {network.total_successful_calls}")
    print("-" * 30)
    print("ПРИЧИНЫ НЕУДАЧ:")
    print(f" - Перегрузка вышек: {network.blocked_by_capacity} ({network.blocked_by_capacity/network.total_attempts:.2%})")
    print(f" - Нехватка средств: {network.blocked_by_balance} ({network.blocked_by_balance/network.total_attempts:.2%})")
    print("-" * 30)
    
    total_blocked = network.blocked_by_capacity + network.blocked_by_balance
    if network.total_attempts > 0:
        gos = total_blocked / network.total_attempts
        print(f"Общий Grade of Service: {gos:.2%}")
    print("="*30)


def print_subscriber_trace(network, subscriber_id):
    """Print subscriber movement and signal quality trace."""
    sub = network.subscribers.get(subscriber_id)
    if not sub or not sub.user_equipment.history:
        print(f"История для {subscriber_id} не найдена.")
        return

    print(f"\n--- ТРАССИРОВКА ПЕРЕМЕЩЕНИЙ И СИГНАЛА ДЛЯ {sub.first_name} ---")
    print(f"{'Время':<12} | {'X':<6} | {'Y':<6} | {'RSRP':<8} | {'Качество':<10} | {'БС'}")
    print("-" * 70)

    for entry in sub.user_equipment.history:
        readable_time = datetime.datetime.fromtimestamp(entry['time']).strftime('%H:%M:%S')
        
        val = entry['rsrp']
        if val > -80:
            q = "Excellent"
        elif val > -90:
            q = "Good"
        elif val > -100:
            q = "Fair"
        else:
            q = "Poor"

        print(f"{readable_time:<12} | "
            f"{entry['x']:<6.1f} | "
            f"{entry['y']:<6.1f} | "
            f"{entry['rsrp']:<8.1f} | "
            f"{q:<10} | "
            f"{entry['base_station_id']}")


def plot_subscriber_movement(network, subscriber_id):
    """Plot subscriber movement map with signal strength."""
    sub = network.subscribers.get(subscriber_id)
    history = sub.user_equipment.history
    
    x_coords = [e['x'] for e in history]
    y_coords = [e['y'] for e in history]
    rsrp_vals = [e['rsrp'] for e in history]

    plt.figure(figsize=(10, 8))
    
    path = plt.scatter(x_coords, y_coords, c=rsrp_vals, cmap='RdYlGn', label='Путь абонента')
    plt.colorbar(path, label='RSRP (dBm)')

    for bs_id, bs in network.base_stations.items():
        plt.plot(bs.location_x, bs.location_y, 'r^', markersize=12)
        plt.text(bs.location_x + 5, bs.location_y + 5, bs_id, color='red', fontweight='bold')

    plt.title(f"Карта перемещений и уровня сигнала: {sub.first_name}")
    plt.xlabel("X (метры)")
    plt.ylabel("Y (метры)")
    plt.grid(True)
    plt.xlim(0, 1000)
    plt.ylim(0, 1000)
    plt.show()

def plot_coverage_gradient(network, resolution=15):
    """
    Строит карту покрытия с плавным переходом:
    Зеленый (-50 дБм и выше) -> Желтый -> Красный (-110 дБм и ниже).
    """
    # 1. Подготовка сетки координат
    x = np.linspace(0, 1000, 1000 // resolution)
    y = np.linspace(0, 1000, 1000 // resolution)
    X, Y = np.meshgrid(x, y)
    Z = np.full(X.shape, -140.0) # Фоновое значение (очень слабый сигнал)

    # 2. Расчет максимального RSRP для каждой точки сетки
    for bs in network.base_stations.values():
        # Дистанция от каждой точки сетки до текущей БС
        dist_sq = (X - bs.location_x)**2 + (Y - bs.location_y)**2
        dist = np.sqrt(np.maximum(dist_sq, 1.0))
        
        # Формула Path Loss: L = 40 + 30 * log10(d) [из physics.py]
        path_loss = 40 + 30 * np.log10(dist)
        rsrp = bs.tx_power - path_loss
        
        # Выбираем лучший сигнал из всех доступных вышек
        Z = np.maximum(Z, rsrp)

    # 3. Визуализация
    plt.figure(figsize=(11, 8))
    
    # vmin/vmax фиксируют границы цветов: 
    # -50 будет ярко-зеленым, -110 ярко-красным
    levels = np.linspace(-115, -45, 70)
    contour = plt.contourf(X, Y, Z, levels=levels, cmap='RdYlGn', vmin=-110, vmax=-50)
    
    # Добавляем цветовую шкалу с пояснениями
    cbar = plt.colorbar(contour)
    cbar.set_label('Уровень сигнала RSRP (dBm)', rotation=270, labelpad=15)
    
    # Отрисовка самих вышек [из base_station/core.py]
    for bs in network.base_stations.values():
        plt.plot(bs.location_x, bs.location_y, 'k^', markersize=10)
        plt.text(bs.location_x + 15, bs.location_y + 15, bs.id, 
                 fontsize=10, fontweight='bold', bbox=dict(facecolor='white', alpha=0.6))

    plt.title("Тепловая карта покрытия сети: Градиент качества сигнала")
    plt.xlabel("X (метры)")
    plt.ylabel("Y (метры)")
    plt.grid(True, alpha=0.2, linestyle='--')
    plt.show()