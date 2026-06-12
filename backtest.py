"""
Backtest -- Estrategia D: BB Breakout + SMA50
XAU/USD H4 | Enero 2024 - Junio 2026 (29 meses)
Datos reales exportados desde MetaTrader 5 IC Markets
"""
import pandas as pd
import numpy as np
import os
import warnings
warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# PARAMETROS (exactos del PDF)
# ---------------------------------------------------------------------------
INITIAL_CAPITAL = 10_000
RISK_PCT        = 0.02
BB_PERIOD       = 20;  BB_DEVS       = 2.0
SMA_PERIOD      = 50;  EMA_PERIOD    = 21
ADX_PERIOD      = 14;  RSI_PERIOD    = 14;  ATR_PERIOD = 14
ADX_MIN         = 18
RSI_LONG_MIN    = 38;  RSI_LONG_MAX  = 80
RSI_SHORT_MIN   = 20;  RSI_SHORT_MAX = 62
ATR_SL_MULT     = 2.0; ATR_TRAIL_MULT = 1.0
FTMO_MAX_DD     = 0.10; FTMO_DAILY_DD = 0.05

# ---------------------------------------------------------------------------
# CARGA DE DATOS
# Prioridad 1: CSV exportado desde MT5 (datos reales IC Markets)
# Prioridad 2: yfinance como fallback
# ---------------------------------------------------------------------------
MT5_COMMON = os.path.join(os.environ["APPDATA"],
             "MetaQuotes", "Terminal", "Common", "Files")
MT5_CSV    = os.path.join(MT5_COMMON, "xauusd_h4_data.csv")

def load_mt5_csv(path):
    df = pd.read_csv(path, parse_dates=["datetime"], encoding="utf-16")
    df.columns = [c.lower().strip() for c in df.columns]
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df[["open","high","low","close","volume"]].dropna()

def load_yfinance_fallback():
    import yfinance as yf
    from datetime import datetime, timedelta
    print("  Usando yfinance como fallback...")

    # Parte 1: diarias Ene-Jun 2024
    raw_d = yf.Ticker("GC=F").history(start="2024-01-01", end="2024-07-01", interval="1d")
    raw_d.columns = [c.lower() for c in raw_d.columns]
    raw_d = raw_d[["open","high","low","close","volume"]]
    if hasattr(raw_d.index, "tz") and raw_d.index.tz is not None:
        raw_d.index = raw_d.index.tz_localize(None)
    df_early = raw_d.dropna()

    # Parte 2: 1h -> H4 Jul 2024 - Jun 2026
    chunks = []
    cursor = datetime(2024, 7, 1)
    end_dt = datetime(2026, 6, 10)
    while cursor < end_dt:
        chunk_end = min(cursor + timedelta(days=59), end_dt)
        try:
            raw = yf.Ticker("GC=F").history(
                start=cursor.strftime("%Y-%m-%d"),
                end=chunk_end.strftime("%Y-%m-%d"),
                interval="1h"
            )
            if not raw.empty:
                chunks.append(raw)
        except Exception:
            pass
        cursor = chunk_end + timedelta(days=1)

    raw_1h = pd.concat(chunks)
    raw_1h = raw_1h[~raw_1h.index.duplicated(keep="first")]
    raw_1h.sort_index(inplace=True)
    raw_1h.columns = [c.lower() for c in raw_1h.columns]
    raw_1h = raw_1h[["open","high","low","close","volume"]]
    if hasattr(raw_1h.index, "tz") and raw_1h.index.tz is not None:
        raw_1h.index = raw_1h.index.tz_localize(None)
    df_late = raw_1h.resample("4h").agg(
        {"open":"first","high":"max","low":"min","close":"last","volume":"sum"}
    ).dropna()

    combined = pd.concat([df_early, df_late])
    combined = combined[~combined.index.duplicated(keep="first")]
    return combined.sort_index()


# --- Seleccionar fuente de datos ---
if os.path.exists(MT5_CSV):
    print(f"Cargando datos reales MT5: {MT5_CSV}")
    df_raw = load_mt5_csv(MT5_CSV)
    source = "MetaTrader 5 IC Markets (datos reales)"
else:
    print(f"Archivo MT5 no encontrado: {MT5_CSV}")
    print("Para exportarlo desde MT5:")
    print("  1. Abre MetaTrader 5")
    print("  2. Abre el grafico XAUUSD H4")
    print("  3. MetaEditor (F4) -> Scripts -> ExportH4Data -> Compilar (F7)")
    print("  4. Arrastra ExportH4Data al grafico XAUUSD")
    print("  5. Click OK -> espera el mensaje de exito")
    print("  6. Vuelve a ejecutar este script\n")
    print("Continuando con yfinance (aproximacion)...\n")
    df_raw = load_yfinance_fallback()
    source = "Yahoo Finance / yfinance (aproximacion)"

meses = (df_raw.index[-1] - df_raw.index[0]).days / 30
print(f"\nFuente   : {source}")
print(f"Velas    : {len(df_raw)}")
print(f"Periodo  : {df_raw.index[0].date()} a {df_raw.index[-1].date()} ({meses:.1f} meses)\n")


# ---------------------------------------------------------------------------
# INDICADORES
# ---------------------------------------------------------------------------
def add_indicators(df):
    c, h, l = df["close"], df["high"], df["low"]
    bm = c.rolling(BB_PERIOD).mean(); bs = c.rolling(BB_PERIOD).std()
    df["bb_upper"]   = bm + BB_DEVS * bs
    df["bb_lower"]   = bm - BB_DEVS * bs
    df["bb_width"]   = df["bb_upper"] - df["bb_lower"]
    df["bb_squeeze"] = df["bb_width"] < df["bb_width"].rolling(BB_PERIOD).mean()
    df["sma50"]      = c.rolling(SMA_PERIOD).mean()
    df["sma50_slope"]= df["sma50"].diff(3)
    df["ema21"]      = c.ewm(span=EMA_PERIOD, adjust=False).mean()
    tr = pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    df["atr"]        = tr.rolling(ATR_PERIOD).mean()
    d = c.diff(); g = d.clip(lower=0).rolling(RSI_PERIOD).mean()
    ls= (-d.clip(upper=0)).rolling(RSI_PERIOD).mean()
    df["rsi"]        = 100 - (100 / (1 + g / ls.replace(0, np.nan)))
    up=h.diff(); dn=-l.diff()
    pdm = pd.Series(np.where((up>dn)&(up>0), up, 0.0), index=df.index)
    mdm = pd.Series(np.where((dn>up)&(dn>0), dn, 0.0), index=df.index)
    at14= tr.rolling(ADX_PERIOD).mean()
    pdi = 100*pdm.rolling(ADX_PERIOD).mean()/at14
    mdi = 100*mdm.rolling(ADX_PERIOD).mean()/at14
    dx  = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)
    df["adx"] = dx.rolling(ADX_PERIOD).mean()
    return df.dropna()

df = add_indicators(df_raw.copy())
print(f"Velas con indicadores: {len(df)}\n")


# ---------------------------------------------------------------------------
# SIMULACION BARRA A BARRA
# ---------------------------------------------------------------------------
capital      = INITIAL_CAPITAL
peak_capital = capital
trades       = []
position     = None
daily_start  = {}

for i in range(1, len(df)):
    row  = df.iloc[i]
    prev = df.iloc[i - 1]
    dt   = df.index[i].date()

    if dt not in daily_start:
        daily_start[dt] = capital

    # Gestion de posicion abierta
    if position:
        trail = (row["ema21"] - ATR_TRAIL_MULT * row["atr"]
                 if position["type"] == "long"
                 else row["ema21"] + ATR_TRAIL_MULT * row["atr"])
        if position["type"] == "long"  and trail > position["sl"]: position["sl"] = trail
        elif position["type"] == "short" and trail < position["sl"]: position["sl"] = trail

        hit = ((position["type"]=="long"  and row["low"]  <= position["sl"]) or
               (position["type"]=="short" and row["high"] >= position["sl"]))
        if hit:
            mult    = 1 if position["type"] == "long" else -1
            pnl_usd = (position["sl"] - position["entry"]) * mult * position["lot"] * 100
            capital += pnl_usd
            peak_capital = max(peak_capital, capital)
            trades.append({
                "entry_date": position["entry_date"],
                "exit_date":  df.index[i],
                "type":       position["type"],
                "entry":      round(position["entry"], 2),
                "exit":       round(position["sl"], 2),
                "lot":        position["lot"],
                "pnl_usd":    round(pnl_usd, 2),
                "capital":    round(capital, 2),
            })
            position = None
        continue

    # Guardias FTMO (no detienen el sim, pero bloquean nuevas entradas)
    if (capital - peak_capital) / INITIAL_CAPITAL <= -FTMO_MAX_DD:
        continue
    if (capital - daily_start[dt]) / INITIAL_CAPITAL <= -FTMO_DAILY_DD:
        continue

    # Logica Estrategia D exacta del PDF
    sq = prev["bb_squeeze"]
    ok = row["adx"] >= ADX_MIN

    if (sq and row["close"] > row["bb_upper"]
            and row["sma50_slope"] > 0 and row["close"] > row["sma50"]
            and ok and RSI_LONG_MIN <= row["rsi"] <= RSI_LONG_MAX):
        sl_d = ATR_SL_MULT * row["atr"]
        lot  = max(0.01, round((capital * RISK_PCT) / (sl_d * 100), 2))
        position = {"type":"long",  "entry":row["close"], "sl":row["close"]-sl_d,
                    "lot":lot, "entry_date":df.index[i]}

    elif (sq and row["close"] < row["bb_lower"]
            and row["sma50_slope"] < 0 and row["close"] < row["sma50"]
            and ok and RSI_SHORT_MIN <= row["rsi"] <= RSI_SHORT_MAX):
        sl_d = ATR_SL_MULT * row["atr"]
        lot  = max(0.01, round((capital * RISK_PCT) / (sl_d * 100), 2))
        position = {"type":"short", "entry":row["close"], "sl":row["close"]+sl_d,
                    "lot":lot, "entry_date":df.index[i]}


# ---------------------------------------------------------------------------
# METRICAS
# ---------------------------------------------------------------------------
df_t = pd.DataFrame(trades)
if df_t.empty:
    print("Sin trades generados."); exit()

wins = df_t[df_t["pnl_usd"] > 0]
loss = df_t[df_t["pnl_usd"] <= 0]
n    = len(df_t)
wr   = len(wins) / n * 100
aw   = wins["pnl_usd"].mean() if len(wins) else 0
al   = loss["pnl_usd"].mean() if len(loss) else 0
gp   = wins["pnl_usd"].sum(); gl = abs(loss["pnl_usd"].sum())
pf   = gp / gl if gl else 999
fin  = df_t["capital"].iloc[-1]
ret  = (fin - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
gpr  = abs(aw / al) if al else 0

eq = [INITIAL_CAPITAL] + df_t["capital"].tolist()
pk = eq[0]; dd_max = 0.0
for v in eq: pk = max(pk, v); dd_max = min(dd_max, (v-pk)/pk*100)

target = INITIAL_CAPITAL * 1.10
d2t = None; dd10 = None
for t in df_t.itertuples():
    if t.capital >= target:
        d2t = (t.exit_date - df_t["entry_date"].iloc[0]).days
        sub = [INITIAL_CAPITAL] + df_t[df_t["exit_date"] <= t.exit_date]["capital"].tolist()
        pk2 = sub[0]; dd2 = 0.0
        for v in sub: pk2 = max(pk2, v); dd2 = min(dd2, (v-pk2)/pk2*100)
        dd10 = dd2; break

streak = ms = 0
for p in df_t["pnl_usd"]:
    if p <= 0: streak+=1; ms=max(ms,streak)
    else: streak=0

months = max(1, (df_t["exit_date"].iloc[-1] - df_t["exit_date"].iloc[0]).days / 30)
tpm    = n / months

df_t["year"] = df_t["exit_date"].dt.year
by_year = df_t.groupby("year")["pnl_usd"].agg(["count","sum"])
ftmo_ok = (d2t is not None and abs(dd_max) < 10)


# ---------------------------------------------------------------------------
# IMPRIMIR
# ---------------------------------------------------------------------------
W = 62; SEP = "=" * W; S2 = "-" * W

print()
print(SEP)
print("  BOT MINING STORE GOLD -- BACKTEST ESTRATEGIA D")
print("  BB Breakout + SMA50 | XAU/USD H4 | Riesgo 2%")
print(SEP)
print(f"  Fuente de datos: {source}")
print(SEP)
print(f"  {'METRICA':<30} {'RESULTADO':>14}   {'PDF REF':>10}")
print(S2)
print(f"  {'Trades totales':<30} {n:>14}   {'42':>10}")
print(f"  {'Ganadores':<30} {f'{len(wins)} ({wr:.1f}%)':>14}   {'16 (38.1%)':>10}")
print(f"  {'Perdedores':<30} {f'{len(loss)} ({100-wr:.1f}%)':>14}   {'26 (61.9%)':>10}")
print(f"  {'Promedio ganancia':<30} {'${:,.0f}'.format(aw):>14}   {'$631':>10}")
print(f"  {'Promedio perdida':<30} {'${:,.0f}'.format(al):>14}   {'$-201':>10}")
print(f"  {'Ratio G/P':<30} {'{:.1f}x'.format(gpr):>14}   {'3.1x':>10}")
print(f"  {'Profit Factor':<30} {'{:.2f}'.format(pf):>14}   {'1.93':>10}")
print(f"  {'Trades / mes':<30} {'{:.1f}'.format(tpm):>14}   {'1.5':>10}")
print(f"  {'Retorno total':<30} {'{:+.1f}%'.format(ret):>14}   {'+48.7%':>10}")
print(f"  {'Drawdown maximo':<30} {'{:+.1f}%'.format(dd_max):>14}   {'-9.0%':>10}")
print(f"  {'Racha max perdidas':<30} {'{} trades'.format(ms):>14}   {'5 trades':>10}")
print(f"  {'Capital final':<30} {'${:,.0f}'.format(fin):>14}   {'$14,865':>10}")
print(S2)
d2t_s  = "{} dias".format(d2t) if d2t else "NO ALCANZADO"
dd10_s = "{:+.1f}%".format(dd10) if dd10 else "N/A"
print(f"  {'Dias para FTMO +10%':<30} {d2t_s:>14}   {'73 dias':>10}")
print(f"  {'DD al alcanzar +10%':<30} {dd10_s:>14}   {'-1.3%':>10}")
print(f"  {'Cumple FTMO':<30} {'[SI]' if ftmo_ok else '[NO]':>14}   {'[SI]':>10}")
print(SEP)

print("\n  RESULTADOS POR ANNO")
print(S2)
print(f"  {'Anno':<8} {'Trades':>8} {'P&L USD':>12} {'Retorno':>10}")
running = INITIAL_CAPITAL
for year, r in by_year.iterrows():
    ret_y = r["sum"] / running * 100; running += r["sum"]
    print(f"  {year:<8} {int(r['count']):>8} ${'  {:,.2f}'.format(r['sum']):>12} {'{:+.2f}%'.format(ret_y):>10}")

print("\n  HISTORIAL COMPLETO DE TRADES")
print(S2)
print(f"  {'Entrada':14} {'Salida':14} {'T':5} {'Entry':>8} {'Exit':>8} {'Lot':>5} {'P&L USD':>10} {'Capital':>10}")
print(f"  {'-'*14} {'-'*14} {'-'*5} {'-'*8} {'-'*8} {'-'*5} {'-'*10} {'-'*10}")
for _, t in df_t.iterrows():
    flag = " WIN" if t["pnl_usd"] > 0 else "    "
    print(f"  {str(t['entry_date'])[:14]:14} {str(t['exit_date'])[:14]:14}"
          f" {t['type'][0].upper():5} {t['entry']:>8.2f} {t['exit']:>8.2f}"
          f" {t['lot']:>5.2f} ${'  {:+,.2f}'.format(t['pnl_usd']):>10} ${'  {:,.2f}'.format(t['capital']):>10}{flag}")

print()
print(SEP)
