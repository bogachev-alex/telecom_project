"""
Network reporting and visualization module.
"""
import datetime
import matplotlib.pyplot as plt
import math
import numpy as np
from utils.logger import get_logger


def get_report(network):
    """Generate network statistics report including mobility statistics."""
    logger = get_logger()
    logger.info("\n" + "="*30)
    logger.info("--- ДЕТАЛЬНЫЙ ОТЧЕТ СЕТИ ---")
    logger.info(f"Всего попыток звонков: {network.total_attempts}")
    logger.info(f"Успешных соединений: {network.total_successful_calls}")
    logger.info("-" * 30)
    logger.info("--- МОБИЛЬНОСТЬ АБОНЕНТОВ ---")
    logger.info(f"🔄 Active Handovers (во время звонка): {len(network.handover_events)}")
    logger.info(f"📍 Idle Reselections (в ожидании):    {len(network.reselection_events)}")
    
    # Count handovers by type
    if network.handover_events:
        a3_count = sum(1 for ho in network.handover_events if ho.get('type') == 'A3')
        legacy_count = sum(1 for ho in network.handover_events if ho.get('type') == 'legacy')
        logger.info(f"  - Event A3: {a3_count}")
        logger.info(f"  - Legacy: {legacy_count}")
    
    logger.info("-" * 30)
    logger.info("ПРИЧИНЫ НЕУДАЧ:")
    if network.total_attempts > 0:
        logger.info(f" - Перегрузка вышек: {network.blocked_by_capacity} ({network.blocked_by_capacity/network.total_attempts:.2%})")
        logger.info(f" - Нехватка средств: {network.blocked_by_balance} ({network.blocked_by_balance/network.total_attempts:.2%})")
    logger.info("-" * 30)
    
    total_blocked = network.blocked_by_capacity + network.blocked_by_balance
    if network.total_attempts > 0:
        gos = total_blocked / network.total_attempts
        logger.info(f"Общий Grade of Service: {gos:.2%}")
    logger.info("="*30)


def print_subscriber_trace(network, subscriber_id):
    """Print subscriber trace with handover event markers and aggregation."""
    logger = get_logger()
    sub = network.subscribers.get(subscriber_id)
    if not sub or not sub.user_equipment.history:
        logger.info(f"История для {subscriber_id} не найдена.")
        return

    logger.info(f"\n--- ТРАССИРОВКА ДЛЯ {sub.first_name} ---")
    logger.info(f"{'Шаги':<12} | {'БС':<12} | {'RSRP':<15} | {'Событие'}")
    logger.info("-" * 60)

    if not sub.user_equipment.history:
        return
    
    # Aggregate consecutive entries with same BS
    aggregated = []
    current_group = None
    
    for entry in sub.user_equipment.history:
        step = entry.get('sim_step', entry.get('time', 'N/A'))
        current_bs = entry['base_station_id']
        rsrp = entry['rsrp']
        event_type = entry.get('event')
        
        # Determine event
        event = ""
        if event_type == "HANDOVER":
            event = "🔄 HANDOVER"
        elif event_type == "RESELECTION":
            event = "📍 RESELECTION"
        
        # Check if we can aggregate with previous group
        if (current_group and 
            current_group['bs'] == current_bs and 
            current_group['event'] == event and
            abs(current_group['rsrp_max'] - rsrp) < 0.5):  # RSRP within 0.5 dB
            # Extend current group
            current_group['step_end'] = step
            current_group['rsrp_min'] = min(current_group['rsrp_min'], rsrp)
            current_group['rsrp_max'] = max(current_group['rsrp_max'], rsrp)
            current_group['count'] += 1
        else:
            # Save previous group and start new one
            if current_group:
                aggregated.append(current_group)
            
            current_group = {
                'step_start': step,
                'step_end': step,
                'bs': current_bs,
                'rsrp_min': rsrp,
                'rsrp_max': rsrp,
                'event': event,
                'count': 1
            }
    
    # Don't forget the last group
    if current_group:
        aggregated.append(current_group)
    
    # Print aggregated results
    for group in aggregated:
        step_str = f"{group['step_start']}-{group['step_end']}" if group['step_start'] != group['step_end'] else str(group['step_start'])
        rsrp_str = f"{group['rsrp_min']:.1f}" if group['rsrp_min'] == group['rsrp_max'] else f"{group['rsrp_min']:.1f}..{group['rsrp_max']:.1f}"
        count_str = f" ({group['count']})" if group['count'] > 1 else ""
        
        logger.info(f"{step_str:<12} | {group['bs']:<12} | {rsrp_str:<15} | {group['event']}{count_str}")


def plot_subscriber_movement(network, subscriber_id):
    """Plot subscriber movement trajectory with handover points."""
    sub = network.subscribers.get(subscriber_id)
    history = sub.user_equipment.history
    
    if not history:
        print(f"Нет истории для {subscriber_id}")
        return
    
    x_coords = [e['x'] for e in history]
    y_coords = [e['y'] for e in history]
    rsrp_vals = [e['rsrp'] for e in history]

    plt.figure(figsize=(12, 10))
    
    # Draw trajectory line
    plt.plot(x_coords, y_coords, 'b-', alpha=0.3, linewidth=1, label='Траектория')
    
    # Color points by RSRP
    scatter = plt.scatter(x_coords, y_coords, c=rsrp_vals, cmap='RdYlGn', 
                         s=30, alpha=0.7, edgecolors='black', linewidths=0.5,
                         label='Точки измерения', zorder=5)
    plt.colorbar(scatter, label='RSRP (dBm)')
    
    # Mark handover points
    handover_points = []
    last_bs = None
    for i, entry in enumerate(history):
        current_bs = entry['base_station_id']
        if last_bs and current_bs != last_bs:
            handover_points.append((entry['x'], entry['y'], last_bs, current_bs))
        last_bs = current_bs
    
    if handover_points:
        ho_x = [p[0] for p in handover_points]
        ho_y = [p[1] for p in handover_points]
        plt.scatter(ho_x, ho_y, c='magenta', s=200, marker='*', 
                   edgecolors='black', linewidths=1.5, zorder=10,
                   label=f'Хэндоверы ({len(handover_points)})')
        
        # Draw arrows showing handover direction
        for ho_x, ho_y, from_bs, to_bs in handover_points:
            from_bs_obj = network.base_stations.get(from_bs)
            to_bs_obj = network.base_stations.get(to_bs)
            if from_bs_obj and to_bs_obj:
                plt.annotate('', xy=(to_bs_obj.location_x, to_bs_obj.location_y),
                           xytext=(ho_x, ho_y),
                           arrowprops=dict(arrowstyle='->', color='magenta', 
                                         lw=2, alpha=0.6, zorder=8))

    # Plot base stations
    for bs_id, bs in network.base_stations.items():
        plt.plot(bs.location_x, bs.location_y, 'r^', markersize=15, 
                markeredgecolor='black', markeredgewidth=1.5, zorder=9)
        plt.text(bs.location_x + 8, bs.location_y + 8, bs_id, 
                color='red', fontweight='bold', fontsize=9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))

    plt.title(f"Траектория перемещений и хэндоверы: {sub.first_name}", fontsize=14, fontweight='bold')
    plt.xlabel("X (метры)")
    plt.ylabel("Y (метры)")
    plt.grid(True, alpha=0.3)
    plt.xlim(0, 1000)
    plt.ylim(0, 1000)
    plt.legend(loc='upper right', fontsize=9)
    plt.tight_layout()
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

