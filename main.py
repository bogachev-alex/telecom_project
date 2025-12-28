import time
import random
import numpy as np
import matplotlib.pyplot as plt
from tariff import Tariff
from network import Network
from base_station.core import BaseStation
from subscriber import Subscriber
from equipment import UserEquipment
from network.reporting import plot_coverage_gradient
from network.physics import interference_calculation, get_signal_strength, get_antenna_gain, noise_calculation, check_connection_quality, get_path_loss
from network.rem.core import CoverageMap
from utils import load_config


def visualize_coverage(coverage, network=None):
    """Visualize coverage map layers with handover points."""
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    
    # Layer 0: RSRP
    im0 = axes[0, 0].imshow(coverage.coverage_map[:, :, 0], cmap='RdYlGn', origin='lower')
    axes[0, 0].set_title('RSRP (dBm)')
    axes[0, 0].set_xlabel('X')
    axes[0, 0].set_ylabel('Y')
    plt.colorbar(im0, ax=axes[0, 0])
    
    # Layer 1: Serving BS Index
    im1 = axes[0, 1].imshow(coverage.coverage_map[:, :, 1], cmap='tab10', origin='lower')
    axes[0, 1].set_title('Serving BS Index')
    plt.colorbar(im1, ax=axes[0, 1])
    
    # Layer 2: Candidate RSRP
    im2 = axes[0, 2].imshow(coverage.coverage_map[:, :, 2], cmap='RdYlGn', origin='lower')
    axes[0, 2].set_title('Candidate RSRP (dBm)')
    plt.colorbar(im2, ax=axes[0, 2])
    
    # Layer 3: Candidate BS Index
    im3 = axes[1, 0].imshow(coverage.coverage_map[:, :, 3], cmap='tab10', origin='lower')
    axes[1, 0].set_title('Candidate BS Index')
    plt.colorbar(im3, ax=axes[1, 0])
    
    # Layer 4: Interference
    im4 = axes[1, 1].imshow(coverage.coverage_map[:, :, 4], cmap='hot', origin='lower')
    axes[1, 1].set_title('Interference (dBm)')
    plt.colorbar(im4, ax=axes[1, 1])
    
    # Layer 5: SINR
    im5 = axes[1, 2].imshow(coverage.coverage_map[:, :, 5], cmap='RdYlGn', origin='lower')
    axes[1, 2].set_title('SINR (dB)')
    axes[1, 2].set_xlabel('X')
    axes[1, 2].set_ylabel('Y')
    plt.colorbar(im5, ax=axes[1, 2])
    
    # Overlay base station locations with frequency colors on all plots
    frequency_colors = {900: 'blue', 1800: 'green', 2100: 'red'}
    
    for ax in axes.flat:
        for bs in coverage.base_stations.values():
            freq_color = frequency_colors.get(bs.frequency, 'gray')
            ax.scatter(
                bs.location_x, bs.location_y,
                c=freq_color, s=150, marker='^', 
                edgecolors='white', linewidths=2, 
                zorder=10, alpha=0.8
            )
            # Add frequency label
            ax.annotate(
                f'{bs.id}\n{bs.frequency}MHz',
                xy=(bs.location_x, bs.location_y),
                xytext=(5, 5), textcoords='offset points',
                fontsize=7, color='white',
                bbox=dict(boxstyle='round,pad=0.3', facecolor=freq_color, alpha=0.7),
                zorder=11
            )
    
    # Add frequency legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='blue', label='900 MHz'),
        Patch(facecolor='green', label='1800 MHz'),
        Patch(facecolor='red', label='2100 MHz')
    ]
    axes[1, 2].legend(handles=legend_elements, loc='upper left', fontsize=8)
    
    # Overlay handover points on SINR plot
    if network and network.handover_events:
        ho_x = [ho['x'] for ho in network.handover_events]
        ho_y = [ho['y'] for ho in network.handover_events]
        axes[1, 2].scatter(
            ho_x, ho_y,
            c='magenta', s=200, marker='*', 
            edgecolors='black', linewidths=1.5,
            zorder=15, alpha=0.9, label='Handovers'
        )
        # Add arrows showing handover direction
        for ho in network.handover_events[:20]:  # Limit to first 20 for clarity
            from_bs = coverage.base_stations.get(ho['from_bs'])
            to_bs = coverage.base_stations.get(ho['to_bs'])
            if from_bs and to_bs:
                axes[1, 2].annotate(
                    '', xy=(to_bs.location_x, to_bs.location_y),
                    xytext=(ho['x'], ho['y']),
                    arrowprops=dict(arrowstyle='->', color='magenta', lw=1.5, alpha=0.6)
                )
        axes[1, 2].legend(handles=legend_elements + [
            plt.Line2D([0], [0], marker='*', color='w', markerfacecolor='magenta', 
                      markersize=10, label='Handovers', markeredgecolor='black')
        ], loc='upper left', fontsize=8)
    
    plt.tight_layout()


def visualize_handovers(network, coverage_map):
    """Visualize handover events on coverage map."""
    if not network.handover_events:
        print("Нет хендоверов для визуализации")
        return
    
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    
    # Show SINR as background
    im = ax.imshow(coverage_map.coverage_map[:, :, 5], cmap='RdYlGn', origin='lower', alpha=0.7)
    ax.set_title('Handover Events on SINR Map', fontsize=14, fontweight='bold')
    ax.set_xlabel('X (meters)')
    ax.set_ylabel('Y (meters)')
    plt.colorbar(im, ax=ax, label='SINR (dB)')
    
    # Plot base stations
    frequency_colors = {900: 'blue', 1800: 'green', 2100: 'red'}
    for bs in coverage_map.base_stations.values():
        freq_color = frequency_colors.get(bs.frequency, 'gray')
        ax.scatter(
            bs.location_x, bs.location_y,
            c=freq_color, s=300, marker='^', 
            edgecolors='white', linewidths=3, 
            zorder=10, alpha=0.9, label=f'{bs.frequency} MHz' if bs.frequency not in [freq for _, freq in frequency_colors.items() if _ == bs.frequency] else None
        )
        ax.annotate(
            bs.id, xy=(bs.location_x, bs.location_y),
            xytext=(0, -20), textcoords='offset points',
            fontsize=9, color='white', fontweight='bold',
            ha='center', bbox=dict(boxstyle='round,pad=0.3', facecolor=freq_color, alpha=0.8)
        )
    
    # Plot handover points
    ho_x = [ho['x'] for ho in network.handover_events]
    ho_y = [ho['y'] for ho in network.handover_events]
    ax.scatter(
        ho_x, ho_y,
        c='magenta', s=300, marker='*', 
        edgecolors='black', linewidths=2,
        zorder=15, alpha=1.0, label=f'Handovers ({len(network.handover_events)})'
    )
    
    # Draw handover arrows (from point to target BS)
    for ho in network.handover_events:
        to_bs = coverage_map.base_stations.get(ho['to_bs'])
        if to_bs:
            ax.annotate(
                '', xy=(to_bs.location_x, to_bs.location_y),
                xytext=(ho['x'], ho['y']),
                arrowprops=dict(arrowstyle='->', color='magenta', lw=2, alpha=0.7, zorder=12)
            )
    
    # Add legend
    from matplotlib.patches import Patch
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, coverage_map.width)
    ax.set_ylim(0, coverage_map.height)
    
    plt.tight_layout()
    return fig


def visualize_interference_dashboard(coverage_map):
    """Create interference dashboard: overall and per-frequency maps."""
    # Get unique frequencies
    frequencies = sorted(set(bs.frequency for bs in coverage_map.base_stations.values()))
    
    # Calculate interference maps per frequency
    interference_maps = {}
    for freq in frequencies:
        interference_maps[freq] = coverage_map.calculate_interference_by_frequency(freq)
    
    # Create figure with subplots: 1 overall + N per frequency
    n_freqs = len(frequencies)
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    axes = axes.flatten()
    
    # Overall interference map
    im0 = axes[0].imshow(coverage_map.coverage_map[:, :, 4], cmap='hot', origin='lower', vmin=-140, vmax=-35)
    axes[0].set_title('Overall Interference (All Frequencies)', fontsize=12, fontweight='bold')
    axes[0].set_xlabel('X (meters)')
    axes[0].set_ylabel('Y (meters)')
    plt.colorbar(im0, ax=axes[0], label='Interference (dBm)')
    
    # Per-frequency interference maps
    frequency_colors = {900: 'blue', 1800: 'green', 2100: 'red'}
    frequency_names = {900: '900 MHz', 1800: '1800 MHz', 2100: '2100 MHz'}
    
    for idx, freq in enumerate(frequencies, start=1):
        if idx >= len(axes):
            break
        
        im = axes[idx].imshow(interference_maps[freq], cmap='hot', origin='lower', vmin=-140, vmax=-35)
        axes[idx].set_title(f'Interference at {frequency_names.get(freq, f"{freq} MHz")}', 
                           fontsize=12, fontweight='bold')
        axes[idx].set_xlabel('X (meters)')
        axes[idx].set_ylabel('Y (meters)')
        plt.colorbar(im, ax=axes[idx], label='Interference (dBm)')
        
        # Overlay BS on this frequency
        freq_color = frequency_colors.get(freq, 'gray')
        for bs in coverage_map.base_stations.values():
            if bs.frequency == freq:
                axes[idx].scatter(
                    bs.location_x, bs.location_y,
                    c=freq_color, s=200, marker='^',
                    edgecolors='white', linewidths=2,
                    zorder=10, alpha=0.9
                )
                axes[idx].annotate(
                    bs.id, xy=(bs.location_x, bs.location_y),
                    xytext=(0, -15), textcoords='offset points',
                    fontsize=8, color='white', fontweight='bold',
                    ha='center', bbox=dict(boxstyle='round,pad=0.3', facecolor=freq_color, alpha=0.8)
                )
    
    # Hide unused subplots
    for idx in range(len(frequencies) + 1, len(axes)):
        axes[idx].axis('off')
    
    # Add BS to overall map
    for bs in coverage_map.base_stations.values():
        freq_color = frequency_colors.get(bs.frequency, 'gray')
        axes[0].scatter(
            bs.location_x, bs.location_y,
            c=freq_color, s=200, marker='^',
            edgecolors='white', linewidths=2,
            zorder=10, alpha=0.9
        )
        axes[0].annotate(
            f'{bs.id}\n{bs.frequency}MHz',
            xy=(bs.location_x, bs.location_y),
            xytext=(5, 5), textcoords='offset points',
            fontsize=7, color='white',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=freq_color, alpha=0.7),
            zorder=11
        )
    
    # Add frequency legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='blue', label='900 MHz'),
        Patch(facecolor='green', label='1800 MHz'),
        Patch(facecolor='red', label='2100 MHz')
    ]
    axes[0].legend(handles=legend_elements, loc='upper right', fontsize=9)
    
    plt.suptitle('Interference Dashboard', fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout()
    return fig


def visualize_capacity_map(coverage_map):
    """
    Visualize capacity map using Shannon-Hartley theorem.
    Shows maximum achievable throughput (Mbps) at each location.
    Uses log scale to show wide range of values.
    """
    capacity_map = coverage_map.calculate_capacity_map()
    
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    
    # Use log scale for better visualization of wide range (0.001 to 140+ Mbps)
    # Apply log1p to handle zeros: log(1 + capacity)
    capacity_log = np.log1p(capacity_map)  # log(1 + x) handles zeros gracefully
    
    # Set reasonable limits for log scale
    vmin_log = 0.0
    if np.any(capacity_map > 0):
        vmax_log = np.log1p(capacity_map.max())
    else:
        vmax_log = 1.0
    
    # Display with log scale
    im = ax.imshow(capacity_log, cmap='plasma', origin='lower', 
                   interpolation='bilinear', vmin=vmin_log, vmax=vmax_log)
    ax.set_title('Capacity Map (Shannon-Hartley, Log Scale)', fontsize=14, fontweight='bold')
    ax.set_xlabel('X (meters)')
    ax.set_ylabel('Y (meters)')
    
    # Create colorbar with original scale labels
    cbar = plt.colorbar(im, ax=ax, label='Capacity (Mbps, log scale)')
    
    # Add tick labels showing actual Mbps values
    # Generate ticks at meaningful capacity values
    tick_capacities = [0, 0.01, 0.1, 1, 5, 10, 20, 50, 100, capacity_map.max()]
    tick_capacities = [c for c in tick_capacities if c <= capacity_map.max()]
    tick_positions = [np.log1p(c) for c in tick_capacities]
    cbar.set_ticks(tick_positions)
    cbar.set_ticklabels([f'{c:.2f}' if c < 1 else f'{c:.0f}' for c in tick_capacities])
    
    # Add note about scale
    ax.text(0.02, 0.98, f'Log scale: 0 - {capacity_map.max():.1f} Mbps', 
            transform=ax.transAxes, fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # Overlay base stations with frequency colors
    frequency_colors = {900: 'blue', 1800: 'green', 2100: 'red'}
    for bs in coverage_map.base_stations.values():
        freq_color = frequency_colors.get(bs.frequency, 'gray')
        ax.scatter(
            bs.location_x, bs.location_y,
            c=freq_color, s=300, marker='^',
            edgecolors='white', linewidths=3,
            zorder=10, alpha=0.9
        )
        ax.annotate(
            f'{bs.id}\n{bs.frequency}MHz\n{bs.bandwidth}MHz BW',
            xy=(bs.location_x, bs.location_y),
            xytext=(0, -25), textcoords='offset points',
            fontsize=8, color='white', fontweight='bold',
            ha='center', bbox=dict(boxstyle='round,pad=0.3', facecolor=freq_color, alpha=0.8)
        )
    
    # Add frequency legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='blue', label='900 MHz'),
        Patch(facecolor='green', label='1800 MHz'),
        Patch(facecolor='red', label='2100 MHz')
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=9)
    
    # Print statistics
    print(f"\nCapacity Map Statistics:")
    print(f"  Min: {capacity_map.min():.4f} Mbps")
    print(f"  Max: {capacity_map.max():.2f} Mbps")
    print(f"  Mean: {capacity_map.mean():.4f} Mbps")
    print(f"  Median: {np.median(capacity_map):.4f} Mbps")
    if np.any(capacity_map > 0):
        p95 = np.percentile(capacity_map[capacity_map > 0], 95)
        p99 = np.percentile(capacity_map[capacity_map > 0], 99)
        print(f"  95th percentile: {p95:.2f} Mbps")
        print(f"  99th percentile: {p99:.2f} Mbps")
        
        # Show distribution of non-zero values
        non_zero = capacity_map[capacity_map > 0]
        print(f"\n  Non-zero capacity points: {len(non_zero)} / {capacity_map.size} ({100*len(non_zero)/capacity_map.size:.1f}%)")
        print(f"  Non-zero mean: {non_zero.mean():.4f} Mbps")
        print(f"  Non-zero median: {np.median(non_zero):.4f} Mbps")
        
        # Show capacity by bandwidth
        print(f"\n  Capacity by bandwidth:")
        for bw in sorted(set(bs.bandwidth for bs in coverage_map.base_stations.values())):
            # Find points served by BS with this bandwidth
            bw_mask = np.zeros_like(capacity_map, dtype=bool)
            for bs_id, bs in coverage_map.base_stations.items():
                if bs.bandwidth == bw:
                    bs_idx = coverage_map.bs_id_to_index.get(bs_id, -1)
                    if bs_idx >= 0:
                        serving_mask = coverage_map.coverage_map[:, :, 1] == bs_idx
                        bw_mask |= serving_mask
            if np.any(bw_mask):
                bw_capacity = capacity_map[bw_mask]
                bw_non_zero = bw_capacity[bw_capacity > 0]
                if len(bw_non_zero) > 0:
                    print(f"    {bw} MHz: mean={bw_non_zero.mean():.4f} Mbps, max={bw_non_zero.max():.2f} Mbps, "
                          f"points={len(bw_non_zero)}/{len(bw_capacity)}")
    
    plt.tight_layout()
    return fig




if __name__ == "__main__":
    config = load_config("config.yaml")
    core_network = Network()

    # 1. Загружаем тарифы (создаем словарь для быстрого поиска)
    tariffs = {t['name']: Tariff(t['name'], t['price_per_minute']) for t in config['tariffs']}

    # 2. Оптимальное размещение базовых станций
    print("Планирование оптимального размещения базовых станций...")
    from base_station.placement import BSPlacementOptimizer
    
    width, height = 1000, 1000
    frequencies = [f['frequency'] for f in config['frequencies']]
    bandwidths = [f['bandwidth'] for f in config['frequencies']]
    
    optimizer = BSPlacementOptimizer(
        width=width,
        height=height,
        min_rsrp=-110.0,
        target_coverage=0.95,
        frequencies=frequencies,
        bandwidths=bandwidths
    )
    
    # Plan optimal placement (auto-calculates number of BS)
    optimal_bs = optimizer.plan_optimal_placement(n_bs=None, max_iterations=30)
    
    print(f"\nРазмещено {len(optimal_bs)} базовых станций:")
    for bs_id, bs in optimal_bs.items():
        core_network.add_base_station(bs)
        sector_azimuths = [f'{s.azimuth:.0f}°' for s in bs.sectors]
        print(f"  {bs_id}: ({bs.location_x:.0f}, {bs.location_y:.0f}), "
              f"{bs.frequency} MHz, {bs.bandwidth} MHz, секторы {sector_azimuths}")

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

    # 4. Создание карты покрытия для Event A3 handover
    print("\nСоздание карты покрытия...")
    coverage_map = CoverageMap(width, height, core_network.base_stations)
    coverage_map.update_coverage_map()
    core_network.coverage_map = coverage_map
    print("Карта покрытия создана. Запуск симуляции с Event A3 handover...")
    
    # 5. Запуск симуляции
    duration = config['simulation']['duration_seconds']
    for second in range(1, duration):
        for sub in core_network.subscribers.values(): 
            sub.act(core_network)
        core_network.tick(coverage_map)
        if second % 100 == 0:
            print(f"Прошло {second} секунд...")

    # Отчеты и графики
    if core_network.subscribers:
        first_sub_id = list(core_network.subscribers.keys())[0]
        core_network.plot_subscriber_movement(first_sub_id)
    
    # Print network statistics
    if core_network.base_stations:
        first_bs_id = list(core_network.base_stations.keys())[0]
        first_bs = core_network.base_stations[first_bs_id]
        print("Interference: ", interference_calculation(first_bs, first_bs.frequency, first_bs.bandwidth))
        print("Signal Strength: ", get_signal_strength(first_bs.tx_power, get_path_loss(100), first_bs.antenna_type))
        print("Antenna Gain: ", get_antenna_gain(first_bs.antenna_type))
        print("Noise: ", noise_calculation(first_bs.bandwidth))
    
    # Print coverage statistics
    rsrp = coverage_map.coverage_map[:, :, 0]
    interference = coverage_map.coverage_map[:, :, 4]
    sinr = coverage_map.coverage_map[:, :, 5]
    print(f"RSRP range: {rsrp.min():.2f} to {rsrp.max():.2f} dBm")
    print(f"Interference range: {interference.min():.2f} to {interference.max():.2f} dBm")
    print(f"SINR range: {sinr.min():.2f} to {sinr.max():.2f} dB")
    print(f"SINR mean: {sinr.mean():.2f} dB, median: {np.median(sinr):.2f} dB")
    
    # Check SINR values for capacity calculation
    valid_sinr = sinr[sinr > -140]
    if len(valid_sinr) > 0:
        sinr_linear_sample = 10 ** (valid_sinr / 10.0)
        print(f"SINR linear range: {sinr_linear_sample.min():.6f} to {sinr_linear_sample.max():.6f}")
        # Test capacity for 20 MHz at different SINR levels
        test_bw = 20e6  # 20 MHz in Hz
        for test_sinr_db in [-10, 0, 10, 20]:
            test_sinr_lin = 10 ** (test_sinr_db / 10.0)
            test_cap = test_bw * np.log2(1.0 + test_sinr_lin) / 1e6
            print(f"  Capacity at SINR={test_sinr_db} dB: {test_cap:.2f} Mbps")
    
    # Visualize coverage map
    visualize_coverage(coverage_map, core_network)
    
    # Interference dashboard
    print("\nСоздание дашборда интерференции...")
    visualize_interference_dashboard(coverage_map)
    
    # Capacity map
    print("\nСоздание карты пропускной способности...")
    # Verify bandwidth values before calculating capacity
    print("Проверка bandwidth базовых станций:")
    for bs_id, bs in coverage_map.base_stations.items():
        print(f"  {bs_id}: {bs.bandwidth} MHz")
    visualize_capacity_map(coverage_map)
    
    # Print handover statistics
    print(f"\nВсего хендоверов: {len(core_network.handover_events)}")
    if core_network.handover_events:
        print("Примеры хендоверов:")
        for i, ho in enumerate(core_network.handover_events[:5]):
            print(f"  {i+1}. {ho['subscriber']}: {ho['from_bs']} -> {ho['to_bs']} в точке ({ho['x']:.1f}, {ho['y']:.1f})")
        
        # Visualize handovers separately
        visualize_handovers(core_network, coverage_map)
    
    print("Все расчеты завершены. Запускаю plt.show()...")
    plt.show()