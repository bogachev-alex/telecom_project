import random 
import time
import math
import datetime
import matplotlib.pyplot as plt

class Subscriber:
    def __init__(self, first_name, last_name, id_number, user_equipment, email, phone, tariff, arrival_rate, avg_duration):
        self.first_name = first_name
        self.last_name = last_name
        self.id_number = id_number
        self.user_equipment = user_equipment
        self.email = email
        self.phone = phone
        self.balance = 0
        self.subscribed = False
        self.bonus_balance = 0
        self.tariff = tariff
        self.arrival_rate = arrival_rate
        self.avg_duration = avg_duration
        self.retrial_timer = 0
        self.pending_duration = 0

    def top_up(self, amount):
        self.balance += amount
        return self.balance

    def withdraw(self, amount):
        self.balance -= amount
        return self.balance

    def subscribe(self):
        self.subscribed = True
        return self.subscribed

    def unsubscribe(self):
        self.subscribed = False
        return self.subscribed

    def get_balance(self):
        return self.balance

    def get_bonus_balance(self):
        return self.bonus_balance
    
    def make_call(self, duration):
        cost_per_min = self.tariff.get_cost_per_minute()
        total_cost = duration*cost_per_min
        if self.balance < total_cost:
            print(f"Недостаточно денег на балансе: нужно {total_cost} руб., на балансе {self.balance} руб.")
            return False
        self.balance -= total_cost
        self.bonus_balance += total_cost * 0.05
        return True

    def act(self, network):
        # 1. Проверка на занятость
        if self.is_busy(network):
            return
        # 2. Логика переповтора (если была неудача ранее)
        if self.retrial_timer > 0:
            self.retrial_timer -= 1
            if self.retrial_timer == 0:
                print(f"--- {self.first_name} делает ПОВТОРНУЮ попытку ---")
                success = network.connect_call(self, self.pending_duration, time.time())
                if not success:
                    self.retrial_timer = random.randint(5, 15) # Снова неудача
            return

        # 3. Логика нового звонка (используем переданные параметры)
        if random.random() < self.arrival_rate:
            duration = max(1, int(random.expovariate(1/self.avg_duration)))
            success = network.connect_call(self, duration, time.time())

            if not success:
                self.pending_duration = duration
                self.retrial_timer = random.randint(5, 15)

    def is_busy(self, network):
        return any(session.subscriber == self for session in network.active_sessions)

class BaseStation:
    def __init__(self, id, capacity, location_x, location_y):
        self.id = id
        self.capacity = capacity
        self.current_calls = 0
        self.tx_power = 43
        self.rx_sensitivity = -120
        self.location_x = location_x
        self.location_y = location_y
    def connect_call(self, subscriber, duration, start_time):
        if self.current_calls < self.capacity:
            if subscriber.make_call(duration):
                self.current_calls += 1
                return CallSession(subscriber, self, duration, start_time)
            return None
            
        else:
            print("Вышка перегружена")
            return False

    def get_current_calls(self):
        return self.current_calls

    def get_capacity(self):
        return self.capacity

    def evaluate_handover(self, current_rsrp, measurement_report):
        """
        Логика принятия решения на стороне БС.
        Применяем Hysteresis (запас), чтобы избежать эффекта пинг-понга.
        """
        hysteresis = 3.0 # дБ
        
        if not measurement_report:
            return None
            
        best_candidate = measurement_report[0] # Самый сильный сигнал в отчете
        
        # Условие: сигнал цели должен быть лучше текущего + запас
        if best_candidate['rsrp'] > (current_rsrp + hysteresis):
            # Проверяем, не является ли лучшая вышка той же самой, к которой мы подключены
            if best_candidate['bs_id'] != self.id:
                return best_candidate['bs_object']
        
        return None

class UserEquipment:
    def __init__(self, ue_id, location_x, location_y):
        self.ue_id = ue_id
        self.location_x = random.randint(0, 1000)
        self.location_y = random.randint(0, 1000)
        self.velocity_x = random.uniform(-1, 1)
        self.velocity_y = random.uniform(-1, 1)
        self.tx_power = 23
        self.rx_sensitivity = -110

        self.history = [] # Список для хранения истории

    def log_state(self, timestamp, rsrp, base_station_id):
        self.history.append({
            'time': timestamp,
            'x': self.location_x,
            'y': self.location_y,
            'rsrp': rsrp,
            'base_station_id': base_station_id
        })

    def get_id(self):
        return self.ue_id
    
    def get_location(self):
        return self.location_x, self.location_y
   
    def move(self):
        # Абонент перемещается
        self.location_x += self.velocity_x
        self.location_y += self.velocity_y
        
        # Отражение от границ "города" (1000x1000), чтобы не ушли в бесконечность
        if self.location_x < 0 or self.location_x > 1000: self.velocity_x *= -1
        if self.location_y < 0 or self.location_y > 1000: self.velocity_y *= -1

    def generate_measurement_report(self, network):
        '''Он возвращает список всех видимых вышек и их RSRP.'''
        report = []
        for bs in network.base_stations.values():
            _, rsrp = network.check_connection_quality(self, bs) # Используем метод из Network для физики
            if rsrp > self.rx_sensitivity:
                report.append({'bs_id': bs.id, 'rsrp': rsrp, 'bs_object': bs})
        
        # Сортируем: самая мощная вышка первая
        report.sort(key=lambda x: x['rsrp'], reverse=True)
        return report



class Tariff:
    def __init__(self, tariff_name, cost_per_minute):
        self.tariff_name = tariff_name
        self.cost_per_minute = cost_per_minute

    def get_tariff_name(self):
        return self.tariff_name

    def get_cost_per_minute(self):
        return self.cost_per_minute

    def set_cost_per_minute(self, cost_per_minute):
        self.cost_per_minute = cost_per_minute

class CallSession:
    def __init__(self, subscriber, base_station, duration, start_time):
        self.subscriber = subscriber
        self.base_station = base_station
        self.remaining_time = duration
        self.duration = duration
        self.start_time = start_time


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
        self.cdr_database = {}
        self.mme = MME(self)
        self.hss = HSS()
        self.ocs = OCS()
        self.base_stations = {}
        self.active_sessions = []
    def tick(self):
        for subscriber in self.subscribers.values():
            subscriber.user_equipment.move()
            
        still_active = []
        for session in self.active_sessions:
            session.remaining_time -= 1
            ue = session.subscriber.user_equipment
            source_bs = session.base_station
            
            # 1. UE измеряет уровень сигнала (Measurement Report)
            mr = ue.generate_measurement_report(self)
            
            # Находим текущий RSRP для отчета
            _, current_rsrp = self.check_connection_quality(session.subscriber, source_bs)
            
            # 2. ТЕКУЩАЯ ВЫШКА анализирует отчет и ищет цель для хендовера
            target_bs = source_bs.evaluate_handover(current_rsrp, mr)
            
            # 3. ИСПОЛНЕНИЕ ХЕНДОВЕРА (через X2-интерфейс / ядро)
            if target_bs and target_bs.current_calls < target_bs.capacity:
                print(f"🔄 [HANDOVER] {session.subscriber.first_name}: {source_bs.id} -> {target_bs.id}")
                source_bs.current_calls -= 1
                session.base_station = target_bs
                target_bs.current_calls += 1
                # Обновляем RSRP после переключения для логов
                _, current_rsrp = self.check_connection_quality(session.subscriber, target_bs)

            # Логируем состояние в историю UE
            ue.log_state(time.time(), current_rsrp, session.base_station.id)

            # Проверка на обрыв (если даже после попытки хендовера сигнал ниже чувствительности)
            is_good_link = current_rsrp > ue.rx_sensitivity
            
            if not is_good_link:
                print(f"❌ [DROPPED] {session.subscriber.first_name} потерял сеть в точке ({ue.location_x:.1f}, {ue.location_y:.1f})")
                self.close_session(session, "DROPPED")
            elif session.remaining_time <= 0:
                self.close_session(session, "COMPLETED")
            else:
                still_active.append(session)

        self.active_sessions = still_active

    def close_session(self, session, reason):
        """Вспомогательный метод для записи в CDR и освобождения линии"""
        cost = session.duration * session.subscriber.tariff.get_cost_per_minute()
        cdr_id = f"{session.subscriber.id_number}_{session.base_station.id}_{int(session.start_time)}"
        
        self.cdr_database[cdr_id] = {
            "subscriber_id": session.subscriber.id_number,
            "base_station_id": session.base_station.id,
            "start_time": time.strftime('%H:%M:%S', time.localtime(session.start_time)),
            "duration": session.duration,
            "cost": cost,
            "reason": reason # Теперь мы знаем, почему звонок завершился
        }
        session.base_station.current_calls -= 1

    def add_base_station(self, base_station):
        self.base_stations[base_station.id] = base_station

    def add_subscriber(self, subscriber):
        self.subscribers[subscriber.id_number] = subscriber
        self.hss.add_subscriber(subscriber.id_number, subscriber)

    def connect_call(self, subscriber, duration, start_time):
        self.total_attempts += 1
        estimated_cost = duration*subscriber.tariff.get_cost_per_minute()
        # 1. Запрос в HSS: Существует ли такой абонент?
        if not self.hss.get_subscriber(subscriber.id_number):
            self.blocked_calls += 1
            return False

        # 3. Запрос в MME: Какая вышка лучше всего "слышит" абонента?
        towers = self.mme.select_best_base_station(subscriber, self.base_stations.values())
        
        if not towers:
            self.blocked_by_capacity += 1
            return False # Вне зоны покрытия

        # 4. Попытка занять радиоканал на выбранной eNodeB
        for signal, bs in towers:
            if bs.current_calls < bs.capacity:
                session = bs.connect_call(subscriber, duration, start_time)
                if session:
                    # Успех: списываем деньги и фиксируем сессию
                    self.ocs.charge_subscriber(subscriber, estimated_cost)
                    self.active_sessions.append(session)
                    return True
                else:
                    self.blocked_by_capacity += 1
        return False

    '''Класс Network: Выступает только как «шина» (Backhaul), которая передает сигнальные сообщения между вышками и обновляет маршруты трафика.'''
    
    def get_distance(self, subscriber, base_station):
        return math.sqrt((subscriber.user_equipment.location_x - base_station.location_x)**2 + (subscriber.user_equipment.location_y - base_station.location_y)**2)

    def check_connection_quality(self, subscriber, base_station):
        dist = self.get_distance(subscriber, base_station)
        if dist < 1: dist = 1
        
        # Расчет Path Loss (Затухание сигнала)
        # L = 40 + 30 * log10(d)
        path_loss = 40 + 30 * math.log10(dist)
        
        # 1. DOWNLINK (Вышка -> Телефон)
        dl_signal = base_station.tx_power - path_loss
        downlink_ok = dl_signal > subscriber.user_equipment.rx_sensitivity
        
        # 2. UPLINK (Телефон -> Вышка)
        ul_signal = subscriber.user_equipment.tx_power - path_loss
        uplink_ok = ul_signal > base_station.rx_sensitivity
        
        # Для отчета возвращаем и результат, и уровень RSRP (сигнал Downlink)
        return (downlink_ok and uplink_ok), dl_signal    
    # def connect_call(self, subscriber, duration):
    #     self.total_attempts += 1
    #     # 0. Проверяем, есть ли абонент в сети
    #     if subscriber.id_number not in self.subscribers:
    #         print("Абонент не найден")
    #         self.blocked_calls += 1
    #         return False
    #     # 1. Проверяем, есть ли вообще свободные вышки в радиусе (в нашем случае - в списке)
    #     any_base_station_available = any(base_station.get_current_calls() < base_station.get_capacity() for base_station in self.base_stations.values())
    #     if not any_base_station_available:
    #         self.blocked_by_capacity += 1
    #         print("Сеть перегружена")
    #         return False
    #     # 2. Пробуем найти свободную вышку
    #     for base_station in self.base_stations.values():
    #         if base_station.get_current_calls() < base_station.get_capacity():
    #             session = base_station.connect_call(subscriber, duration, time.time())
    #             if session:
    #                 self.active_sessions.append(session)
    #                 self.total_successful_calls += 1
    #                 return True
    #             else:
    #                 self.blocked_by_balance += 1
    #                 print("Недостаточно денег на балансе")
    #                 return False
    #     # 3. Если нет свободных вышек, блокируем звонок
    #     self.blocked_calls += 1
    #     return False



        # for base_station in self.base_stations.values():
        #    session = base_station.connect_call(subscriber, duration)
        #    if session:
        #        self.active_sessions.append(session)
        #        self.total_successful_calls += 1
        #        return True
        # self.blocked_calls += 1
        # return False
    
    def get_report(self):
        print("\n" + "="*30)
        print("--- ДЕТАЛЬНЫЙ ОТЧЕТ СЕТИ ---")
        print(f"Всего попыток: {self.total_attempts}")
        print(f"Успешных звонков: {self.total_successful_calls}")
        print("-" * 30)
        print("ПРИЧИНЫ НЕУДАЧ:")
        print(f" - Перегрузка вышек: {self.blocked_by_capacity} ({self.blocked_by_capacity/self.total_attempts:.2%})")
        print(f" - Нехватка средств: {self.blocked_by_balance} ({self.blocked_by_balance/self.total_attempts:.2%})")
        print("-" * 30)
        
        total_blocked = self.blocked_by_capacity + self.blocked_by_balance
        if self.total_attempts > 0:
            gos = total_blocked / self.total_attempts
            print(f"Общий Grade of Service: {gos:.2%}")
        print("="*30)

    def print_cdr_report(self):
        print("\n" + "="*85)
        print(f"{'ID Абонента':<12} | {'Начало':<8} | {'Длит.':<6} | {'Стоимость':<8} | {'Вышка'}")
        print("-" * 85)
        
        if not self.cdr_database:
            print("База CDR пуста.")
        else:
            # ДОБАВЛЯЕМ .values(), чтобы record стал словарем с данными
            for record in self.cdr_database.values():
                print(f"{record['subscriber_id']:<12} | "
                    f"{record['start_time']:<8} | "
                    f"{record['duration']:<6} | "
                    f"{record['cost']:<8.2f} | "
                    f"{record['base_station_id']}") # Убедись, что ключ совпадает с тем, что в tick
        print("="*85)

    def audit_network_revenue(self):
        total_cdr_sum = sum(record['cost'] for record in self.cdr_database.values())
        print(f"\n[АУДИТ] Общая выручка по CDR: {total_cdr_sum:.2f} руб.")
        print(f"[АУДИТ] Количество записей: {len(self.cdr_database)}")

    def get_calls_by_phone(self, phone_number):
        calls = [r for r in self.cdr_database.values() if r['subscriber_id'] == phone_number]
        
        print(f"\nНайдено звонков для номера {phone_number}: {len(calls)}")
        for c in calls:
            print(f"  - Старт: {c['start_time']} сек, Длительность: {c['duration']} сек, Списано: {c['cost']} руб.")
        return calls

    def print_subscriber_trace(self, subscriber_id):
        sub = self.subscribers.get(subscriber_id)
        if not sub or not sub.user_equipment.history:
            print(f"История для {subscriber_id} не найдена.")
            return

        print(f"\n--- ТРАССИРОВКА ПЕРЕМЕЩЕНИЙ И СИГНАЛА ДЛЯ {sub.first_name} ---")
        print(f"{'Время':<12} | {'X':<6} | {'Y':<6} | {'RSRP':<8} | {'Качество':<10} | {'БС'}")
        print("-" * 70)

        for entry in sub.user_equipment.history:
            # Превращаем Unix-секунды в нормальное время (ЧЧ:ММ:СС)
            readable_time = datetime.datetime.fromtimestamp(entry['time']).strftime('%H:%M:%S')
            
            # Оценка качества сигнала
            val = entry['rsrp']
            if val > -80: q = "Excellent"
            elif val > -90: q = "Good"
            elif val > -100: q = "Fair"
            else: q = "Poor"

            print(f"{readable_time:<12} | "
                f"{entry['x']:<6.1f} | "
                f"{entry['y']:<6.1f} | "
                f"{entry['rsrp']:<8.1f} | "
                f"{q:<10} | "
                f"{entry['base_station_id']}")
    
    def plot_subscriber_movement(self, subscriber_id):
        sub = self.subscribers.get(subscriber_id)
        history = sub.user_equipment.history
        
        x_coords = [e['x'] for e in history]
        y_coords = [e['y'] for e in history]
        rsrp_vals = [e['rsrp'] for e in history]

        plt.figure(figsize=(10, 8))
        
        # Рисуем путь абонента (цвет зависит от силы сигнала)
        path = plt.scatter(x_coords, y_coords, c=rsrp_vals, cmap='RdYlGn', label='Путь абонента')
        plt.colorbar(path, label='RSRP (dBm)')

        # Рисуем вышки
        for bs_id, bs in self.base_stations.items():
            plt.plot(bs.location_x, bs.location_y, 'r^', markersize=12)
            plt.text(bs.location_x + 5, bs.location_y + 5, bs_id, color='red', fontweight='bold')

        plt.title(f"Карта перемещений и уровня сигнала: {sub.first_name}")
        plt.xlabel("X (метры)")
        plt.ylabel("Y (метры)")
        plt.grid(True)
        plt.xlim(0, 1000)
        plt.ylim(0, 1000)
        plt.show()

class HSS:
    def __init__(self):
        self.subscribers = {}
    
    def add_subscriber(self, id_number, subscriber):
        self.subscribers[id_number] = subscriber
        
    def get_subscriber(self, id_number):
        return self.subscribers[id_number]

class OCS:
    def __init__(self):
        self.cdr_database = {}

    def check_balance(self, subscriber, estimated_cost):
        return subscriber.get_balance() >= estimated_cost

    def charge_subscriber(self, subscriber, amount):
        subscriber.withdraw(amount)
        return subscriber.get_balance()

class MME:
    def __init__(self, network):
        self.network = network

    def select_best_base_station(self, user_equipment, base_stations):
        """
        Имитирует выбор лучшей соты на основе Measurement Reports от телефона.
        Возвращает список кортежей (сигнал, объект_БС), отсортированный по силе сигнала.
        """
        candidates = [] # Используем список для возможности сортировки
        
        for bs in self.network.base_stations.values():
            # Вызываем физическую проверку из Network (Link Budget)
            is_good_link, rsrp = self.network.check_connection_quality(user_equipment, bs)
            
            if is_good_link:
                # Сохраняем и сигнал, и сам объект вышки
                candidates.append((rsrp, bs))
        
        # Сортируем список кортежей по первому элементу (rsrp)
        # reverse=True, так как -70 дБм > -90 дБм
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        return candidates


if __name__ == "__main__":
    tariff_1 = Tariff("Basic", 1)
    core_network = Network()
    bs1 = BaseStation("BS-01", 1, 500, 500)
    bs2 = BaseStation("BS-02", 1, 100, 100)
    core_network.add_base_station(bs1)
    core_network.add_base_station(bs2)
    sub_ivan = Subscriber("Иван", "Иванов", "1234567890", UserEquipment("UE-01", 400, 500), "ivan@example.com", "1234567890", tariff_1, 0.002, 5)
    sub_maria = Subscriber("Мария", "Петрова", "1234567891", UserEquipment("UE-02", 700, 500), "maria@example.com", "1234567891", tariff_1, 0.001, 10)
    sub_ivan.top_up(100)
    sub_maria.top_up(100)
    core_network.add_subscriber(sub_ivan)
    core_network.add_subscriber(sub_maria)
    core_network.connect_call(sub_ivan, 5, time.time())
    for second in range(1, 3600):
        sub_ivan.act(core_network)
        sub_maria.act(core_network)
        core_network.tick()
        print(f"Время: {second} секунда")
    core_network.get_report()
    core_network.print_cdr_report()
    core_network.audit_network_revenue()
    core_network.get_calls_by_phone(sub_ivan.phone)
    core_network.get_calls_by_phone(sub_maria.phone)
    core_network.print_subscriber_trace("1234567890") # ID Ивана
    core_network.plot_subscriber_movement("1234567890") # ID Ивана