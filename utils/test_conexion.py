from utils import mt5_connector as m
import json
from pathlib import Path

print("Verificando EA Bridge...")
print("Carpeta MT5 Common:", m.MT5_COMMON)
print("State file existe:", m.STATE_FILE.exists())

if m.STATE_FILE.exists():
    with open(m.STATE_FILE) as f:
        state = json.load(f)
    print("\n✓ Estado recibido del EA:")
    print(f"  Status  : {state.get('status')}")
    print(f"  Cuenta  : {state.get('login')}")
    print(f"  Balance : {state.get('balance')} {state.get('currency')}")
    print(f"  Equity  : {state.get('equity')}")
    print(f"  Servidor: {state.get('server')}")
    print(f"  Hora MT5: {state.get('time')}")
else:
    print("\n✗ State file no encontrado aun")
    print("  Asegurate de que el EA BotGold_Bridge este corriendo en MT5")

print("\nProbando ping al EA...")
ok = m.connect()
print("Conexion:", "OK" if ok else "FALLO")

acc = m.get_account()
print("Cuenta:", acc)
