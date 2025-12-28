"""
Resource Management module for different Radio Access Technologies.
"""
from abc import ABC, abstractmethod
from .constants import SLOTS_PER_TRX, SIG_SLOTS_PER_CELL

class BaseResourceManager(ABC):
    """Абстрактный интерфейс менеджера ресурсов."""
    @abstractmethod
    def allocate(self, subscriber_id, demand=1):
        pass

    @abstractmethod
    def release(self, resource_id):
        pass

    @abstractmethod
    def get_utilization(self):
        pass

class GsmResourceManager(BaseResourceManager):
    """Менеджер ресурсов для 2G (TDMA слоты)."""
    def __init__(self, num_trx):
        self.total_slots = (num_trx * SLOTS_PER_TRX) - SIG_SLOTS_PER_CELL
        self.slots = [None] * self.total_slots  # Массив слотов

    def allocate(self, subscriber_id, demand=1):
        """Ищет первый свободный слот и занимает его."""
        for i, occupant in enumerate(self.slots):
            if occupant is None:
                self.slots[i] = subscriber_id
                return i  # Возвращаем slot_id
        return None

    def release(self, slot_id):
        """Освобождает слот по индексу."""
        if 0 <= slot_id < self.total_slots:
            self.slots[slot_id] = None

    def get_utilization(self):
        used = sum(1 for s in self.slots if s is not None)
        return used / self.total_slots if self.total_slots > 0 else 1.0

class NrResourceManager(BaseResourceManager):
    """Менеджер ресурсов для 5G (Полоса пропускания / PRB)."""
    def __init__(self, bandwidth_mhz):
        # Упрощенно: считаем емкость в условных единицах ресурсов (PRB)
        self.total_resources = bandwidth_mhz * 10  # Примерная сетка
        self.used_resources = 0
        self.allocations = {} # resource_id -> amount

    def allocate(self, subscriber_id, demand=10):
        """Выделяет часть спектра (demand в условных единицах)."""
        if self.used_resources + demand <= self.total_resources:
            res_id = f"res_{subscriber_id}_{self.used_resources}"
            self.allocations[res_id] = demand
            self.used_resources += demand
            return res_id
        return None

    def release(self, res_id):
        if res_id in self.allocations:
            self.used_resources -= self.allocations.pop(res_id)

    def get_utilization(self):
        return self.used_resources / self.total_resources