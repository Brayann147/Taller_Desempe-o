"""
Corre E0, E1 y E2 automáticamente, sin depender de bash (sirve en Windows,
Mac o Linux).

Uso:
    python run_experimentos.py
"""

import os
import subprocess
import sys
import time

DURACION = 18
TARJETAS = 10
HILOS = 30

EXPERIMENTOS = [
    ("e0", "1", "false"),
    ("e1", "8", "false"),
    ("e2", "8", "true"),
    ("e2b", "8", "true"),  # segunda corrida de E2 para confirmar valores
]


def run_experimento(nombre, workers, cache_enabled):
    print(f"\n>>> {nombre} (WORKERS={workers}, CACHE_ENABLED={cache_enabled})")

    env = os.environ.copy()
    env["WORKERS"] = workers
    env["CACHE_ENABLED"] = cache_enabled

    log_path = f"server_{nombre}.log"
    log_file = open(log_path, "w")
    server = subprocess.Popen(
        [sys.executable, "server.py"],
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    time.sleep(1.5)  # darle tiempo al servidor de levantar

    try:
        subprocess.run(
            [
                sys.executable, "client.py",
                "--duracion", str(DURACION),
                "--tarjetas", str(TARJETAS),
                "--hilos", str(HILOS),
                "--salida", f"{nombre}.csv",
            ],
            check=True,
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        log_file.close()

    time.sleep(1)


def main():
    for nombre, workers, cache_enabled in EXPERIMENTOS:
        run_experimento(nombre, workers, cache_enabled)

    print("\n=== RESULTADOS ===")
    subprocess.run([sys.executable, "analyze.py", "e0.csv", "e1.csv", "e2.csv", "e2b.csv"])


if __name__ == "__main__":
    main()
