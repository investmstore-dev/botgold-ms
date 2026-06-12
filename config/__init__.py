# BOT Mining Store GOLD -- Configuracion
# Estrategia D: BB Breakout + SMA50 | XAU/USD H4
# Cuenta: FTMO Challenge $10k 2-Step

# Credenciales fuera del codigo: se leen de variables de entorno / .env
# El login real lo maneja el terminal MT5 (el bot se comunica via EA Bridge).
import os

def _load_dotenv():
    path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

_load_dotenv()

MT5_LOGIN    = int(os.environ.get("MT5_LOGIN", "0"))
MT5_PASSWORD = os.environ.get("MT5_PASSWORD", "")
MT5_SERVER   = os.environ.get("MT5_SERVER", "")

SYMBOL     = "XAUUSD"
TIMEFRAME  = "H4"
RISK_PCT   = 0.02      # 2% del capital por operacion

# Indicadores
BB_PERIOD  = 20
BB_DEVS    = 2.0
SMA_PERIOD = 50
EMA_PERIOD = 21        # base del trailing stop
ADX_PERIOD = 14
RSI_PERIOD = 14
ATR_PERIOD = 14

# Filtros de entrada -- Estrategia D (BB Breakout + SMA50)
ADX_MIN        = 18
RSI_LONG_MIN   = 38
RSI_LONG_MAX   = 80
RSI_SHORT_MIN  = 20
RSI_SHORT_MAX  = 62

# Gestion de posicion
ATR_SL_MULT    = 2.0   # Stop loss = 2x ATR
ATR_TRAIL_MULT = 1.0   # Trailing stop = 1x ATR desde EMA21
MAX_POSITIONS  = 1

# Archivos de estado para el dashboard
DATA_DIR       = "data"
STATE_FILE     = "data/state.json"
TRADES_FILE    = "data/trades.json"
EQUITY_FILE    = "data/equity.json"

# Objetivo FTMO
FTMO_TARGET_PCT   = 0.10   # +10% objetivo fase 1
FTMO_MAX_DD_PCT   = 0.10   # -10% drawdown maximo
FTMO_DAILY_DD_PCT = 0.05   # -5% perdida diaria maxima
