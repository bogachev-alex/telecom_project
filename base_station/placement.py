"""
Optimal base station placement algorithm.
Plans BS locations from scratch for maximum coverage and minimum interference.
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from .core import BaseStation
from .allocation import calculate_optimal_sectors
from network.rem.core import CoverageMap
from .constants import DEFAULT_CAPACITY


class BSPlacementOptimizer:
    """
    Optimizes base station placement on a map.
    
    Strategy:
    1. Grid-based initial placement with hexagonal pattern
    2. Genetic algorithm or simulated annealing for refinement
    3. Frequency assignment with reuse planning
    4. Sector orientation optimization
    """
    
    def __init__(self, width: int, height: int, min_rsrp: float = -110.0, 
                 target_coverage: float = 0.95, frequencies: List[int] = None,
                 bandwidths: List[int] = None):
        """
        Initialize optimizer.
        
        Args:
            width: Map width in meters
            height: Map height in meters
            min_rsrp: Minimum RSRP threshold for coverage (dBm)
            target_coverage: Target coverage percentage (0-1)
            frequencies: Available frequencies in MHz
            bandwidths: Available bandwidths in MHz
        """
        self.width = width
        self.height = height
        self.min_rsrp = min_rsrp
        self.target_coverage = target_coverage
        self.frequencies = frequencies or [900, 1800, 2100]
        self.bandwidths = bandwidths or [10, 15, 20]
        
    def plan_optimal_placement(self, n_bs: Optional[int] = None, 
                               max_iterations: int = 50) -> Dict[str, BaseStation]:
        """
        Plan optimal BS placement from scratch.
        
        Args:
            n_bs: Number of BS to place (auto-calculated if None)
            max_iterations: Maximum optimization iterations
            
        Returns:
            Dictionary of optimally placed BaseStation objects
        """
        if n_bs is None:
            n_bs = self._estimate_required_bs()
        
        # Step 1: Initial hexagonal grid placement
        initial_locations = self._hexagonal_grid_placement(n_bs)
        
        # Step 2: Optimize locations
        optimized_locations = self._optimize_locations(initial_locations, max_iterations)
        
        # Step 3: Assign frequencies with reuse planning
        frequency_assignments = self._assign_frequencies(optimized_locations)
        
        # Step 4: Create BS objects
        base_stations = self._create_base_stations(optimized_locations, frequency_assignments)
        
        # Step 5: Optimize sector orientations
        optimal_sectors = calculate_optimal_sectors(base_stations)
        for bs_id, sectors in optimal_sectors.items():
            base_stations[bs_id].sectors = sectors
        
        return base_stations
    
    def _estimate_required_bs(self) -> int:
        """
        Estimate required number of BS based on coverage radius.
        Uses hexagonal cell model: R = sqrt(3*Area / (2*N))
        """
        # Estimate coverage radius per sector (assuming 65° beamwidth)
        # Typical sector coverage: ~200-300m for urban
        sector_radius = 250  # meters
        cell_radius = sector_radius * 1.5  # Account for 3 sectors
        
        # Hexagonal cell area: A = (3*sqrt(3)/2) * R^2
        cell_area = (3 * np.sqrt(3) / 2) * (cell_radius ** 2)
        total_area = self.width * self.height
        
        n_bs = int(np.ceil(total_area / cell_area))
        return max(n_bs, 4)  # Minimum 4 BS
    
    def _hexagonal_grid_placement(self, n_bs: int) -> List[Tuple[float, float]]:
        """
        Generate hexagonal grid placement for initial BS locations.
        
        Args:
            n_bs: Number of base stations
            
        Returns:
            List of (x, y) coordinates
        """
        # Calculate grid dimensions
        cols = int(np.ceil(np.sqrt(n_bs * self.width / self.height)))
        rows = int(np.ceil(n_bs / cols))
        
        # Hexagonal spacing
        spacing_x = self.width / (cols + 1)
        spacing_y = self.height / (rows + 1)
        hex_offset = spacing_x / 2  # Hexagonal offset
        
        locations = []
        bs_count = 0
        
        for row in range(rows):
            for col in range(cols):
                if bs_count >= n_bs:
                    break
                
                x = spacing_x * (col + 1)
                if row % 2 == 1:  # Offset odd rows for hex pattern
                    x += hex_offset
                
                y = spacing_y * (row + 1)
                
                # Add margin from edges
                x = np.clip(x, 50, self.width - 50)
                y = np.clip(y, 50, self.height - 50)
                
                locations.append((x, y))
                bs_count += 1
            
            if bs_count >= n_bs:
                break
        
        return locations
    
    def _optimize_locations(self, initial_locations: List[Tuple[float, float]], 
                           max_iterations: int) -> List[Tuple[float, float]]:
        """
        Optimize BS locations using simulated annealing.
        
        Args:
            initial_locations: Initial (x, y) coordinates
            max_iterations: Maximum iterations
            
        Returns:
            Optimized (x, y) coordinates
        """
        current_locations = initial_locations.copy()
        best_locations = current_locations.copy()
        best_score = self._evaluate_placement(current_locations)
        
        temperature = 100.0
        cooling_rate = 0.95
        
        for iteration in range(max_iterations):
            # Generate neighbor: move one BS randomly
            neighbor_locations = current_locations.copy()
            move_idx = np.random.randint(len(neighbor_locations))
            
            # Random move (max 50m)
            dx = np.random.uniform(-50, 50)
            dy = np.random.uniform(-50, 50)
            new_x = np.clip(neighbor_locations[move_idx][0] + dx, 50, self.width - 50)
            new_y = np.clip(neighbor_locations[move_idx][1] + dy, 50, self.height - 50)
            neighbor_locations[move_idx] = (new_x, new_y)
            
            # Evaluate neighbor
            neighbor_score = self._evaluate_placement(neighbor_locations)
            
            # Accept if better or with probability (simulated annealing)
            if neighbor_score > best_score or np.random.random() < np.exp((neighbor_score - best_score) / temperature):
                current_locations = neighbor_locations
                if neighbor_score > best_score:
                    best_locations = neighbor_locations
                    best_score = neighbor_score
            
            temperature *= cooling_rate
        
        return best_locations
    
    def _evaluate_placement(self, locations: List[Tuple[float, float]]) -> float:
        """
        Evaluate placement quality (coverage + interference penalty).
        
        Args:
            locations: List of (x, y) coordinates
            
        Returns:
            Fitness score (higher is better)
        """
        # Create temporary BS for evaluation
        temp_bs = {}
        for i, (x, y) in enumerate(locations):
            bs_id = f"BS-TEMP-{i:02d}"
            temp_bs[bs_id] = BaseStation(
                bs_id, DEFAULT_CAPACITY, x, y,
                self.frequencies[i % len(self.frequencies)],
                self.bandwidths[i % len(self.bandwidths)],
                "directional", 0
            )
        
        # Create coverage map
        coverage_map = CoverageMap(self.width, self.height, temp_bs)
        coverage_map.update_coverage_map()
        
        # Calculate coverage percentage
        rsrp = coverage_map.coverage_map[:, :, 0]
        covered = np.sum(rsrp >= self.min_rsrp)
        coverage_ratio = covered / (self.width * self.height)
        
        # Calculate average interference (penalty)
        interference = coverage_map.coverage_map[:, :, 4]
        avg_interference = np.mean(interference[interference > -140])
        interference_penalty = max(0, (avg_interference + 100) / 50)  # Normalize
        
        # Calculate average SINR
        sinr = coverage_map.coverage_map[:, :, 5]
        avg_sinr = np.mean(sinr[sinr > -140])
        sinr_bonus = max(0, (avg_sinr + 10) / 20)  # Normalize
        
        # Fitness: coverage (weight 0.6) + SINR (0.3) - interference (0.1)
        fitness = (coverage_ratio * 0.6 + 
                  sinr_bonus * 0.3 - 
                  interference_penalty * 0.1)
        
        return fitness
    
    def _assign_frequencies(self, locations: List[Tuple[float, float]]) -> List[int]:
        """
        Assign frequencies with reuse planning to minimize interference.
        
        Args:
            locations: List of (x, y) coordinates
            
        Returns:
            List of frequency assignments (MHz)
        """
        n_bs = len(locations)
        assignments = [0] * n_bs
        
        # Calculate distance matrix
        distances = np.zeros((n_bs, n_bs))
        for i in range(n_bs):
            for j in range(n_bs):
                if i != j:
                    dx = locations[i][0] - locations[j][0]
                    dy = locations[i][1] - locations[j][1]
                    distances[i, j] = np.sqrt(dx*dx + dy*dy)
        
        # Frequency reuse: assign same frequency only if distance > threshold
        reuse_distance = 400  # Minimum distance for same frequency (meters)
        
        for i in range(n_bs):
            # Find frequencies used by nearby BS
            nearby_freqs = set()
            for j in range(i):
                if distances[i, j] < reuse_distance:
                    nearby_freqs.add(assignments[j])
            
            # Assign first available frequency
            for freq_idx, freq in enumerate(self.frequencies):
                if freq not in nearby_freqs:
                    assignments[i] = freq
                    break
            else:
                # All frequencies used nearby, use least used
                assignments[i] = self.frequencies[i % len(self.frequencies)]
        
        return assignments
    
    def _create_base_stations(self, locations: List[Tuple[float, float]], 
                             frequencies: List[int]) -> Dict[str, BaseStation]:
        """
        Create BaseStation objects from optimized locations.
        
        Args:
            locations: List of (x, y) coordinates
            frequencies: List of frequency assignments
            
        Returns:
            Dictionary of BaseStation objects
        """
        base_stations = {}
        
        for i, ((x, y), freq) in enumerate(zip(locations, frequencies)):
            bs_id = f"BS-{i+1:02d}"
            bandwidth = self.bandwidths[i % len(self.bandwidths)]
            
            bs = BaseStation(
                bs_id, DEFAULT_CAPACITY, x, y,
                freq, bandwidth, "directional", 0
            )
            base_stations[bs_id] = bs
        
        return base_stations

