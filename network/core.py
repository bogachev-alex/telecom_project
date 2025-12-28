"""
Network core orchestration module.
"""
import time
from .physics import check_connection_quality
from .cdr import CDRManager
from .reporting import get_report, print_subscriber_trace, plot_subscriber_movement
from core_network import HSS, OCS, MME
from utils.logger import get_logger


class Network:
    def __init__(self):
        self.base_stations = {}
        self.subscribers = {}
        self.active_sessions = []
        self.total_attempts = 0
        self.total_successful_calls = 0
        self.blocked_calls = 0
        self.blocked_by_balance = 0
        self.blocked_by_capacity = 0
        self.mme = MME(self)
        self.hss = HSS()
        self.ocs = OCS()
        self.cdr_manager = CDRManager()
        self.coverage_map = None  # Will be set after base stations are added
        self.handover_events = []  # Active Handover (during call)
        self.reselection_events = []  # Idle Cell Reselection (in standby)
        self.sim_step = 0  # Virtual simulation time

    def tick(self, coverage_map=None):
        """
        Process one time tick: move UEs, handle sessions, handovers.
        
        Phase 1: Move all subscribers and handle Idle Reselection
        Phase 2: Handle active sessions with Handover A3
        
        Args:
            coverage_map: Optional CoverageMap instance for Event A3 handover
        """
        self.sim_step += 1  # Increment virtual time
        cmap = coverage_map if coverage_map else self.coverage_map
        
        # --- PHASE 1: Movement and Idle Reselection (for ALL subscribers) ---
        # Store coverage data for active sessions to avoid double movement
        coverage_data_cache = {}
        
        for sub in self.subscribers.values():
            ue = sub.user_equipment
            old_bs_id = ue.current_serving_bs_id
            
            # Check if subscriber is in active call (once)
            is_in_call = any(s.subscriber == sub for s in self.active_sessions)
            
            # Move and get coverage data
            if cmap is not None:
                coverage_data = ue.step(cmap)  # This calls move() internally
                best_bs_id = coverage_data['serving_bs_id']
                # Cache coverage data for active sessions
                if is_in_call:
                    coverage_data_cache[sub] = coverage_data
            else:
                # Fallback: move only, no reselection without coverage map
                ue.move()
                best_bs_id = old_bs_id
            
            # Handle cell reselection for idle subscribers
            if best_bs_id != old_bs_id and cmap is not None:
                if not is_in_call:
                    # --- IDLE RESELECTION ---
                    if old_bs_id is not None:  # Don't log first appearance
                        get_logger().info(f"📍 [RESELECTION] {sub.first_name}: {old_bs_id} -> {best_bs_id} (Idle)")
                        self.reselection_events.append({
                            'step': self.sim_step,
                            'subscriber': sub.first_name,
                            'from_bs': old_bs_id,
                            'to_bs': best_bs_id,
                            'x': ue.location_x,
                            'y': ue.location_y,
                            'rsrp': coverage_data['serving_rsrp']
                        })
                    ue.current_serving_bs_id = best_bs_id
                    # Log reselection event
                    ue.log_state(time.time(), coverage_data['serving_rsrp'], 
                               best_bs_id, self.sim_step, event_type="RESELECTION")
                # If in call, handover will be handled in Phase 2
            
        # --- PHASE 2: Active Session Handling (Handover A3) ---
        still_active = []
        for session in self.active_sessions:
            session.remaining_time -= 1
            ue = session.subscriber.user_equipment
            source_bs = session.base_station
            
            # Update current serving BS ID in UE
            if ue.current_serving_bs_id != source_bs.id:
                ue.current_serving_bs_id = source_bs.id
            
            # Event A3 handover using coverage map (if available)
            if cmap is not None:
                # Use cached coverage data from Phase 1 (already moved)
                coverage_data = coverage_data_cache.get(session.subscriber)
                if coverage_data is None:
                    # Fallback: lookup without moving (if cache missed)
                    coverage_data = cmap.lookup(ue.location_x, ue.location_y)
                
                # Get actual RSRP from current call BS (not from coverage map serving BS)
                _, current_call_rsrp = check_connection_quality(session.subscriber, source_bs)
                
                # Pass current call RSRP to handover check (first argument)
                should_handover, target_bs_id = ue.check_handover_a3(
                    current_call_rsrp,  # Real signal from current connected BS
                    coverage_data, 
                    cmap, 
                    current_bs_id=source_bs.id,
                    hysteresis_db=3.0  # Standard hysteresis
                )
                
                # Debug: log handover attempts
                target_rsrp = coverage_data.get('serving_rsrp', -140)
                target_bs_id_from_map = coverage_data.get('serving_bs_id')
                delta = target_rsrp - current_call_rsrp
                if target_bs_id_from_map and target_bs_id_from_map != source_bs.id and delta > 0.3:
                    get_logger().info(f"🔍 [HO CHECK] {session.subscriber.first_name}: "
                          f"Current={source_bs.id} ({current_call_rsrp:.1f} dBm), "
                          f"Target={target_bs_id_from_map} ({target_rsrp:.1f} dBm), "
                          f"Δ={delta:.1f} dB, Trigger={ue.handover_trigger_count}/3")
                
                if should_handover and target_bs_id and target_bs_id in self.base_stations and target_bs_id != source_bs.id:
                    target_bs = self.base_stations[target_bs_id]
                    if target_bs.current_calls < target_bs.capacity:
                        target_rsrp = coverage_data['serving_rsrp']
                        delta = target_rsrp - current_call_rsrp
                        get_logger().info(f"🔄 [ACTIVE HANDOVER] {session.subscriber.first_name}: "
                              f"{source_bs.id} ({current_call_rsrp:.1f} dBm) -> "
                              f"{target_bs.id} ({target_rsrp:.1f} dBm) | "
                              f"Δ={delta:.1f} dB | Step: {self.sim_step}")
                        # Log handover event
                        self.handover_events.append({
                            'x': ue.location_x,
                            'y': ue.location_y,
                            'from_bs': source_bs.id,
                            'to_bs': target_bs.id,
                            'subscriber': session.subscriber.first_name,
                            'timestamp': time.time(),
                            'sim_step': self.sim_step,
                            'type': 'A3'
                        })
                        ue.handover_history.append({
                            'x': ue.location_x,
                            'y': ue.location_y,
                            'from_bs': source_bs.id,
                            'to_bs': target_bs.id,
                            'timestamp': time.time(),
                            'sim_step': self.sim_step
                        })
                        source_bs.current_calls -= 1
                        session.base_station = target_bs
                        target_bs.current_calls += 1
                        ue.current_serving_bs_id = target_bs.id
                        current_rsrp = coverage_data['serving_rsrp']
                        # Log with handover event type
                        ue.log_state(time.time(), current_rsrp, target_bs.id, self.sim_step, event_type="HANDOVER")
                    else:
                        # Target BS is full, use coverage data for RSRP
                        current_rsrp = coverage_data['serving_rsrp']
                        ue.log_state(time.time(), current_rsrp, session.base_station.id, self.sim_step)
                else:
                    # No handover needed, use coverage data for RSRP
                    current_rsrp = coverage_data['serving_rsrp']
                    ue.log_state(time.time(), current_rsrp, session.base_station.id, self.sim_step)
            else:
                # Fallback to old method if coverage map not available
                mr = ue.generate_measurement_report(self, session.subscriber)
                _, current_rsrp = check_connection_quality(session.subscriber, source_bs)
                target_bs = source_bs.evaluate_handover(current_rsrp, mr)
                if target_bs and target_bs.current_calls < target_bs.capacity:
                    # Get target RSRP for logging
                    _, target_rsrp = check_connection_quality(session.subscriber, target_bs)
                    delta = target_rsrp - current_rsrp
                    get_logger().info(f"🔄 [ACTIVE HANDOVER] {session.subscriber.first_name}: "
                          f"{source_bs.id} ({current_rsrp:.1f} dBm) -> "
                          f"{target_bs.id} ({target_rsrp:.1f} dBm) | "
                          f"Δ={delta:.1f} dB | Step: {self.sim_step}")
                    # Log handover event
                    self.handover_events.append({
                        'x': ue.location_x,
                        'y': ue.location_y,
                        'from_bs': source_bs.id,
                        'to_bs': target_bs.id,
                        'subscriber': session.subscriber.first_name,
                        'timestamp': time.time(),
                        'sim_step': self.sim_step,
                        'type': 'legacy'
                    })
                    ue.handover_history.append({
                        'x': ue.location_x,
                        'y': ue.location_y,
                        'from_bs': source_bs.id,
                        'to_bs': target_bs.id,
                        'timestamp': time.time(),
                        'sim_step': self.sim_step
                    })
                    source_bs.current_calls -= 1
                    session.base_station = target_bs
                    target_bs.current_calls += 1
                    current_rsrp = target_rsrp
                    # Log with handover event type
                    ue.log_state(time.time(), current_rsrp, target_bs.id, self.sim_step, event_type="HANDOVER")
                else:
                    # No handover, log normal state
                    ue.log_state(time.time(), current_rsrp, session.base_station.id, self.sim_step)

            is_good_link = current_rsrp > ue.rx_sensitivity
            
            if not is_good_link:
                get_logger().warning(f"❌ [DROPPED] {session.subscriber.first_name} потерял сеть в точке ({ue.location_x:.1f}, {ue.location_y:.1f})")
                self.cdr_manager.close_session(session, "DROPPED")
            elif session.remaining_time <= 0:
                self.cdr_manager.close_session(session, "COMPLETED")
            else:
                still_active.append(session)

        self.active_sessions = still_active

    def add_base_station(self, base_station):
        self.base_stations[base_station.id] = base_station

    def add_subscriber(self, subscriber):
        self.subscribers[subscriber.phone] = subscriber
        self.hss.add_subscriber(subscriber.id_number, subscriber)

    def connect_call(self, subscriber, duration, start_time):
        """Establish call connection through network."""
        self.total_attempts += 1
        estimated_cost = duration * subscriber.tariff.get_cost_per_minute()
        
        if not self.hss.get_subscriber(subscriber.id_number):
            self.blocked_calls += 1
            return False

        towers = self.mme.select_best_base_station(subscriber, self.base_stations.values())
        if not towers:
            self.blocked_by_capacity += 1
            return False

        # Try each tower in order until we find one with capacity
        for signal, bs in towers:
            if bs.current_calls < bs.capacity:
                session = bs.connect_call(subscriber, duration, start_time)
                if session:
                    self.ocs.charge_subscriber(subscriber, estimated_cost)
                    self.active_sessions.append(session)
                    self.total_successful_calls += 1
                    return True
        
        # All towers are full - count as single blocking event
        self.blocked_by_capacity += 1
        return False

    def check_connection_quality(self, subscriber, base_station):
        """Delegate to physics module."""
        return check_connection_quality(subscriber, base_station)

    def get_report(self):
        """Delegate to reporting module."""
        get_report(self)

    def print_cdr_report(self):
        """Delegate to CDR manager."""
        self.cdr_manager.print_cdr_report()

    def audit_network_revenue(self):
        """Delegate to CDR manager."""
        self.cdr_manager.audit_network_revenue()

    def get_calls_by_phone(self, phone_number):
        """Delegate to CDR manager."""
        return self.cdr_manager.get_calls_by_phone(phone_number)

    def print_subscriber_trace(self, subscriber_id):
        """Delegate to reporting module."""
        print_subscriber_trace(self, subscriber_id)

    def plot_subscriber_movement(self, subscriber_id):
        """Delegate to reporting module."""
        plot_subscriber_movement(self, subscriber_id)

