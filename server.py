"""
RECAUDO-T — Servicio de resumen mensual de viajes
Implementa:
  R1 Introducir Concurrencia: pool de W trabajadores (hilos) configurable.
  R2 Mantener Múltiples Copias de Datos (caché): caché en memoria por (id_tarjeta, viajes).

Ejecutar:
    WORKERS=1 CACHE_ENABLED=false python server.py     # E0: línea base
    WORKERS=8 CACHE_ENABLED=false python server.py     # E1: con concurrencia
    WORKERS=8 CACHE_ENABLED=true  python server.py     # E2: concurrencia + caché
"""

import os
import time
import random
import threading
import zlib
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request

# ---------------------------------------------------------------------------
# Configuración vía variables de entorno (así se cambia W sin tocar código)
# ---------------------------------------------------------------------------
WORKERS = int(os.environ.get("WORKERS", "1"))
CACHE_ENABLED = os.environ.get("CACHE_ENABLED", "false").lower() == "true"
CALC_MIN_MS = int(os.environ.get("CALC_MIN_MS", "150"))
CALC_MAX_MS = int(os.environ.get("CALC_MAX_MS", "250"))

app = Flask(__name__)

# Pool de trabajadores: aquí es donde realmente se limita la concurrencia.
# No delegamos todo el trabajo al servidor web; el cálculo se ejecuta
# siempre dentro de este executor de tamaño W.
executor = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="worker")

# Caché en memoria, protegida con lock porque varios hilos escriben a la vez.
cache = {}
cache_lock = threading.Lock()


def calcular_resumen(id_tarjeta: str, viajes: int) -> dict:
    """Simula el costo real de sumar todos los viajes del usuario."""
    duracion = random.uniform(CALC_MIN_MS / 1000, CALC_MAX_MS / 1000)
    time.sleep(duracion)

    # Generamos un total determinístico (mismo id + mismo N -> mismo resultado)
    seed = zlib.crc32(f"{id_tarjeta}:{viajes}".encode())
    rng = random.Random(seed)
    gasto_total = sum(rng.randint(1500, 5000) for _ in range(viajes))

    return {
        "id_tarjeta": id_tarjeta,
        "total_viajes": viajes,
        "gasto_total": gasto_total,
    }


def buscar_en_cache(id_tarjeta: str, viajes: int):
    """Devuelve el resumen guardado (con desde_cache=True) o None si no esta."""
    if not CACHE_ENABLED:
        return None
    with cache_lock:
        guardado = cache.get((id_tarjeta, viajes))
        if guardado is None:
            return None
        resultado = dict(guardado)
    resultado["desde_cache"] = True
    return resultado


def calcular_y_guardar(id_tarjeta: str, viajes: int) -> dict:
    """Ruta MISS: se ejecuta dentro del pool de trabajadores."""
    resultado = calcular_resumen(id_tarjeta, viajes)
    if CACHE_ENABLED:
        with cache_lock:
            cache[(id_tarjeta, viajes)] = dict(resultado)
    resultado["desde_cache"] = False
    return resultado


@app.route("/resumen/<id_tarjeta>")
def resumen(id_tarjeta):
    viajes = int(request.args.get("viajes", 40))
    # HIT: se responde de inmediato, sin pasar por la cola del pool.
    resultado = buscar_en_cache(id_tarjeta, viajes)
    if resultado is not None:
        return jsonify(resultado)
    # MISS: se envía el trabajo al pool de W trabajadores y se espera el resultado.
    future = executor.submit(calcular_y_guardar, id_tarjeta, viajes)
    resultado = future.result()
    return jsonify(resultado)


@app.route("/config")
def config():
    return jsonify({
        "workers_activos": WORKERS,
        "cache_enabled": CACHE_ENABLED,
        "entradas_cache": len(cache),
    })


if __name__ == "__main__":
    print(f"[server] WORKERS={WORKERS}  CACHE_ENABLED={CACHE_ENABLED}  "
          f"CALC={CALC_MIN_MS}-{CALC_MAX_MS} ms")
    # threaded=True para que Flask pueda recibir varias solicitudes a la vez
    # y dejarlas esperando en el executor (que es quien de verdad limita W).
    app.run(host="0.0.0.0", port=5000, threaded=True)
