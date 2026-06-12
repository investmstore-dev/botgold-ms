# BOT Mining Store GOLD — XAU/USD

Bot de trading algorítmico para pasar evaluaciones de cuentas fondeadas (FTMO).
Opera **XAU/USD en H4** usando la **Estrategia D: BB Breakout + SMA50**.

---

## Resultados Backtesting (Ene 2024 – Jun 2026)

| Métrica | Resultado |
|---|---|
| Capital inicial | $10,000 USD |
| Retorno total | +48.7% (29 meses) |
| Días para pasar FTMO +10% | **73 días** |
| Drawdown al target | -1.3% |
| Drawdown máximo total | -9.0% |
| Win Rate | 38.1% |
| Profit Factor | 1.93 |
| Ratio Ganancia/Pérdida | 3.1x |

---

## Estrategia D — Parámetros

| Indicador | Parámetro | Función |
|---|---|---|
| Bollinger Bands | 20 / Desv. 2.0 | Detecta squeeze y breakout |
| SMA 50 | Período 50 | Filtro de tendencia mayor |
| EMA 21 | Período 21 | Base del trailing stop |
| ADX 14 | Mínimo 18 | Confirma fuerza de tendencia |
| RSI 14 | 38–80 (long) / 20–62 (short) | Evita zonas extremas |
| ATR 14 | SL 2x / Trail 1x | Calibra stops por volatilidad |

**Gestión de posición:** Stop Loss = 2× ATR · Trailing Stop = 1× ATR desde EMA21 · Sin TP fijo · Riesgo 2% por trade · Máx. 1 posición simultánea

---

## Arquitectura

```
Python Bot (bot.py)
    ↓ escribe botgold_command.json
MT5 Terminal (IC Markets)
    ↕ EA BotGold_Bridge.mq5
    ↓ escribe botgold_state.json
Dashboard (botgold-dashboard-ms)
    ↑ lee data/state.json cada 30s
```

---

## Requisitos

- Python 3.11+
- MetaTrader 5 de IC Markets ([descargar aquí](https://www.icmarkets.com/es/trading-platforms/metatrader5))
- Cuenta demo IC Markets MT5 (Raw Spread, USD, $10,000, 1:100)

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/investmstore-dev/botgold-ms.git
cd botgold-ms
```

### 2. Instalar dependencias

```powershell
pip install -r requirements.txt
pip install yfinance
```

### 3. Configurar credenciales

Copia `.env.example` a `.env` y completa tus credenciales (el `.env` no se versiona):

```
MT5_LOGIN=TU_NUMERO_DE_CUENTA
MT5_PASSWORD=TU_PASSWORD
MT5_SERVER=FTMO-Server4
```

### 4. Instalar el EA en MetaTrader 5

Copia `BotGold_Bridge.mq5` a la carpeta de Experts de MT5:

```powershell
# Ajusta el ID de terminal según tu instalación
Copy-Item "BotGold_Bridge.mq5" "$env:APPDATA\MetaQuotes\Terminal\<ID_TERMINAL>\MQL5\Experts\"
```

En MetaTrader 5:
1. Presiona **F4** → abre MetaEditor
2. Busca **BotGold_Bridge** en Experts → presiona **F7** para compilar
3. Adjunta el EA al gráfico **XAUUSD,M1**
4. En la ventana del EA: **Common** → ☑ Allow automated trading → OK

### 5. Crear carpeta de datos

```powershell
mkdir data
```

### 6. Verificar conexión

```powershell
python test_conexion.py
```

Debe mostrar:
```
✓ Estado recibido del EA:
  Status  : running
  Balance : 10000.0 USD
```

---

## Uso

### Iniciar el bot

```powershell
python -m logic.bot
```

O en segundo plano (bot + dashboard, sin ventanas):

```powershell
.\start_botgold.bat   # iniciar
.\stop_botgold.bat    # detener
```

### Estructura del proyecto

```
botgold-ms/
├── config/    # configuracion y credenciales (.env no versionado)
├── model/     # estrategia de trading y backtests
├── logic/     # motor del bot en vivo
├── utils/     # conector MT5, persistencia de estado, test de conexion
├── mql5/      # EA Bridge y scripts MQL5
└── data/      # estado runtime para el dashboard (no versionado)
```

El bot:
- Se conecta al EA Bridge cada 60 segundos
- Lee velas H4 reales del broker exportadas por el EA
- Calcula todos los indicadores de la Estrategia D
- Ejecuta órdenes cuando se cumplen todas las condiciones de entrada
- Aplica trailing stop barra a barra
- Protege las reglas FTMO (DD máximo, DD diario, objetivo)

### Detener el bot

```
Ctrl + C
```

---

## Archivos generados

| Archivo | Descripción |
|---|---|
| `data/bot.log` | Log completo del bot |
| `data/state.json` | Estado actual (leído por el dashboard) |
| `data/trades.json` | Historial de trades abiertos |
| `data/equity.json` | Curva de equity histórica |

---

## Plan de Escalado FTMO

| Etapa | Cuenta | Capital | Ingreso Est. |
|---|---|---|---|
| Etapa 0 | Demo IC Markets | $10,000 | Paper trading |
| Etapa 1 | FTMO $10k (fee $155) | $10,000 | $83/mes |
| Etapa 2 | FTMO $25k (fee $250) | $25,000 | $208/mes |
| Etapa 3 | FTMO $100k (fee $540) | $100,000 | $833/mes |
| **Etapa 4** | **4× FTMO $100k** | **$400,000** | **~$3,200/mes** |

---

## Advertencia

Los resultados de backtesting no garantizan rendimientos futuros. El trading implica riesgos. Úsalo bajo tu propia responsabilidad.
