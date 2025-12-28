import numpy as np
from network.physics import get_path_loss, get_antenna_gain, noise_calculation
from base_station.core import BaseStation


class CoverageMap:
    def __init__(self, width, height, base_stations):
        self.width = width
        self.height = height
        self.coverage_map = np.full((width, height, 6), -140.0)
        self.coverage_map[:, :, 1] = -1
        self.coverage_map[:, :, 3] = -1
        self.coverage_map[:, :, 4] = 0.0
        self.base_stations = base_stations
        self.bs_id_to_index = {bs_id: idx for idx, bs_id in enumerate(base_stations.keys())}
        self.index_to_bs_id = {idx: bs_id for bs_id, idx in self.bs_id_to_index.items()}
        self.bs_id_to_numeric = self._create_numeric_id_map()
        x_coords = np.arange(self.width)
        y_coords = np.arange(self.height)
        self.X, self.Y = np.meshgrid(x_coords, y_coords)

    def _create_numeric_id_map(self):
        """Extract numeric ID from BS ID string (e.g., 'BS-01' -> 1)."""
        numeric_map = {}
        for bs_id in self.base_stations.keys():
            try:
                numeric_part = ''.join(filter(str.isdigit, bs_id))
                numeric_map[bs_id] = int(numeric_part) if numeric_part else 0
            except (ValueError, AttributeError):
                numeric_map[bs_id] = 0
        return numeric_map

    def calculate_distance(self, bs_x, bs_y):
        """Calculate distance matrix from base station to all grid points."""
        return np.sqrt((self.X - bs_x)**2 + (self.Y - bs_y)**2)

    def calculate_path_loss(self, distance, frequency_mhz):
        """
        Calculate path loss with frequency-dependent propagation.
        Synchronized with network.physics.get_path_loss() for consistency.
        
        Formula: L = 32.44 + 20*log10(f_MHz) + 20*log10(d_km) + Urban_Loss
        Where Urban_Loss = 25 dB accounts for urban environment.
        
        Args:
            distance: Distance in meters (numpy array)
            frequency_mhz: Frequency in MHz (scalar or array)
            
        Returns:
            Path loss in dB (numpy array)
        """
        distance_km = np.maximum(distance, 1) / 1000.0
        # Free Space Path Loss (FSPL) - same formula as physics.py
        fspl = 32.44 + 20 * np.log10(frequency_mhz) + 20 * np.log10(distance_km)
        # Urban clutter loss: higher frequencies have more penetration loss (same as physics.py)
        clutter_loss = np.where(frequency_mhz >= 2000, 30, 25)
        return fspl + clutter_loss

    def calculate_angle_to_point(self, bs_x, bs_y, azimuth_deg):
        """
        Calculate angle from base station to each grid point using np.arctan2.
        
        Args:
            bs_x: Base station X coordinate
            bs_y: Base station Y coordinate
            azimuth_deg: Antenna azimuth in degrees (0 = East, 90 = North)
            
        Returns:
            Angle matrix in degrees (0-360), where 0 = East, 90 = North
        """
        dx = self.X - bs_x
        dy = self.Y - bs_y
        # Calculate angle using np.arctan2(Y, X): 0 = East, 90 = North, counterclockwise
        angle_rad = np.arctan2(dy, dx)
        angle_deg = np.degrees(angle_rad)
        # Convert to 0-360 range (0 = East, 90 = North, 180 = West, 270 = South)
        angle_deg = (angle_deg + 360) % 360
        return angle_deg

    def calculate_directional_attenuation(self, angle_to_point, azimuth_deg, theta_3db=65, a_max=30):
        """
        Calculate directional antenna attenuation using Gaussian approximation.
        
        Formula: A(θ) = -min[12 * ((θ - φ) / θ_3dB)^2, A_max]
        where θ is angle to point, φ is azimuth, θ_3dB is 3dB beamwidth.
        
        Args:
            angle_to_point: Angle from BS to point in degrees (0-360)
            azimuth_deg: Antenna pointing direction in degrees (0-360)
            theta_3db: 3dB beamwidth in degrees (default 65° for sector antenna)
            a_max: Maximum attenuation in dB (default 30 dB)
            
        Returns:
            Attenuation in dB (0 = no attenuation, positive = signal reduction)
        """
        # Calculate angular difference, normalized to -180 to 180 range
        angle_diff = angle_to_point - azimuth_deg
        # Normalize to -180 to 180 range
        angle_diff = np.where(angle_diff > 180, angle_diff - 360, angle_diff)
        angle_diff = np.where(angle_diff < -180, angle_diff + 360, angle_diff)
        # Take absolute value for symmetric pattern
        angle_diff = np.abs(angle_diff)
        
        # Gaussian approximation: A(θ) = -min[12 * ((θ - φ) / θ_3dB)^2, A_max]
        # This gives -3dB at θ_3dB/2 from center
        attenuation_squared = 12 * (angle_diff / theta_3db) ** 2
        attenuation = np.minimum(attenuation_squared, a_max)
        
        return attenuation

    def calculate_rsrp(self, bs_id, sector=None):
        """
        Calculate RSRP matrix for a base station (or specific sector) across the entire coverage area.
        
        Args:
            bs_id: Base station identifier
            sector: Optional Sector object. If None, returns best RSRP across all sectors.
            
        Returns:
            RSRP matrix in dBm
        """
        base_station = self.base_stations[bs_id]
        distance = self.calculate_distance(base_station.location_x, base_station.location_y)
        path_loss = self.calculate_path_loss(distance, base_station.frequency)
        antenna_gain = get_antenna_gain("directional" if hasattr(base_station, 'sectors') else base_station.antenna_type)
        
        # Handle 3-sector configuration
        if hasattr(base_station, 'sectors') and base_station.sectors:
            if sector is not None:
                # Calculate for specific sector
                angle_to_point = self.calculate_angle_to_point(
                    base_station.location_x,
                    base_station.location_y,
                    sector.azimuth
                )
                directional_attenuation = self.calculate_directional_attenuation(
                    angle_to_point,
                    sector.azimuth
                )
                effective_gain = antenna_gain - directional_attenuation
            else:
                # Calculate for all sectors and return best
                rsrp_sectors = []
                for sec in base_station.sectors:
                    angle_to_point = self.calculate_angle_to_point(
                        base_station.location_x,
                        base_station.location_y,
                        sec.azimuth
                    )
                    directional_attenuation = self.calculate_directional_attenuation(
                        angle_to_point,
                        sec.azimuth
                    )
                    effective_gain = antenna_gain - directional_attenuation
                    rsrp_sector = base_station.tx_power + effective_gain - path_loss
                    rsrp_sectors.append(rsrp_sector)
                # Return maximum RSRP across all sectors
                return np.maximum.reduce(rsrp_sectors) if rsrp_sectors else base_station.tx_power - path_loss
        else:
            # Legacy: single antenna
            if base_station.antenna_type == "directional":
                angle_to_point = self.calculate_angle_to_point(
                    base_station.location_x,
                    base_station.location_y,
                    base_station.azimuth
                )
                directional_attenuation = self.calculate_directional_attenuation(
                    angle_to_point,
                    base_station.azimuth
                )
                effective_gain = antenna_gain - directional_attenuation
            else:
                effective_gain = get_antenna_gain(base_station.antenna_type)
        
        rsrp = base_station.tx_power + effective_gain - path_loss
        return rsrp

    def update_coverage_map(self):
        """Update coverage map with serving BS, candidate BS, interference, and SINR calculations.
        
        Includes RAT Priority: 5G (wideband > 10 MHz) gets priority over GSM if signal is acceptable (> -105 dBm).
        """
        # First pass: calculate RSRP for all BS and determine best by signal strength
        rsrp_matrices = {}
        for bs_id, base_station in self.base_stations.items():
            rsrp_matrices[bs_id] = self.calculate_rsrp(bs_id)
        
        # Initialize coverage map with best RSRP and find second best (candidate)
        for bs_id, base_station in self.base_stations.items():
            bs_index = self.bs_id_to_index[bs_id]
            RSRP_matrix = rsrp_matrices[bs_id]
            is_new_best = RSRP_matrix > self.coverage_map[:, :, 0]
            
            # Convert current serving BS indices to numeric IDs before update
            current_bs_indices = self.coverage_map[:, :, 1].astype(int)
            current_numeric_ids = np.full_like(current_bs_indices, -1.0, dtype=float)
            for idx, current_bs_id in self.index_to_bs_id.items():
                mask = current_bs_indices == idx
                current_numeric_ids[mask] = self.bs_id_to_numeric[current_bs_id]
            
            # Store old leader as candidate where new BS wins
            self.coverage_map[:, :, 2] = np.where(is_new_best, self.coverage_map[:, :, 0], self.coverage_map[:, :, 2])
            self.coverage_map[:, :, 3] = np.where(is_new_best, current_numeric_ids, self.coverage_map[:, :, 3])
            
            # Also update candidate if this BS is second best (better than current candidate but not best)
            is_second_best = (RSRP_matrix > self.coverage_map[:, :, 2]) & (~is_new_best) & (self.coverage_map[:, :, 1] != bs_index)
            numeric_id = self.bs_id_to_numeric[bs_id]
            self.coverage_map[:, :, 2] = np.where(is_second_best, RSRP_matrix, self.coverage_map[:, :, 2])
            self.coverage_map[:, :, 3] = np.where(is_second_best, numeric_id, self.coverage_map[:, :, 3])
            
            # New BS becomes leader
            self.coverage_map[:, :, 0] = np.where(is_new_best, RSRP_matrix, self.coverage_map[:, :, 0])
            self.coverage_map[:, :, 1] = np.where(is_new_best, bs_index, self.coverage_map[:, :, 1])
        
        # Second pass: Apply RAT Priority - 5G gets priority if signal is acceptable
        # 5G is identified by bandwidth > 10 MHz (vs GSM ~0.2-0.6 MHz)
        priority_threshold = -105.0  # dBm - acceptable signal for 5G
        
        # Build map of current serving BS technology (5G or not)
        current_serving_index = self.coverage_map[:, :, 1].astype(int)
        current_is_5g_map = np.zeros_like(current_serving_index, dtype=bool)
        for idx, serving_bs_id in self.index_to_bs_id.items():
            mask = current_serving_index == idx
            if np.any(mask):
                current_is_5g_map[mask] = self.base_stations[serving_bs_id].bandwidth > 10.0
        
        # Check all 5G BS for priority override
        for bs_id, base_station in self.base_stations.items():
            bs_index = self.bs_id_to_index[bs_id]
            is_5g = base_station.bandwidth > 10.0  # Wideband = 5G/4G
            RSRP_matrix = rsrp_matrices[bs_id]
            
            if not is_5g:
                continue  # Only process 5G BS in priority pass
            
            # Priority condition: 5G wins if signal is acceptable, even if GSM is stronger
            is_priority = (RSRP_matrix > priority_threshold) & (~current_is_5g_map)
            
            if np.any(is_priority):
                # Store current serving as candidate
                current_rsrp = self.coverage_map[:, :, 0]
                current_numeric_ids = np.full_like(current_serving_index, -1.0, dtype=float)
                for idx, current_bs_id in self.index_to_bs_id.items():
                    mask = current_serving_index == idx
                    current_numeric_ids[mask] = self.bs_id_to_numeric[current_bs_id]
                
                self.coverage_map[:, :, 2] = np.where(is_priority, current_rsrp, self.coverage_map[:, :, 2])
                self.coverage_map[:, :, 3] = np.where(is_priority, current_numeric_ids, self.coverage_map[:, :, 3])
                
                # 5G becomes serving
                self.coverage_map[:, :, 0] = np.where(is_priority, RSRP_matrix, self.coverage_map[:, :, 0])
                self.coverage_map[:, :, 1] = np.where(is_priority, bs_index, self.coverage_map[:, :, 1])
                
                # Update current_is_5g_map for subsequent iterations
                current_is_5g_map = np.where(is_priority, True, current_is_5g_map)
        
        # Second pass: calculate interference from all non-serving BS on same frequency
        # CRITICAL: Serving BS signal must NOT be included in interference
        self.coverage_map[:, :, 4] = 0.0
        serving_bs_indices = self.coverage_map[:, :, 1].astype(int)
        serving_frequency_map = np.zeros_like(serving_bs_indices, dtype=float)
        
        # Build serving frequency map
        for idx, freq_bs_id in self.index_to_bs_id.items():
            mask = serving_bs_indices == idx
            serving_frequency_map[mask] = self.base_stations[freq_bs_id].frequency
        
        # Sum interference from all BS sectors on same frequency (except serving BS)
        # Frequency filter: BS on different frequencies don't interfere with each other
        for bs_id, base_station in self.base_stations.items():
            bs_index = self.bs_id_to_index[bs_id]
            # Calculate interference from all sectors of this BS
            # All sectors transmit simultaneously, so sum their interference
            interference_linear = np.zeros((self.width, self.height))
            if hasattr(base_station, 'sectors') and base_station.sectors:
                for sector in base_station.sectors:
                    RSRP_matrix = self.calculate_rsrp(bs_id, sector=sector)
                    interference_linear += 10 ** (RSRP_matrix / 10)
            else:
                RSRP_matrix = self.calculate_rsrp(bs_id)
                interference_linear = 10 ** (RSRP_matrix / 10)
            
            # Interference condition: same frequency AND not serving BS
            is_same_frequency = base_station.frequency == serving_frequency_map
            is_not_serving = serving_bs_indices != bs_index
            has_serving_bs = serving_bs_indices >= 0
            is_interference = is_same_frequency & is_not_serving & has_serving_bs
            
            # Sum interference in linear domain
            self.coverage_map[:, :, 4] += np.where(is_interference, interference_linear, 0)
        
        # Convert interference back to dBm
        # Only convert if there's actual interference (avoid log(0))
        # When multiple BS on same frequency overlap, interference sums up significantly
        self.coverage_map[:, :, 4] = np.where(
            self.coverage_map[:, :, 4] > 0,
            10 * np.log10(np.maximum(self.coverage_map[:, :, 4], 10**(-14))),
            -140.0  # No interference
        )
        # Clamp to reasonable range
        self.coverage_map[:, :, 4] = np.maximum(self.coverage_map[:, :, 4], -140)
        # Don't limit maximum too aggressively - interference can be significant when multiple BS overlap
        # With 13 BS, areas between same-frequency cells should show strong interference
        # Allow up to -35 dBm (very strong interference from multiple nearby BS on same frequency)
        self.coverage_map[:, :, 4] = np.minimum(self.coverage_map[:, :, 4], -35)
        
        # Calculate SINR correctly: SINR_linear = Signal / (Interference + Noise)
        # CRITICAL FIX: Previously we calculated SINR as RSRP - (I+N) in dB, which is correct for dB,
        # but for Shannon formula we need the RATIO in linear scale, not the difference.
        # 
        # Correct approach:
        # 1. Convert all powers to linear scale (milliwatts)
        # 2. Calculate ratio: SINR_linear = Signal_mW / (Interference_mW + Noise_mW)
        # 3. Convert to dB: SINR_dB = 10 * log10(SINR_linear)
        #
        # Example: If signal = 7 mW (8.48 dBm) and noise = 1e-11 mW (-114 dBm),
        # then SINR_linear = 7 / 1e-11 = 700,000,000,000 (not 7!)
        # This gives massive capacity, as expected.
        
        serving_bs_indices = self.coverage_map[:, :, 1].astype(int)
        noise_map = np.zeros_like(serving_bs_indices, dtype=float)
        for idx, noise_bs_id in self.index_to_bs_id.items():
            mask = serving_bs_indices == idx
            bandwidth = self.base_stations[noise_bs_id].bandwidth
            noise_map[mask] = noise_calculation(bandwidth)  # Returns noise in dBm
        
        # Convert all powers to linear scale (milliwatts)
        signal_linear = 10 ** (self.coverage_map[:, :, 0] / 10)  # RSRP in mW
        interference_linear = 10 ** (self.coverage_map[:, :, 4] / 10)  # Interference in mW
        noise_linear = 10 ** (noise_map / 10)  # Thermal noise in mW (typically ~1e-11 mW for 1 MHz)
        
        # Calculate SINR as ratio: SINR_linear = Signal / (Interference + Noise)
        # This is the correct ratio for Shannon formula: C = B * log2(1 + SINR_linear)
        total_interference_plus_noise = interference_linear + noise_linear
        sinr_linear = signal_linear / np.maximum(total_interference_plus_noise, 10**(-14))
        
        # Store SINR in dB for visualization and other uses
        # SINR [dB] = 10 * log10(SINR_linear)
        sinr_db = 10 * np.log10(np.maximum(sinr_linear, 10**(-14)))
        
        # Store in coverage map (layer 5)
        self.coverage_map[:, :, 5] = sinr_db

    def calculate_interference_by_frequency(self, frequency_mhz):
        """
        Calculate interference map for a specific frequency.
        Shows interference from all BS on this frequency (except serving BS).
        
        Args:
            frequency_mhz: Frequency in MHz (900, 1800, or 2100)
            
        Returns:
            Interference map in dBm for the specified frequency
        """
        interference_map = np.zeros((self.width, self.height), dtype=float)
        
        # Get serving BS indices and frequencies
        serving_bs_indices = self.coverage_map[:, :, 1].astype(int)
        serving_frequency_map = np.zeros_like(serving_bs_indices, dtype=float)
        
        for idx, freq_bs_id in self.index_to_bs_id.items():
            mask = serving_bs_indices == idx
            serving_frequency_map[mask] = self.base_stations[freq_bs_id].frequency
        
        # Sum interference from all BS sectors on target frequency (except serving BS)
        for bs_id, base_station in self.base_stations.items():
            if base_station.frequency != frequency_mhz:
                continue
            
            bs_index = self.bs_id_to_index[bs_id]
            
            # Sum interference from all sectors
            interference_linear = np.zeros((self.width, self.height))
            if hasattr(base_station, 'sectors') and base_station.sectors:
                for sector in base_station.sectors:
                    RSRP_matrix = self.calculate_rsrp(bs_id, sector=sector)
                    interference_linear += 10 ** (RSRP_matrix / 10)
            else:
                RSRP_matrix = self.calculate_rsrp(bs_id)
                interference_linear = 10 ** (RSRP_matrix / 10)
            
            # Interference: target frequency AND not serving BS
            is_target_frequency = serving_frequency_map == frequency_mhz
            is_not_serving = serving_bs_indices != bs_index
            is_interference = is_target_frequency & is_not_serving
            
            interference_map += np.where(is_interference, interference_linear, 0)
        
        # Convert back to dBm
        interference_map = np.where(
            interference_map > 0,
            10 * np.log10(np.maximum(interference_map, 10**(-14))),
            -140.0
        )
        interference_map = np.maximum(interference_map, -140)
        interference_map = np.minimum(interference_map, -35)
        
        return interference_map

    def calculate_capacity_map(self):
        """
        Calculate capacity map using Shannon-Hartley theorem.
        
        Formula: C = B * log2(1 + SINR_linear)
        Where:
            C - capacity in bits/sec
            B - bandwidth in Hz
            SINR_linear - signal-to-interference-plus-noise ratio in linear scale
        
        Returns:
            Capacity map in Mbps (megabits per second)
        """
        # Get SINR in dB from coverage map (now correctly calculated as ratio)
        sinr_db = self.coverage_map[:, :, 5]
        
        # Convert SINR from dB to linear: SINR_linear = 10^(SINR_dB/10)
        # This is now the correct ratio: Signal / (Interference + Noise)
        sinr_linear = np.power(10, sinr_db / 10.0)
        
        # Ensure we don't have negative or zero values (shouldn't happen with correct calculation)
        sinr_linear = np.maximum(sinr_linear, 10**(-14))
        
        # Get bandwidth for each point from serving BS
        serving_bs_indices = self.coverage_map[:, :, 1].astype(int)
        bandwidth_map = np.zeros_like(serving_bs_indices, dtype=float)
        
        # Debug: print bandwidth values for each BS
        bandwidth_values = {}
        for idx, bs_id in self.index_to_bs_id.items():
            bandwidth_mhz = self.base_stations[bs_id].bandwidth
            bandwidth_values[bs_id] = bandwidth_mhz
            mask = serving_bs_indices == idx
            # Bandwidth is in MHz, convert to Hz
            bandwidth_hz = bandwidth_mhz * 1e6
            bandwidth_map[mask] = bandwidth_hz
        
        # Print bandwidth distribution for debugging
        print(f"  Bandwidth distribution: {bandwidth_values}")
        
        # Verify calculation with test values
        test_bw_mhz = 20.0
        test_sinr_db = 10.0  # Good signal
        test_sinr_linear = 10 ** (test_sinr_db / 10.0)
        test_capacity_bps = test_bw_mhz * 1e6 * np.log2(1.0 + test_sinr_linear)
        test_capacity_mbps = test_capacity_bps / 1e6
        print(f"  Verification: {test_bw_mhz} MHz, SINR={test_sinr_db} dB -> {test_capacity_mbps:.2f} Mbps (expected ~69 Mbps)")
        
        # Calculate capacity: C = B * log2(1 + SINR_linear)
        # Formula: C [bits/sec] = B [Hz] * log2(1 + SINR_linear)
        # Where: bandwidth_map is in Hz, sinr_linear is dimensionless
        # Result: capacity_bps in bits/sec
        capacity_bps = bandwidth_map * np.log2(1.0 + sinr_linear)
        
        # Convert to Mbps (megabits per second): 1 Mbps = 1,000,000 bits/sec
        # Verify: bandwidth_map is in Hz (MHz * 1e6), so capacity_bps is in bits/sec
        capacity_mbps = capacity_bps / 1e6
        
        # Sanity check: for 20 MHz at SINR=10 dB, should get ~69 Mbps
        # 20 MHz = 20e6 Hz, SINR_linear = 10, log2(11) ≈ 3.46
        # 20e6 * 3.46 / 1e6 ≈ 69 Mbps ✓
        
        # Debug: verify units are correct
        if np.any(capacity_mbps > 0):
            max_capacity = capacity_mbps.max()
            max_idx = np.unravel_index(np.argmax(capacity_mbps), capacity_mbps.shape)
            max_sinr_db = sinr_db[max_idx]
            max_sinr_linear = sinr_linear[max_idx]
            max_bw_hz = bandwidth_map[max_idx]
            max_bw_mhz = max_bw_hz / 1e6
            print(f"  Max capacity point: {max_capacity:.2f} Mbps at ({max_idx[1]}, {max_idx[0]})")
            print(f"    SINR={max_sinr_db:.2f} dB, SINR_linear={max_sinr_linear:.6f}, BW={max_bw_mhz:.1f} MHz ({max_bw_hz:.0f} Hz)")
            print(f"    Calculation: {max_bw_hz:.0f} Hz * log2(1 + {max_sinr_linear:.6f}) = {capacity_bps[max_idx]:.0f} bps = {max_capacity:.2f} Mbps")
        
        # Debug: print sample values for verification
        valid_mask = (sinr_db > -140) & (serving_bs_indices >= 0) & (serving_bs_indices < len(self.index_to_bs_id))
        if np.any(valid_mask):
            # Find point with good SINR for example
            valid_sinr = sinr_db[valid_mask]
            if len(valid_sinr) > 0:
                # Find point near median SINR
                median_sinr = np.median(valid_sinr)
                best_idx = np.argmin(np.abs(sinr_db - median_sinr))
                i, j = np.unravel_index(best_idx, sinr_db.shape)
                
                sample_sinr_db = sinr_db[i, j]
                sample_sinr_linear = sinr_linear[i, j]
                sample_bw_hz = bandwidth_map[i, j]
                sample_capacity_mbps = capacity_mbps[i, j]
                print(f"  Sample (median SINR): SINR={sample_sinr_db:.2f} dB, SINR_linear={sample_sinr_linear:.6f}, "
                      f"BW={sample_bw_hz/1e6:.1f} MHz, Capacity={sample_capacity_mbps:.4f} Mbps")
                
                # Also show best case
                best_sinr_idx = np.argmax(sinr_db)
                bi, bj = np.unravel_index(best_sinr_idx, sinr_db.shape)
                best_sinr_db = sinr_db[bi, bj]
                best_sinr_linear = sinr_linear[bi, bj]
                best_bw_hz = bandwidth_map[bi, bj]
                best_capacity_mbps = capacity_mbps[bi, bj]
                print(f"  Best case: SINR={best_sinr_db:.2f} dB, SINR_linear={best_sinr_linear:.6f}, "
                      f"BW={best_bw_hz/1e6:.1f} MHz, Capacity={best_capacity_mbps:.2f} Mbps")
        
        # Handle invalid values (negative SINR, no serving BS)
        # serving_bs_indices == -1 means no serving BS
        capacity_mbps = np.where(valid_mask, capacity_mbps, 0.0)
        
        # Additional check: ensure we're not losing precision for small values
        # For very low SINR, capacity should still be > 0 if SINR > -140 dB
        # Example: SINR = -40 dB, BW = 20 MHz
        # SINR_linear = 10^(-40/10) = 0.0001
        # C = 20e6 * log2(1.0001) ≈ 20e6 * 0.000144 ≈ 2.88 Mbps
        # So even at -40 dB we should have measurable capacity
        
        return capacity_mbps

    def lookup(self, x, y):
        """
        Lookup coverage data at specific coordinates.
        UE simply reads pre-calculated data from the map.
        
        Args:
            x: X coordinate (0 to width-1)
            y: Y coordinate (0 to height-1)
            
        Returns:
            Dictionary with coverage data:
            - serving_rsrp: RSRP of serving BS (dBm)
            - serving_bs_index: Index of serving BS
            - candidate_rsrp: RSRP of candidate BS (dBm)
            - candidate_bs_id: Numeric ID of candidate BS
            - interference: Interference level (dBm)
            - sinr: SINR (dB)
        """
        # Convert coordinates to array indices (clamp to valid range)
        idx_x = int(np.clip(x, 0, self.width - 1))
        idx_y = int(np.clip(y, 0, self.height - 1))
        
        serving_bs_index = int(self.coverage_map[idx_y, idx_x, 1])
        serving_bs_id = self.index_to_bs_id.get(serving_bs_index, None)
        
        return {
            'serving_rsrp': float(self.coverage_map[idx_y, idx_x, 0]),
            'serving_bs_index': serving_bs_index,
            'serving_bs_id': serving_bs_id,
            'candidate_rsrp': float(self.coverage_map[idx_y, idx_x, 2]),
            'candidate_bs_id': int(self.coverage_map[idx_y, idx_x, 3]) if self.coverage_map[idx_y, idx_x, 3] >= 0 else None,
            'interference': float(self.coverage_map[idx_y, idx_x, 4]),
            'sinr': float(self.coverage_map[idx_y, idx_x, 5])
        }
