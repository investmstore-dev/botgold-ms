"""
Modulo de notificaciones Telegram — BOT Mining Store GOLD
=========================================================
Envia a un chat/grupo de Telegram:
  - Apertura de trades (entrada, SL, lote)
  - Cierre de trades (PnL en $ y %, razon del cierre)
  - Alertas FTMO (drawdown violado, objetivo alcanzado)

Configuracion en config/.env:
  TELEGRAM_BOT_TOKEN=123456:ABC-DEF...   (de @BotFather)
  TELEGRAM_CHAT_ID=-100123456789         (id del chat o grupo)

Si no estan configurados, las funciones son no-op (el bot sigue normal).

Para obtener el chat_id: envia un mensaje al bot y corre
  python -m utils.notifier --get-chat-id
Para probar: python -m utils.notifier --test
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

# config carga el .env al importarse
import config  # noqa: F401

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
API_URL   = f"https://api.telegram.org/bot{BOT_TOKEN}"

ENABLED = bool(BOT_TOKEN and CHAT_ID)


def send(text: str) -> bool:
    """Envia un mensaje al chat configurado. HTML basico soportado."""
    if not ENABLED:
        return False
    try:
        r = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id":    CHAT_ID,
            "text":       text,
            "parse_mode": "HTML",
        }, timeout=10)
        ok = r.json().get("ok", False)
        if not ok:
            logger.warning("Telegram error: %s", r.text)
        return ok
    except Exception as e:
        logger.warning("Telegram send error: %s", e)
        return False


# -- Notificaciones de trades --------------------------------------------------

def notify_trade_open(trade: dict):
    """trade: dict con type, open_price, sl, lot."""
    emoji = "🟢" if trade["type"] == "long" else "🔴"
    send(
        f"{emoji} <b>TRADE ABIERTO — {trade['type'].upper()}</b> 🥇\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🤖 BOT GOLD — XAU/USD H4\n"
        f"💵 Entrada: <b>${trade.get('open_price', 0):,.2f}</b>\n"
        f"🛑 Stop Loss: ${trade.get('sl', 0):,.2f}\n"
        f"📦 Lote: {trade.get('lot', 0):.2f}\n"
        f"📊 Estrategia D: BB Breakout + SMA50 (trailing 1xATR)"
    )


def notify_trade_close(trade: dict, exit_price: float, pnl: float,
                       balance: float, reason: str):
    """Notifica cierre con PnL en $ y % sobre el balance."""
    pnl_pct = pnl / balance * 100 if balance else 0.0
    emoji   = "✅" if pnl >= 0 else "❌"
    word    = "GANANCIA" if pnl >= 0 else "PERDIDA"
    send(
        f"{emoji} <b>TRADE CERRADO — {word}</b> 🥇\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🤖 BOT GOLD — XAU/USD H4\n"
        f"📈 Tipo: {trade.get('type', '?').upper()}\n"
        f"💵 Entrada: ${trade.get('open_price', 0):,.2f}\n"
        f"🚪 Salida: ${exit_price:,.2f}\n"
        f"💰 Resultado: <b>${pnl:+,.2f} ({pnl_pct:+.2f}%)</b>\n"
        f"📝 Razon: {reason}"
    )


# -- Alertas FTMO ----------------------------------------------------------------

def notify_dd_violated(ftmo: dict):
    send(
        "🚨 <b>ALERTA: DRAWDOWN MAXIMO VIOLADO</b> 🥇\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🤖 BOT GOLD — Bot detenido\n"
        f"🔻 DD: {ftmo.get('max_dd_pct', 0):.2f}% "
        f"(limite -{ftmo.get('dd_limit_pct', 10):.0f}%)\n"
        f"💼 Balance: ${ftmo.get('current_balance', 0):,.2f}"
    )


def notify_daily_dd(ftmo: dict):
    send(
        "⚠️ <b>DRAWDOWN DIARIO ALCANZADO</b> 🥇\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🤖 BOT GOLD — Sin nuevas entradas hoy\n"
        f"🔻 DD diario: {ftmo.get('daily_dd_pct', 0):.2f}% "
        f"(limite -{ftmo.get('daily_dd_limit_pct', 5):.0f}%)"
    )


def notify_target_reached(ftmo: dict):
    send(
        "🏆 <b>OBJETIVO FTMO ALCANZADO!</b> 🥇\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🤖 BOT GOLD — XAU/USD\n"
        f"📈 Profit: <b>{ftmo.get('profit_pct', 0):+.2f}%</b> "
        f"(objetivo +{ftmo.get('target_pct', 10):.0f}%)\n"
        f"💼 Balance: ${ftmo.get('current_balance', 0):,.2f}\n"
        "🎉 Revisa el Client Area de FTMO para pasar de fase"
    )


# -- Utilidades CLI --------------------------------------------------------------

def get_chat_id():
    """Muestra los chat_id de los ultimos mensajes recibidos por el bot."""
    if not BOT_TOKEN:
        print("Falta TELEGRAM_BOT_TOKEN en config/.env")
        return
    r = requests.get(f"{API_URL}/getUpdates", timeout=10).json()
    updates = r.get("result", [])
    if not updates:
        print("Sin mensajes. Envia un mensaje al bot (o al grupo) y vuelve a correr esto.")
        return
    seen = set()
    for u in updates:
        msg = u.get("message") or u.get("channel_post") or {}
        chat = msg.get("chat", {})
        cid = chat.get("id")
        if cid and cid not in seen:
            seen.add(cid)
            print(f"chat_id: {cid}  ({chat.get('type')}: "
                  f"{chat.get('title') or chat.get('username') or chat.get('first_name')})")


if __name__ == "__main__":
    import sys
    if "--get-chat-id" in sys.argv:
        get_chat_id()
    elif "--test" in sys.argv:
        if not ENABLED:
            print("Falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en config/.env")
        else:
            ok = send("🤖 <b>Test BOT GOLD</b> 🥇 — notificaciones funcionando correctamente ✅")
            print("Mensaje enviado" if ok else "ERROR al enviar")
    else:
        print(__doc__)
