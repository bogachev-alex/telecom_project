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

    def tick(self):
        """Process one time tick: move UEs, handle sessions, handovers."""
        for subscriber in self.subscribers.values():
            subscriber.user_equipment.move()
            
        still_active = []
        for session in self.active_sessions:
            session.remaining_time -= 1
            ue = session.subscriber.user_equipment
            source_bs = session.base_station
            
            mr = ue.generate_measurement_report(self, session.subscriber)
            _, current_rsrp = check_connection_quality(session.subscriber, source_bs)
            
            target_bs = source_bs.evaluate_handover(current_rsrp, mr)
            
            if target_bs and target_bs.current_calls < target_bs.capacity:
                print(f"🔄 [HANDOVER] {session.subscriber.first_name}: {source_bs.id} -> {target_bs.id}")
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

