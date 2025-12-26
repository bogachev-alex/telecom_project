"""
Network reporting and visualization module.
"""
import datetime
import matplotlib.pyplot as plt


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

