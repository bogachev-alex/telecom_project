"""
CDR (Call Detail Record) management module.
"""
import time


class CDRManager:
    def __init__(self):
        self.cdr_database = {}

    def close_session(self, session, reason):
        """Record CDR entry and free base station capacity."""
        cost = session.duration * session.subscriber.tariff.get_cost_per_minute()
        cdr_id = f"{session.subscriber.id_number}_{session.base_station.id}_{int(session.start_time)}"
        
        self.cdr_database[cdr_id] = {
            "subscriber_id": session.subscriber.id_number,
            "base_station_id": session.base_station.id,
            "start_time": time.strftime('%H:%M:%S', time.localtime(session.start_time)),
            "duration": session.duration,
            "cost": cost,
            "reason": reason
        }
        session.base_station.current_calls -= 1

    def print_cdr_report(self):
        """Print formatted CDR report."""
        print("\n" + "="*85)
        print(f"{'ID Абонента':<12} | {'Начало':<8} | {'Длит.':<6} | {'Стоимость':<8} | {'Вышка'}")
        print("-" * 85)
        
        if not self.cdr_database:
            print("База CDR пуста.")
        else:
            for record in self.cdr_database.values():
                print(f"{record['subscriber_id']:<12} | "
                    f"{record['start_time']:<8} | "
                    f"{record['duration']:<6} | "
                    f"{record['cost']:<8.2f} | "
                    f"{record['base_station_id']}")
        print("="*85)

    def audit_network_revenue(self):
        """Audit total revenue from CDR records."""
        total_cdr_sum = sum(record['cost'] for record in self.cdr_database.values())
        print(f"\n[АУДИТ] Общая выручка по CDR: {total_cdr_sum:.2f} руб.")
        print(f"[АУДИТ] Количество записей: {len(self.cdr_database)}")

    def get_calls_by_phone(self, phone_number):
        """Get all calls for a specific phone number."""
        calls = [r for r in self.cdr_database.values() if r['subscriber_id'] == phone_number]
        
        print(f"\nНайдено звонков для номера {phone_number}: {len(calls)}")
        for c in calls:
            print(f"  - Старт: {c['start_time']} сек, Длительность: {c['duration']} сек, Списано: {c['cost']} руб.")
        return calls

