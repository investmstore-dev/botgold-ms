"""
Backtest multi-instrumento -- Estrategia D (BB Breakout + SMA50) en H4
Prueba la misma estrategia del oro en otros pares (plata, petroleo, etc.)

Datos: yfinance 1h en chunks (max ~730 dias) -> resample H4
NOTA: datos exploratorios (futuros yfinance). Para validacion final usar
datos reales del broker FTMO via ExportH4Data.mq5.
"""
import sys
import pandas as pd
import numpy as np
import warnings
from datetime import datetime, timedelta
warnings.filterwarnings("ignore")

# --- Parametros Estrategia D (identicos al oro) ---
INITIAL_CAPITAL = 10_000
RISK_PCT        = 0.02
BB_PERIOD=20; BB_DEVS=2.0; SMA_PERIOD=50; EMA_PERIOD=21
ADX_PERIOD=14; RSI_PERIOD=14; ATR_PERIOD=14; ADX_MIN=18
RSI_LONG_MIN=38;  RSI_LONG_MAX=80
RSI_SHORT_MIN=20; RSI_SHORT_MAX=62
ATR_SL_MULT=2.0;  ATR_TRAIL_MULT=1.0
FTMO_MAX_DD=0.10; FTMO_DAILY_DD=0.05

import os
COMMON = os.path.join(os.environ["APPDATA"], "MetaQuotes", "Terminal", "Common", "Files")

# --- Catalogo: ticker yfinance + multiplicador contrato + csv real del broker ---
INSTRUMENTS = {
    "gold":   {"ticker": "GC=F", "mult": 100,  "name": "ORO (XAUUSD)",     "csv": "xauusd_h4_data.csv"},
    "silver": {"ticker": "SI=F", "mult": 5000, "name": "PLATA (XAGUSD)",   "csv": "xagusd_h4_data.csv"},
    "oil":    {"ticker": "CL=F", "mult": 1000, "name": "PETROLEO (USOIL)", "csv": "usoil_h4_data.csv"},
}


def load_real_csv(csv_name: str) -> pd.DataFrame:
    """Lee el CSV H4 exportado por el EA/script desde Common/Files (UTF-16)."""
    path = os.path.join(COMMON, csv_name)
    if not os.path.exists(path):
        return pd.DataFrame()
    for enc in ("utf-16", "utf-8"):
        try:
            df = pd.read_csv(path, parse_dates=["datetime"], encoding=enc)
            break
        except Exception:
            df = pd.DataFrame()
    if df.empty:
        return df
    df.columns = [c.lower().strip() for c in df.columns]
    df = df.set_index("datetime").sort_index()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df[["open", "high", "low", "close", "volume"]].dropna()


def download_h4(ticker: str) -> pd.DataFrame:
    """Baja la maxima historia 1h posible (chunks de 720 dias) y resamplea a H4."""
    import yfinance as yf
    frames = []
    end = datetime.now()
    for _ in range(2):  # ~2 chunks => hasta ~1.5 anios
        start = end - timedelta(days=720)
        df = yf.Ticker(ticker).history(start=start.date(), end=end.date(), interval="1h")
        if not df.empty:
            frames.append(df)
        end = start
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames)
    df = df[~df.index.duplicated(keep="first")].sort_index()
    df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]]
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df.resample("4h").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum"
    }).dropna()
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c, h, l = df["close"], df["high"], df["low"]
    bm = c.rolling(BB_PERIOD).mean(); bs = c.rolling(BB_PERIOD).std()
    df["bb_upper"] = bm + BB_DEVS*bs
    df["bb_lower"] = bm - BB_DEVS*bs
    df["bb_width"] = df["bb_upper"] - df["bb_lower"]
    df["bb_squeeze"] = df["bb_width"] < df["bb_width"].rolling(BB_PERIOD).mean()
    df["sma50"] = c.rolling(SMA_PERIOD).mean()
    df["sma50_slope"] = df["sma50"].diff(3)
    df["ema21"] = c.ewm(span=EMA_PERIOD, adjust=False).mean()
    tr = pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(ATR_PERIOD).mean()
    d = c.diff(); g = d.clip(lower=0).rolling(RSI_PERIOD).mean()
    ls = (-d.clip(upper=0)).rolling(RSI_PERIOD).mean()
    df["rsi"] = 100 - (100/(1 + g/ls.replace(0, np.nan)))
    up = h.diff(); dn = -l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    mdm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    atr14 = tr.rolling(ADX_PERIOD).mean()
    pdi = 100*pdm.rolling(ADX_PERIOD).mean()/atr14
    mdi = 100*mdm.rolling(ADX_PERIOD).mean()/atr14
    dx = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)
    df["adx"] = dx.rolling(ADX_PERIOD).mean()
    return df.dropna()


def run_backtest(df: pd.DataFrame, mult: int):
    capital = INITIAL_CAPITAL; peak = capital
    trades = []; pos = None; daily_start = {}
    for i in range(1, len(df)):
        row = df.iloc[i]; prev = df.iloc[i-1]; dt = df.index[i].date()
        daily_start.setdefault(dt, capital)
        if pos:
            trail = (row["ema21"]-ATR_TRAIL_MULT*row["atr"] if pos["type"] == "long"
                     else row["ema21"]+ATR_TRAIL_MULT*row["atr"])
            if pos["type"] == "long" and trail > pos["sl"]: pos["sl"] = trail
            elif pos["type"] == "short" and trail < pos["sl"]: pos["sl"] = trail
            hit = ((pos["type"] == "long" and row["low"] <= pos["sl"]) or
                   (pos["type"] == "short" and row["high"] >= pos["sl"]))
            if hit:
                m = 1 if pos["type"] == "long" else -1
                pnl = (pos["sl"]-pos["entry"])*m*pos["lot"]*mult
                capital += pnl; peak = max(peak, capital)
                trades.append({"entry_date": pos["entry_date"], "exit_date": df.index[i],
                    "type": pos["type"], "pnl_usd": round(pnl, 2), "capital": round(capital, 2)})
                pos = None
            continue
        if (capital-peak)/INITIAL_CAPITAL <= -FTMO_MAX_DD: continue
        if (capital-daily_start[dt])/INITIAL_CAPITAL <= -FTMO_DAILY_DD: continue
        sq = prev["bb_squeeze"]; ok = row["adx"] >= ADX_MIN
        if (sq and row["close"] > row["bb_upper"] and row["sma50_slope"] > 0
                and row["close"] > row["sma50"] and ok
                and RSI_LONG_MIN <= row["rsi"] <= RSI_LONG_MAX):
            sl_d = ATR_SL_MULT*row["atr"]
            lot = max(0.01, round((capital*RISK_PCT)/(sl_d*mult), 2))
            pos = {"type": "long", "entry": row["close"], "sl": row["close"]-sl_d,
                   "lot": lot, "entry_date": df.index[i]}
        elif (sq and row["close"] < row["bb_lower"] and row["sma50_slope"] < 0
                and row["close"] < row["sma50"] and ok
                and RSI_SHORT_MIN <= row["rsi"] <= RSI_SHORT_MAX):
            sl_d = ATR_SL_MULT*row["atr"]
            lot = max(0.01, round((capital*RISK_PCT)/(sl_d*mult), 2))
            pos = {"type": "short", "entry": row["close"], "sl": row["close"]+sl_d,
                   "lot": lot, "entry_date": df.index[i]}
    return trades


def report(key: str):
    inst = INSTRUMENTS[key]
    real = load_real_csv(inst["csv"])
    if not real.empty:
        src = "DATOS REALES BROKER ({})".format(inst["csv"])
        df = real
    else:
        print("Descargando {} ({}) de yfinance...".format(inst["name"], inst["ticker"]))
        df = download_h4(inst["ticker"])
        src = "yfinance EXPLORATORIO (futuros, no spot del broker)"
    if df.empty:
        print("  Sin datos para {}\n".format(inst["name"])); return
    df = add_indicators(df)
    trades = run_backtest(df, inst["mult"])
    W = 60; print("="*W)
    print("  {}  |  Estrategia D  |  H4  |  riesgo 2%".format(inst["name"]))
    print("  Fuente: {}".format(src))
    print("  Periodo: {} a {}  ({} velas H4)".format(
        df.index[0].date(), df.index[-1].date(), len(df)))
    print("="*W)
    if not trades:
        print("  Sin trades en el periodo.\n"); return
    dft = pd.DataFrame(trades)
    wins = dft[dft["pnl_usd"] > 0]; loss = dft[dft["pnl_usd"] <= 0]
    n = len(dft); wr = len(wins)/n*100
    pf = wins["pnl_usd"].sum()/abs(loss["pnl_usd"].sum()) if len(loss) else 999
    fin = dft["capital"].iloc[-1]; ret = (fin-INITIAL_CAPITAL)/INITIAL_CAPITAL*100
    eq = [INITIAL_CAPITAL]+dft["capital"].tolist(); pk = eq[0]; dd = 0.0
    for v in eq: pk = max(pk, v); dd = min(dd, (v-pk)/pk*100)
    months = max(1, (dft["exit_date"].iloc[-1]-dft["exit_date"].iloc[0]).days/30)
    print("  {:<22} {:>12}".format("Trades totales", n))
    print("  {:<22} {:>12}".format("Ganadores", "{} ({:.1f}%)".format(len(wins), wr)))
    print("  {:<22} {:>12}".format("Profit Factor", "{:.2f}".format(pf)))
    print("  {:<22} {:>12}".format("Trades / mes", "{:.1f}".format(n/months)))
    print("  {:<22} {:>12}".format("Retorno total", "{:+.1f}%".format(ret)))
    print("  {:<22} {:>12}".format("Drawdown maximo", "{:.1f}%".format(dd)))
    print("  {:<22} {:>12}".format("Capital final", "${:,.0f}".format(fin)))
    ftmo = "[SI]" if (ret >= 10 and abs(dd) < 10) else "[NO/PARCIAL]"
    print("  {:<22} {:>12}".format("Apto FTMO (+10%/-10%)", ftmo))
    print("="*W); print()


if __name__ == "__main__":
    keys = sys.argv[1:] if len(sys.argv) > 1 else ["gold", "silver", "oil"]
    for k in keys:
        if k in INSTRUMENTS:
            report(k)
        else:
            print("Instrumento desconocido:", k)
