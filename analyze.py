"""
Calcula, a partir del CSV del cliente: latencia (prom/p95), throughput,
jitter, % de eventos no procesados y % de respuestas servidas desde caché.

Uso:
    python analyze.py e0.csv e1.csv e2.csv
"""

import csv
import sys
import statistics


def analizar(path):
    filas = []
    with open(path) as f:
        for r in csv.DictReader(f):
            filas.append({
                "t_envio": float(r["timestamp_envio"]),
                "t_resp": float(r["timestamp_respuesta"]),
                "exito": int(r["exito"]),
                "desde_cache": int(r["desde_cache"]),
            })

    if not filas:
        print(f"{path}: vacío")
        return

    filas.sort(key=lambda r: r["t_envio"])
    total = len(filas)
    exitosas = [r for r in filas if r["exito"] == 1]
    n_exitosas = len(exitosas)

    # duración total del experimento: primer envío -> última respuesta
    duracion = max(max(r["t_resp"] for r in filas) - filas[0]["t_envio"], 1e-9)

    latencias = [r["t_resp"] - r["t_envio"] for r in exitosas]
    latencia_prom = statistics.mean(latencias) if latencias else 0
    latencia_p95 = statistics.quantiles(latencias, n=100)[94] if len(latencias) >= 20 else (
        max(latencias) if latencias else 0
    )

    jitters = [abs(latencias[i] - latencias[i - 1]) for i in range(1, len(latencias))]
    jitter_prom = statistics.mean(jitters) if jitters else 0

    throughput = n_exitosas / duracion
    pct_no_procesadas = 100 * (total - n_exitosas) / total
    pct_desde_cache = 100 * sum(r["desde_cache"] for r in exitosas) / n_exitosas if n_exitosas else 0

    lat_hit = [r["t_resp"] - r["t_envio"] for r in exitosas if r["desde_cache"]]
    lat_miss = [r["t_resp"] - r["t_envio"] for r in exitosas if not r["desde_cache"]]

    print(f"\n=== {path} ===")
    print(f"  Solicitudes totales:      {total}")
    print(f"  Exitosas:                 {n_exitosas}")
    print(f"  Latencia promedio:        {latencia_prom * 1000:.1f} ms")
    print(f"  Latencia p95:             {latencia_p95 * 1000:.1f} ms")
    print(f"  Throughput:               {throughput:.2f} req/s")
    print(f"  Jitter promedio:          {jitter_prom * 1000:.1f} ms")
    print(f"  % no procesadas:          {pct_no_procesadas:.1f} %")
    print(f"  % servidas desde caché:   {pct_desde_cache:.1f} %")
    if lat_hit:
        print(f"  Latencia prom. (caché):   {statistics.mean(lat_hit) * 1000:.1f} ms  (n={len(lat_hit)})")
    if lat_miss:
        print(f"  Latencia prom. (cálculo): {statistics.mean(lat_miss) * 1000:.1f} ms  (n={len(lat_miss)})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python analyze.py archivo1.csv [archivo2.csv ...]")
        sys.exit(1)
    for path in sys.argv[1:]:
        analizar(path)
