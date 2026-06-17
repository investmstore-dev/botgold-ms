"""
BOT Mining Store GOLD — Motor principal
Estrategia D: BB Breakout + SMA50 | XAU/USD H4
"""
import os
import time
import logging
from datetime import datetime, timezone

from utils import mt5_connector as mt5c
from model import strategy as strat
from utils import state_manager as sm
from utils import notifier
from config import SYMBOL, TIMEFRAME, RISK_PCT, MAX_POSITIONS, ATR_SL_MULT, DATA_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("data/bot.log"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

INITIAL_BALANCE = None   # Se fija al conectar

# Estado para notificaciones (evita duplicados y detecta cierres)
_last_pos        = None    # snapshot de la ultima posicion abierta vista
_alerted_dd      = False
_alerted_daily   = None    # fecha del ultimo aviso de DD diario
_alerted_target  = False

# Reporte diario (20:00 UTC, una vez al dia, persistido para sobrevivir reinicios)
REPORT_HOUR_UTC  = 20
_REPORT_MARKER   = os.path.join(DATA_DIR, "last_report.txt")
_last_report_date = None
_trades_today     = []     # trades cerrados hoy (para el reporte)


def _maybe_daily_report(account: dict, ftmo: dict):
    """Envia el reporte diario una vez al dia despues de las 20:00 UTC.
    La fecha se persiste en disco para no duplicar tras reinicios."""
    global _last_report_date, _trades_today
    now = datetime.now(timezone.utc)
    if now.hour < REPORT_HOUR_UTC:
        return
    if _last_report_date is None and os.path.exists(_REPORT_MARKER):
        with open(_REPORT_MARKER) as f:
            _last_report_date = f.read().strip()
    if _last_report_date == str(now.date()):
        return
    _last_report_date = str(now.date())
    with open(_REPORT_MARKER, "w") as f:
        f.write(_last_report_date)
    notifier.notify_daily_report(account, ftmo, _trades_today)
    logger.info("Reporte diario enviado (%d trades hoy)", len(_trades_today))
    _trades_today = []


def run_cycle():
    global INITIAL_BALANCE, _last_pos, _alerted_dd, _alerted_daily, _alerted_target, _trades_today

    # --- Datos de cuenta ---
    account = mt5c.get_account()
    if not account:
        logger.warning("No se pudo obtener cuenta MT5")
        return

    if INITIAL_BALANCE is None:
        INITIAL_BALANCE = account["balance"]
        logger.info("Balance inicial fijado: %.2f", INITIAL_BALANCE)

    sm.append_equity(account["equity"], account["balance"])
    ftmo = sm.calc_ftmo_status(account, INITIAL_BALANCE)

    # Reporte diario (se evalua antes de las guardias para enviarse siempre)
    _maybe_daily_report(account, ftmo)

    # --- Guardia FTMO ---
    if ftmo["dd_violated"]:
        logger.error("DRAWDOWN MAXIMO VIOLADO — Bot detenido")
        if not _alerted_dd:
            notifier.notify_dd_violated(ftmo)
            _alerted_dd = True
        sm.save_state(account, "HALTED_DD", None, ftmo)
        return
    if ftmo["daily_dd_violated"]:
        logger.warning("Drawdown diario alcanzado — sin nuevas entradas hoy")
        today = datetime.now().date()
        if _alerted_daily != today:
            notifier.notify_daily_dd(ftmo)
            _alerted_daily = today
        sm.save_state(account, "HALTED_DAILY", None, ftmo)
        return
    if ftmo["target_reached"]:
        logger.info("OBJETIVO FTMO ALCANZADO — +%.2f%%", ftmo["profit_pct"])
        if not _alerted_target:
            notifier.notify_target_reached(ftmo)
            _alerted_target = True
        sm.save_state(account, "TARGET_REACHED", None, ftmo)
        return

    # --- Velas e indicadores ---
    df = mt5c.get_candles(SYMBOL, TIMEFRAME, count=200)
    if df.empty:
        logger.warning("Sin datos de velas")
        return
    df = strat.compute_indicators(df)

    curr = df.iloc[-1]
    atr    = curr["atr"]
    ema21  = curr["ema21"]
    close  = curr["close"]

    # --- Gestionar posicion abierta (trailing stop) ---
    positions = mt5c.get_open_positions(SYMBOL)
    active_trade = None

    # Detectar cierre: habia posicion y ya no esta (SL / trailing ejecutado)
    if _last_pos and not positions:
        pnl = _last_pos.get("profit", 0)
        exit_px = _last_pos.get("current_sl", 0)
        notifier.notify_trade_close(
            _last_pos, exit_px, pnl,
            account["balance"], "Stop Loss / Trailing Stop"
        )
        _trades_today.append({
            "type":  _last_pos.get("type", "?"),
            "entry": _last_pos.get("open_price", 0),
            "exit":  exit_px,
            "pnl":   pnl,
        })
        logger.info("Posicion cerrada detectada | PnL aprox: %.2f", pnl)
        _last_pos = None

    if positions:
        pos = positions[0]   # dict del EA: ticket, type ("long"/"short"), sl, ...
        ptype  = pos.get("type", "long")
        cur_sl = pos.get("sl", 0)
        new_sl = strat.calc_trailing_sl(ptype, ema21, atr)
        # Solo mover SL a favor nunca en contra
        if ptype == "long" and new_sl > cur_sl:
            mt5c.modify_sl(pos.get("ticket"), new_sl)
        elif ptype == "short" and (cur_sl == 0 or new_sl < cur_sl):
            mt5c.modify_sl(pos.get("ticket"), new_sl)

        active_trade = {
            "ticket":     pos.get("ticket"),
            "type":       ptype,
            "open_price": pos.get("open_price", 0),
            "current_sl": cur_sl,
            "profit":     pos.get("profit", 0),
            "volume":     pos.get("volume", 0),
        }
        _last_pos = active_trade
        sm.save_state(account, "holding", active_trade, ftmo)
        return

    # --- Buscar nueva entrada ---
    if len(positions) >= MAX_POSITIONS:
        sm.save_state(account, "max_positions", active_trade, ftmo)
        return

    signal = strat.check_entry(df)
    if signal is None:
        sm.save_state(account, "no_signal", None, ftmo)
        return

    # Calcular SL y lote
    if signal == "long":
        sl = close - ATR_SL_MULT * atr
    else:
        sl = close + ATR_SL_MULT * atr

    lot = strat.calc_lot_size(account["balance"], atr, close, RISK_PCT)
    logger.info("Señal: %s | close=%.2f | sl=%.2f | atr=%.2f | lot=%.2f",
                signal, close, sl, atr, lot)

    result = mt5c.open_order(SYMBOL, signal, lot, sl)
    if "error" not in result:
        trade_record = {
            "ticket":     result.get("ticket"),
            "type":       signal,
            "open_price": close,   # precio de referencia (cierre de vela)
            "lot":        lot,
            "sl":         sl,
            "atr":        atr,
        }
        sm.append_trade(trade_record)
        notifier.notify_trade_open(trade_record)
        active_trade = trade_record

    sm.save_state(account, signal, active_trade, ftmo)


def main():
    logger.info("=== BOT Mining Store GOLD iniciando ===")

    if not mt5c.connect():
        logger.error("No se pudo conectar a MT5. Verifica que MT5 este abierto.")
        return

    import os
    os.makedirs("data", exist_ok=True)

    try:
        while True:
            now = datetime.now()
            logger.info("--- Ciclo %s ---", now.strftime("%Y-%m-%d %H:%M:%S"))
            try:
                run_cycle()
            except Exception as e:
                logger.exception("Error en ciclo: %s", e)

            # Esperar 60 segundos entre ciclos (H4 = nueva vela cada 4h,
            # pero chequeamos cada minuto para trailing stop y guardia FTMO)
            time.sleep(60)

    except KeyboardInterrupt:
        logger.info("Bot detenido por usuario")
    finally:
        mt5c.disconnect()
        logger.info("Desconectado de MT5")


if __name__ == "__main__":
    main()
