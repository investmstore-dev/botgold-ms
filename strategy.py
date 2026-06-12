import pandas as pd
import numpy as np


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula todos los indicadores sobre el DataFrame de velas H4."""
    from config import (BB_PERIOD, BB_DEVS, SMA_PERIOD, EMA_PERIOD,
                        ADX_PERIOD, RSI_PERIOD, ATR_PERIOD)

    c = df["close"]
    h = df["high"]
    l = df["low"]

    # --- Bollinger Bands (mantenidas para compatibilidad) ---
    bb_mid         = c.rolling(BB_PERIOD).mean()
    bb_std         = c.rolling(BB_PERIOD).std()
    df["bb_upper"] = bb_mid + BB_DEVS * bb_std
    df["bb_lower"] = bb_mid - BB_DEVS * bb_std
    df["bb_width"] = df["bb_upper"] - df["bb_lower"]

    # --- Medias moviles ---
    df["ema50"]  = c.ewm(span=50,  adjust=False).mean()   # filtro tendencia rapida
    df["ema200"] = c.ewm(span=200, adjust=False).mean()   # filtro tendencia lenta
    df["ema21"]  = c.ewm(span=EMA_PERIOD, adjust=False).mean()  # trailing stop base
    df["sma50"]  = c.rolling(SMA_PERIOD).mean()           # pendiente de tendencia
    df["sma50_slope"] = df["sma50"].diff(3)

    # --- ATR ---
    tr = pd.concat([
        h - l,
        (h - c.shift()).abs(),
        (l - c.shift()).abs()
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(ATR_PERIOD).mean()

    # --- RSI ---
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss  = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
    df["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

    # --- ADX ---
    df["adx"] = _compute_adx(h, l, c, ADX_PERIOD)

    # --- MACD (19/39/9) optimo para H4 en gold ---
    ema_fast       = c.ewm(span=19, adjust=False).mean()
    ema_slow       = c.ewm(span=39, adjust=False).mean()
    df["macd"]     = ema_fast - ema_slow
    df["macd_sig"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"]= df["macd"] - df["macd_sig"]

    # --- Pullback detector: precio toco el EMA50 en las ultimas 3 velas ---
    # Se considera pullback cuando el low llego al rango EMA50 +/- 0.5*ATR
    ema50_band_hi = df["ema50"] + 0.5 * df["atr"]
    ema50_band_lo = df["ema50"] - 0.5 * df["atr"]
    touched_ema50 = (l <= ema50_band_hi) & (h >= ema50_band_lo)
    df["pullback_long"]  = touched_ema50.rolling(3).max().astype(bool)

    ema50_band_hi_s = df["ema50"] + 0.5 * df["atr"]
    ema50_band_lo_s = df["ema50"] - 0.5 * df["atr"]
    touched_ema50_s = (h >= ema50_band_lo_s) & (l <= ema50_band_hi_s)
    df["pullback_short"] = touched_ema50_s.rolling(3).max().astype(bool)

    # BB squeeze (mantenido)
    df["bb_squeeze"] = df["bb_width"] < df["bb_width"].rolling(BB_PERIOD).mean()

    return df


def _compute_adx(high, low, close, period):
    up   = high.diff()
    down = -low.diff()

    plus_dm  = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=high.index)

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)

    atr      = tr.rolling(period).mean()
    plus_di  = 100 * plus_dm.rolling(period).mean() / atr
    minus_di = 100 * minus_dm.rolling(period).mean() / atr
    dx       = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    return dx.rolling(period).mean()


def check_entry(df: pd.DataFrame):
    """
    Estrategia E: EMA Pullback + EMA200 Trend Filter
    Condiciones LONG:
      - EMA50 > EMA200 (tendencia alcista confirmada)
      - Precio hizo pullback al EMA50 en las ultimas 3 velas
      - Close actual > EMA50 (rebote confirmado)
      - MACD hist cruzando de negativo a positivo (momentum)
      - ADX >= 20 (tendencia con fuerza)
      - RSI entre 40-72 (ni sobrecomprado ni sobrevendido)
    Condiciones SHORT: espejo inverso
    """
    from config import ADX_MIN, RSI_LONG_MIN, RSI_LONG_MAX, RSI_SHORT_MIN, RSI_SHORT_MAX

    if len(df) < 210:
        return None

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    adx_ok    = curr["adx"] >= ADX_MIN
    trend_up  = curr["ema50"] > curr["ema200"]
    trend_dn  = curr["ema50"] < curr["ema200"]
    macd_bull = prev["macd_hist"] < 0 and curr["macd_hist"] >= 0
    macd_bear = prev["macd_hist"] > 0 and curr["macd_hist"] <= 0

    # LONG
    if (trend_up
            and curr["pullback_long"]
            and curr["close"] > curr["ema50"]
            and (macd_bull or curr["macd_hist"] > 0)
            and adx_ok
            and RSI_LONG_MIN <= curr["rsi"] <= RSI_LONG_MAX):
        return "long"

    # SHORT
    if (trend_dn
            and curr["pullback_short"]
            and curr["close"] < curr["ema50"]
            and (macd_bear or curr["macd_hist"] < 0)
            and adx_ok
            and RSI_SHORT_MIN <= curr["rsi"] <= RSI_SHORT_MAX):
        return "short"

    return None


def calc_lot_size(capital: float, atr: float, price: float, risk_pct: float) -> float:
    """
    Calcula el lotaje para arriesgar exactamente risk_pct del capital.
    XAU/USD: 1 lote = 100 oz. lot = (capital * risk) / (atr_sl * 100)
    """
    from config import ATR_SL_MULT
    risk_usd  = capital * risk_pct
    sl_points = atr * ATR_SL_MULT
    lot = risk_usd / (sl_points * 100)
    lot = max(0.01, round(lot, 2))
    return lot


def calc_trailing_sl(position_type: str, ema21: float, atr: float) -> float:
    """Trailing stop = EMA21 +/- 1x ATR."""
    from config import ATR_TRAIL_MULT
    if position_type == "long":
        return ema21 - ATR_TRAIL_MULT * atr
    return ema21 + ATR_TRAIL_MULT * atr
