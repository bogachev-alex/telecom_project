"""
Network core orchestration module.
"""
import time
from .physics import check_connection_quality
from .cdr import CDRManager
from .reporting import get_report, print_subscriber_trace, plot_subscriber_movement
from core_network import HSS, OCS, MME


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
        self.handover_events = []  # List of handover events: [(x, y, from_bs_id, to_bs_id, subscriber_name, timestamp)]

    def tick(self, coverage_map=None):
        """
        Process one time tick: move UEs, handle sessions, handovers.
        
        Args:
            coverage_map: Optional CoverageMap instance for Event A3 handover
        """
        # Use provided coverage map or instance variable
        cmap = coverage_map if coverage_map else self.coverage_map
        
        for subscriber in self.subscribers.values():
            subscriber.user_equipment.move()
            
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
                coverage_data = ue.step(cmap)
                should_handover, target_bs_id = ue.check_handover_a3(coverage_data, cmap)
                
                if should_handover and target_bs_id and target_bs_id in self.base_stations:
                    target_bs = self.base_stations[target_bs_id]
                    if target_bs.current_calls < target_bs.capacity:
                        print(f"🔄 [HANDOVER A3] {session.subscriber.first_name}: {source_bs.id} -> {target_bs.id} "
                              f"(Candidate RSRP: {coverage_data['candidate_rsrp']:.2f} > Serving: {coverage_data['serving_rsrp']:.2f} + 3dB)")
                        # Log handover event
                        self.handover_events.append({
                            'x': ue.location_x,
                            'y': ue.location_y,
                            'from_bs': source_bs.id,
                            'to_bs': target_bs.id,
                            'subscriber': session.subscriber.first_name,
                            'timestamp': time.time()
                        })
                        ue.handover_history.append({
                            'x': ue.location_x,
                            'y': ue.location_y,
                            'from_bs': source_bs.id,
                            'to_bs': target_bs.id,
                            'timestamp': time.time()
                        })
                        source_bs.current_calls -= 1
                        session.base_station = target_bs
                        target_bs.current_calls += 1
                        ue.current_serving_bs_id = target_bs.id
                        current_rsrp = coverage_data['serving_rsrp']
                    else:
                        # Target BS is full, use coverage data for RSRP
                        current_rsrp = coverage_data['serving_rsrp']
                else:
                    # No handover needed, use coverage data for RSRP
                    current_rsrp = coverage_data['serving_rsrp']
            else:
                # Fallback to old method if coverage map not available
                mr = ue.generate_measurement_report(self, session.subscriber)
                _, current_rsrp = check_connection_quality(session.subscriber, source_bs)
                target_bs = source_bs.evaluate_handover(current_rsrp, mr)
                if target_bs and target_bs.current_calls < target_bs.capacity:
                    print(f"🔄 [HANDOVER] {session.subscriber.first_name}: {source_bs.id} -> {target_bs.id}")
                    # Log handover event
                    self.handover_events.append({
                        'x': ue.location_x,
                        'y': ue.location_y,
                        'from_bs': source_bs.id,
                        'to_bs': target_bs.id,
                        'subscriber': session.subscriber.first_name,
                        'timestamp': time.time()
                    })
                    ue.handover_history.append({
                        'x': ue.location_x,
                        'y': ue.location_y,
                        'from_bs': source_bs.id,
                        'to_bs': target_bs.id,
                        'timestamp': time.time()
                    })
                    source_bs.current_calls -= 1
                    session.base_station = target_bs
                    target_bs.current_calls += 1
                    _, current_rsrp = check_connection_quality(session.subscriber, target_bs)

            ue.log_state(time.time(), current_rsrp, session.base_station.id)

            is_good_link = current_rsrp > ue.rx_sensitivity
            
            if not is_good_link:
                print(f"❌ [DROPPED] {session.subscriber.first_name} потерял сеть в точке ({ue.location_x:.1f}, {ue.location_y:.1f})")
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

        for signal, bs in towers:
            if bs.current_calls < bs.capacity:
                session = bs.connect_call(subscriber, duration, start_time)
                if session:
                    self.ocs.charge_subscriber(subscriber, estimated_cost)
                    self.active_sessions.append(session)
                    self.total_successful_calls += 1
                    return True
                else:
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

