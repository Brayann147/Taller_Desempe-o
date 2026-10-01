# Taller: Concurrencia + Caché — RECAUDO-T

## Cómo levantarlo

```bash
pip install -r requirements.txt
python run_experimentos.py
```

(`run_experimentos.py` funciona igual en Windows, Mac o Linux. Si estás en
Mac/Linux y prefieres el script de bash, también está `run_experimentos.sh`.)

Esto corre automáticamente E0, E1 y E2 (E2 dos veces: `e2.csv` y `e2b.csv`),
genera `e0.csv`, `e1.csv`, `e2.csv`, `e2b.csv` y al final imprime la tabla de métricas de los tres.

Si prefieres correr un experimento a la mano:

**Windows (PowerShell):**
```powershell
# Terminal 1
$env:WORKERS="1"; $env:CACHE_ENABLED="false"; python server.py

# Terminal 2
python client.py --duracion 18 --tarjetas 10 --hilos 30 --salida e0.csv
```

**Mac/Linux:**
```bash
# Terminal 1
WORKERS=1 CACHE_ENABLED=false python3 server.py

# Terminal 2
python3 client.py --duracion 18 --tarjetas 10 --hilos 30 --salida e0.csv
```

Cambia `WORKERS` y `CACHE_ENABLED` según el experimento (ver tabla abajo)
y luego corre `python analyze.py e0.csv e1.csv e2.csv e2b.csv` para ver las métricas.

| Experimento | WORKERS | CACHE_ENABLED |
|---|---|---|
| E0 (línea base) | 1 | false |
| E1 (concurrencia) | 8 | false |
| E2 (concurrencia + caché), 2 corridas | 8 | true |

Puedes verificar en vivo que W y el caché están activos consultando
`GET /config` mientras el servidor corre.

## Cómo quedó resuelto cada requisito

- **R1 (concurrencia):** el servidor no calcula nada en el hilo que recibe
  la petición HTTP. Cada solicitud se entrega a un `ThreadPoolExecutor` de
  tamaño `W` (variable de entorno `WORKERS`), y el hilo HTTP simplemente
  espera el resultado. Así, W controla de verdad cuántos cálculos corren
  al mismo tiempo — no es Flask quien decide eso.
- **Caché HIT sin cola:** la ruta `/resumen` consulta el caché *antes* de
  entregar nada al pool; un HIT responde de inmediato y solo los MISS se
  encolan en los W trabajadores.
- **R2 (caché):** un diccionario en memoria, protegido con un `Lock`,
  indexado por `(id_tarjeta, viajes)`. Si `CACHE_ENABLED=true` y la clave
  ya existe, se responde de inmediato con `desde_cache=true` sin pasar por
  el cálculo costoso.
- El cálculo costoso (`calcular_resumen`) siempre duerme entre 150 y 250 ms,
  como pide el taller, para que los experimentos sean comparables.

## Tabla de métricas

Cliente: 30 hilos ("usuarios"), 10 tarjetas, ráfaga de 18 s, pausa media de
1 s entre consultas de cada usuario, timeout de 3 s. Cada número sale del CSV
indicado (`python analyze.py e0.csv e1.csv e2.csv e2b.csv`).

| Métrica | E0 (W=1, sin caché) `e0.csv` | E1 (W=8, sin caché) `e1.csv` | E2 (W=8 + caché) `e2.csv` | E2, 2.ª corrida `e2b.csv` |
|---|---|---|---|---|
| Solicitudes totales | 156 | 456 | 532 | 527 |
| Latencia promedio | 1527.5 ms | 240.1 ms | 39.2 ms | 39.8 ms |
| Latencia p95 | 2864.0 ms | 372.3 ms | 232.2 ms | 206.5 ms |
| Throughput (req/s) | 0.67 | 24.99 | 29.60 | 29.40 |
| Jitter promedio | 822.9 ms | 42.0 ms | 13.8 ms | 14.9 ms |
| No procesadas (>3 s) | 91.0 % | 0.0 % | 0.0 % | 0.0 % |
| % desde caché | 0 % | 0 % | 94.4 % | 94.3 % |
| Latencia prom. respuestas de caché | — | — | 12.6 ms | 14.0 ms |
| Latencia prom. respuestas calculadas | 1527.5 ms | 240.1 ms | 484.0 ms | 468.5 ms |

Notas: en E0 el throughput es tan bajo porque el servidor sigue calculando
las solicitudes que el cliente ya abandonó por timeout, así que la cola nunca
se vacía y casi todo lo que llega excede los 3 s. Las latencias de E0 y E1
solo consideran solicitudes exitosas. En E2 las respuestas calculadas son
lentas (~470-480 ms) porque son los primeros MISS de las 10 tarjetas, cuando
los 30 usuarios llegan a la vez y hacen cola.

## Preguntas de análisis

**1. ¿Por qué aumentar el número de trabajadores mejora el throughput aunque
cada cálculo individual siga tardando lo mismo?**

Porque el throughput no depende de cuánto tarda *una* solicitud, sino de
cuántas se pueden estar procesando *al mismo tiempo*. Con W=1, el servidor
es como una sola caja registradora: aunque cada cliente se demore lo mismo
en pagar, solo se atiende a uno a la vez y la fila crece. Con W=8 hay ocho
cajas abiertas: el tiempo por cliente no cambia, pero en el mismo minuto
se atienden ocho veces más personas. El throughput crece porque se
aprovecha el tiempo en que unos trabajadores están calculando mientras
otros ya terminaron y están listos para el siguiente.

**2. En E1, ¿bajó la latencia promedio de cada solicitud individual, o solo
mejoró cuántas solicitudes se atendieron en total?**

En nuestras mediciones la latencia promedio bajó de 1527 ms (E0) a 240 ms
(E1) y el throughput subió de 0.67 a 24.99 req/s. Son dos efectos distintos
y hay que separarlos. La latencia de *una*
solicitud ya en ejecución no baja: el cálculo sigue tardando entre 150 y
250 ms porque esa parte no cambió. Lo que sí baja drásticamente es el
**tiempo de espera en cola** antes de empezar a procesarse: con W=1 la
solicitud 50 espera a que terminen las 49 anteriores; con W=8 solo espera
a que se libere uno de los ocho trabajadores. Como la latencia medida por
el cliente incluye espera + cálculo, la latencia promedio total sí baja
mucho en E1 frente a E0 — pero esa mejora viene de reducir la espera en
cola, no de que el cálculo en sí se haya vuelto más rápido.

**3. En E2, ¿qué porcentaje de solicitudes provino del caché? ¿Qué pasaría
si el cliente usara 1000 tarjetas distintas en vez de 10? ¿Sigue siendo
útil el caché?**

En E2, 94.4 % de las respuestas vino del caché en `e2.csv` y 94.3 % en
`e2b.csv`; las respuestas de caché tardaron ~13 ms en promedio contra ~470-480
ms las que requirieron cálculo. Medido con 1000 tarjetas distintas (`e2_1000tarjetas.csv`, W=8 con
caché, 463 solicitudes): solo 16.0 % vino del caché y la latencia promedio
subió a 199.8 ms (caché 10.5 ms, calculadas 235.8 ms). Con solo 10
tarjetas reutilizadas en una ráfaga de cientos de solicitudes, la enorme
mayoría termina repitiendo una tarjeta ya calculada, por eso el porcentaje
desde caché es tan alto. Si en cambio el cliente usara 1000 tarjetas
distintas, la probabilidad de que dos solicitudes pidan exactamente la
misma tarjeta en la misma ráfaga baja mucho, así que el porcentaje de
aciertos de caché caería fuerte (posiblemente cerca de 0% si nadie repite
tarjeta). El caché seguiría siendo *correcto*, pero dejaría de ser útil
para *esa* carga, porque su beneficio depende de que existan consultas
repetidas — no ayuda con "primera vez que se pregunta algo", solo con
"me lo volvieron a preguntar".

**4. Si el servidor aumentara indefinidamente el número de trabajadores,
¿qué límite físico o técnico lo detendría?**

Tarde o temprano se topa con los recursos reales de la máquina: el número
de núcleos de CPU (más hilos que núcleos, y en algún punto empiezan a
competir por tiempo de procesador en vez de trabajar en paralelo de
verdad), la memoria disponible (cada hilo consume su propia pila y
estructuras), y si el cálculo dependiera de una base de datos externa,
también el límite de conexiones concurrentes que esa base soporte. Este
es justo el punto donde la táctica "Introducir concurrencia" deja de
alcanzar y hay que recurrir a la táctica **"Aumentar los recursos"** del
árbol: agregar más máquinas (más CPU/memoria física), no solo más hilos
dentro de la misma máquina.

**5. El caché evita repetir el cálculo, pero ¿qué pasa si el usuario
realiza un nuevo viaje después de que su resumen quedó en caché?**

Aparece un problema de **datos obsoletos (staleness)**: el caché seguiría
devolviendo el resumen viejo, sin el viaje nuevo, porque nada le avisó que
la información cambió — el servidor asumió que lo que ya calculó sigue
siendo válido para siempre. Para resolverlo hay que agregar algún
mecanismo de **invalidación o expiración de caché**: por ejemplo, ponerle
un tiempo de vida (TTL) a cada entrada para que expire sola después de
unos minutos, o, mejor aún, invalidar explícitamente la entrada de ese
usuario en el momento en que se registra un viaje nuevo, para que la
siguiente consulta fuerce un recálculo con los datos actualizados.
