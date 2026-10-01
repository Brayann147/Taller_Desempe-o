"""
Cliente de carga para RECAUDO-T.
Dispara una ráfaga de solicitudes GET /resumen/{id_tarjeta}, reutilizando
un conjunto pequeño de tarjetas, y registra un CSV con:
    timestamp_envio, timestamp_respuesta, exito, desde_cache, id_tarjeta

Uso:
    python client.py --salida e0.csv
    python client.py --salida e1.csv --duracion 20 --tarjetas 10 --hilos 20
"""

import argparse
import csv
import random
import time
import threading
import requests

TIMEOUT_S = 3.0  # solicitudes que tardan más que esto cuentan como no procesadas


def worker(url, tarjetas, viajes, pausa, fin, resultados, lock):
    session = requests.Session()
    while time.time() < fin:
        id_tarjeta = random.choice(tarjetas)
        t_envio = time.time()
        exito = 0
        desde_cache = 0
        try:
            r = session.get(
                f"{url}/resumen/{id_tarjeta}",
                params={"viajes": viajes},
                timeout=TIMEOUT_S,
            )
            t_resp = time.time()
            # sin respuesta dentro del límite (3 s) => evento no procesado
            if r.status_code == 200 and (t_resp - t_envio) <= TIMEOUT_S:
                exito = 1
                desde_cache = 1 if r.json().get("desde_cache") else 0
        except requests.exceptions.RequestException:
            t_resp = time.time()

        with lock:
            resultados.append((t_envio, t_resp, exito, desde_cache, id_tarjeta))
        # pausa corta de cada "usuario" antes de su siguiente consulta
        time.sleep(random.uniform(0.5 * pausa, 1.5 * pausa))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:5000")
    ap.add_argument("--duracion", type=int, default=18, help="segundos de ráfaga")
    ap.add_argument("--tarjetas", type=int, default=10, help="tarjetas distintas a reutilizar")
    ap.add_argument("--viajes", type=int, default=40)
    ap.add_argument("--hilos", type=int, default=20, help="'usuarios' concurrentes del cliente")
    ap.add_argument("--pausa", type=float, default=1.0, help="pausa media (s) entre solicitudes de cada hilo")
    ap.add_argument("--salida", required=True, help="archivo CSV de salida")
    args = ap.parse_args()

    tarjetas = [f"{1000 + i}" for i in range(args.tarjetas)]
    resultados = []
    lock = threading.Lock()

    fin = time.time() + args.duracion
    hilos = [
        threading.Thread(
            target=worker,
            args=(args.url, tarjetas, args.viajes, args.pausa, fin, resultados, lock),
        )
        for _ in range(args.hilos)
    ]

    print(f"[client] disparando ráfaga durante {args.duracion}s con {args.hilos} hilos, "
          f"{args.tarjetas} tarjetas distintas...")
    t0 = time.time()
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    t1 = time.time()

    resultados.sort(key=lambda r: r[0])
    with open(args.salida, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_envio", "timestamp_respuesta", "exito", "desde_cache", "id_tarjeta"])
        w.writerows(resultados)

    exitosas = sum(r[2] for r in resultados)
    print(f"[client] {len(resultados)} solicitudes en {t1 - t0:.1f}s "
          f"({exitosas} exitosas) -> {args.salida}")


if __name__ == "__main__":
    main()
