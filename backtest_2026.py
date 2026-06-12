"""
Backtest Ene 2026 - Jun 2026 -- datos reales MT5 IC Markets
Estrategia D: BB Breakout + SMA50 | XAU/USD H4
"""
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")

INITIAL_CAPITAL = 10_000
RISK_PCT        = 0.02
BB_PERIOD=20; BB_DEVS=2.0; SMA_PERIOD=50; EMA_PERIOD=21
ADX_PERIOD=14; RSI_PERIOD=14; ATR_PERIOD=14; ADX_MIN=18
RSI_LONG_MIN=38;  RSI_LONG_MAX=80
RSI_SHORT_MIN=20; RSI_SHORT_MAX=62
ATR_SL_MULT=2.0;  ATR_TRAIL_MULT=1.0
FTMO_MAX_DD=0.10; FTMO_DAILY_DD=0.05

import os
MT5_CSV = os.path.join(os.environ["APPDATA"],
          "MetaQuotes","Terminal","Common","Files","xauusd_h4_data.csv")

df_raw = pd.read_csv(MT5_CSV, parse_dates=["datetime"], encoding="utf-16")
df_raw.columns = [c.lower().strip() for c in df_raw.columns]
df_raw.set_index("datetime", inplace=True)
df_raw.sort_index(inplace=True)
if df_raw.index.tz is not None:
    df_raw.index = df_raw.index.tz_localize(None)
df_raw = df_raw[["open","high","low","close","volume"]].dropna()

# Warmup: 6 meses previos para calentar indicadores
df_raw = df_raw[df_raw.index >= "2025-06-01"]

c,h,l = df_raw["close"], df_raw["high"], df_raw["low"]
bm = c.rolling(BB_PERIOD).mean(); bs = c.rolling(BB_PERIOD).std()
df_raw["bb_upper"]   = bm + BB_DEVS*bs
df_raw["bb_lower"]   = bm - BB_DEVS*bs
df_raw["bb_width"]   = df_raw["bb_upper"] - df_raw["bb_lower"]
df_raw["bb_squeeze"] = df_raw["bb_width"] < df_raw["bb_width"].rolling(BB_PERIOD).mean()
df_raw["sma50"]      = c.rolling(SMA_PERIOD).mean()
df_raw["sma50_slope"]= df_raw["sma50"].diff(3)
df_raw["ema21"]      = c.ewm(span=EMA_PERIOD, adjust=False).mean()
tr = pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
df_raw["atr"] = tr.rolling(ATR_PERIOD).mean()
d = c.diff(); g = d.clip(lower=0).rolling(RSI_PERIOD).mean()
ls = (-d.clip(upper=0)).rolling(RSI_PERIOD).mean()
df_raw["rsi"] = 100 - (100/(1 + g/ls.replace(0,np.nan)))
up = h.diff(); dn = -l.diff()
pdm = pd.Series(np.where((up>dn)&(up>0), up, 0.0), index=df_raw.index)
mdm = pd.Series(np.where((dn>up)&(dn>0), dn, 0.0), index=df_raw.index)
atr14 = tr.rolling(ADX_PERIOD).mean()
pdi = 100*pdm.rolling(ADX_PERIOD).mean()/atr14
mdi = 100*mdm.rolling(ADX_PERIOD).mean()/atr14
dx  = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
df_raw["adx"] = dx.rolling(ADX_PERIOD).mean()
df_all = df_raw.dropna()

# Periodo real de prueba
df = df_all[df_all.index >= "2026-01-01"].copy()
print("Velas H4 reales (Ene-Jun 2026): {}".format(len(df)))
print("Inicio : {} | XAUUSD: {:.2f}".format(df.index[0].date(), df["close"].iloc[0]))
print("Fin    : {} | XAUUSD: {:.2f}".format(df.index[-1].date(), df["close"].iloc[-1]))
print()

# Simulacion
capital=INITIAL_CAPITAL; peak=capital; trades=[]; pos=None; daily_start={}

for i in range(1, len(df)):
    row=df.iloc[i]; prev=df.iloc[i-1]; dt=df.index[i].date()
    if dt not in daily_start: daily_start[dt]=capital

    if pos:
        trail=(row["ema21"]-ATR_TRAIL_MULT*row["atr"] if pos["type"]=="long"
               else row["ema21"]+ATR_TRAIL_MULT*row["atr"])
        if pos["type"]=="long"  and trail>pos["sl"]: pos["sl"]=trail
        elif pos["type"]=="short" and trail<pos["sl"]: pos["sl"]=trail
        hit=((pos["type"]=="long" and row["low"]<=pos["sl"]) or
             (pos["type"]=="short" and row["high"]>=pos["sl"]))
        if hit:
            mult=1 if pos["type"]=="long" else -1
            pnl=(pos["sl"]-pos["entry"])*mult*pos["lot"]*100
            capital+=pnl; peak=max(peak,capital)
            trades.append({"entry_date":pos["entry_date"],"exit_date":df.index[i],
                "type":pos["type"],"entry":round(pos["entry"],2),"exit":round(pos["sl"],2),
                "lot":pos["lot"],"pnl_usd":round(pnl,2),"capital":round(capital,2)})
            pos=None
        continue

    if (capital-peak)/INITIAL_CAPITAL<=-FTMO_MAX_DD: continue
    if (capital-daily_start[dt])/INITIAL_CAPITAL<=-FTMO_DAILY_DD: continue

    sq=prev["bb_squeeze"]; ok=row["adx"]>=ADX_MIN
    if (sq and row["close"]>row["bb_upper"] and row["sma50_slope"]>0
            and row["close"]>row["sma50"] and ok
            and RSI_LONG_MIN<=row["rsi"]<=RSI_LONG_MAX):
        sl_d=ATR_SL_MULT*row["atr"]
        lot=max(0.01,round((capital*RISK_PCT)/(sl_d*100),2))
        pos={"type":"long","entry":row["close"],"sl":row["close"]-sl_d,
             "lot":lot,"entry_date":df.index[i]}
    elif (sq and row["close"]<row["bb_lower"] and row["sma50_slope"]<0
            and row["close"]<row["sma50"] and ok
            and RSI_SHORT_MIN<=row["rsi"]<=RSI_SHORT_MAX):
        sl_d=ATR_SL_MULT*row["atr"]
        lot=max(0.01,round((capital*RISK_PCT)/(sl_d*100),2))
        pos={"type":"short","entry":row["close"],"sl":row["close"]+sl_d,
             "lot":lot,"entry_date":df.index[i]}

# Metricas
df_t = pd.DataFrame(trades)
if df_t.empty:
    print("Sin trades en Ene-Jun 2026.")
    exit()

wins=df_t[df_t["pnl_usd"]>0]; loss=df_t[df_t["pnl_usd"]<=0]
n=len(df_t); wr=len(wins)/n*100
aw=wins["pnl_usd"].mean() if len(wins) else 0
al=loss["pnl_usd"].mean() if len(loss) else 0
pf=wins["pnl_usd"].sum()/abs(loss["pnl_usd"].sum()) if len(loss) else 999
fin=df_t["capital"].iloc[-1]; ret=(fin-INITIAL_CAPITAL)/INITIAL_CAPITAL*100
gpr=abs(aw/al) if al else 0
eq=[INITIAL_CAPITAL]+df_t["capital"].tolist()
pk=eq[0]; dd_max=0.0
for v in eq: pk=max(pk,v); dd_max=min(dd_max,(v-pk)/pk*100)
target=INITIAL_CAPITAL*1.10; d2t=None; dd10=None
for t in df_t.itertuples():
    if t.capital>=target:
        d2t=(t.exit_date-df_t["entry_date"].iloc[0]).days
        sub=[INITIAL_CAPITAL]+df_t[df_t["exit_date"]<=t.exit_date]["capital"].tolist()
        pk2=sub[0]; dd2=0.0
        for v in sub: pk2=max(pk2,v); dd2=min(dd2,(v-pk2)/pk2*100)
        dd10=dd2; break
streak=ms=0
for p in df_t["pnl_usd"]:
    if p<=0: streak+=1; ms=max(ms,streak)
    else: streak=0
months=max(1,(df_t["exit_date"].iloc[-1]-df_t["exit_date"].iloc[0]).days/30)

W=62; SEP="="*W; S2="-"*W
print(); print(SEP)
print("  BACKTEST Ene 2026 - Jun 2026  |  Datos reales MT5")
print("  Estrategia D: BB Breakout + SMA50 | XAU/USD H4 | 2%")
print(SEP)
print("  {:<30} {:>14}   {:>10}".format("METRICA","RESULTADO","PDF REF"))
print(S2)
print("  {:<30} {:>14}   {:>10}".format("Trades totales", n, "42 (29m)"))
print("  {:<30} {:>14}   {:>10}".format("Ganadores", "{} ({:.1f}%)".format(len(wins),wr), "38.1%"))
print("  {:<30} {:>14}   {:>10}".format("Perdedores", "{} ({:.1f}%)".format(len(loss),100-wr), "61.9%"))
print("  {:<30} {:>14}   {:>10}".format("Promedio ganancia", "${:,.0f}".format(aw), "$631"))
print("  {:<30} {:>14}   {:>10}".format("Promedio perdida", "${:,.0f}".format(al), "$-201"))
print("  {:<30} {:>14}   {:>10}".format("Ratio G/P", "{:.1f}x".format(gpr), "3.1x"))
print("  {:<30} {:>14}   {:>10}".format("Profit Factor", "{:.2f}".format(pf), "1.93"))
print("  {:<30} {:>14}   {:>10}".format("Trades / mes", "{:.1f}".format(n/months), "1.5"))
print("  {:<30} {:>14}   {:>10}".format("Retorno total", "{:+.1f}%".format(ret), "+48.7%"))
print("  {:<30} {:>14}   {:>10}".format("Drawdown maximo", "{:+.1f}%".format(dd_max), "-9.0%"))
print("  {:<30} {:>14}   {:>10}".format("Racha max perdidas", "{} trades".format(ms), "5 trades"))
print("  {:<30} {:>14}   {:>10}".format("Capital final", "${:,.0f}".format(fin), "$14,865"))
print(S2)
d2t_s="{} dias".format(d2t) if d2t else "NO ALCANZADO"
dd10_s="{:+.1f}%".format(dd10) if dd10 else "N/A"
ftmo_ok = d2t is not None and abs(dd_max)<10
print("  {:<30} {:>14}   {:>10}".format("Dias para FTMO +10%", d2t_s, "73 dias"))
print("  {:<30} {:>14}   {:>10}".format("DD al alcanzar +10%", dd10_s, "-1.3%"))
print("  {:<30} {:>14}   {:>10}".format("Cumple FTMO", "[SI]" if ftmo_ok else "[NO]", "[SI]"))
print(SEP)

print()
print("  HISTORIAL DE TRADES")
print(S2)
print("  {:<14} {:<14} {:5} {:>8} {:>8} {:>5} {:>10} {:>10}".format(
    "Entrada","Salida","Tipo","Entry","Exit","Lot","P&L USD","Capital"))
print("  "+"-"*87)
for _,t in df_t.iterrows():
    flag=" WIN" if t["pnl_usd"]>0 else "    "
    print("  {:<14} {:<14} {:5} {:>8.2f} {:>8.2f} {:>5.2f} ${:>+9,.2f} ${:>9,.2f}{}".format(
        str(t["entry_date"])[:14], str(t["exit_date"])[:14],
        t["type"][0].upper(), t["entry"], t["exit"],
        t["lot"], t["pnl_usd"], t["capital"], flag))
print(); print(SEP)
