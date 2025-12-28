"""
Base Station constants.
"""
TX_POWER = 30  # Reduced from 43 dBm (20W) to 30 dBm (1W) for dense network
RX_SENSITIVITY = -120
HANDOVER_HYSTERESIS = 3.0
DEFAULT_CAPACITY = 200  # Increased to reduce blocking

# GSM (2G) физика
GSM_TRX_BW_MHZ = 0.2     # Полоса одного TRX
SLOTS_PER_TRX = 8         # 8 слотов в TDMA-фрейме
SIG_SLOTS_PER_CELL = 2    # Служебные слоты (BCCH, SDCCH)