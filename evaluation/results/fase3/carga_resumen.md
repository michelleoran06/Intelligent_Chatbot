# Resumen de pruebas de carga

Latencias en segundos. RNF01: p95 < 2.5 s. Percentiles aproximados a partir de las ventanas de Locust, descartando la rampa de cada escalón.

## Sin límite, sin caché

| Usuarios | Throughput (req/s) | p50 (s) | p95 (s) | Errores | ¿Cumple RNF01? |
|---|---|---|---|---|---|
| 10 | 1.71 | 3.800 | 7.600 | 0.00 % | no |
| 25 | 1.24 | 4.200 | 19.000 | 0.00 % | no |
| 50 | 1.78 | 12.000 | 28.000 | 7.89 % | no |
| 100 | 0.32 | 15.000 | 45.000 | 3.80 % | no |

## Límite 2, sin caché

| Usuarios | Throughput (req/s) | p50 (s) | p95 (s) | Errores | ¿Cumple RNF01? |
|---|---|---|---|---|---|
| 10 | 2.43 | 1.900 | 3.200 | 0.00 % | no |
| 25 | 1.79 | 2.400 | 13.000 | 0.00 % | no |
| 50 | 1.83 | 5.900 | 25.000 | 0.00 % | no |
| 100 | 1.82 | 12.000 | 29.000 | 0.00 % | no |

## Sin límite, con caché

| Usuarios | Throughput (req/s) | p50 (s) | p95 (s) | Errores | ¿Cumple RNF01? |
|---|---|---|---|---|---|
| 10 | 2.30 | 3.600 | 8.100 | 0.00 % | no |
| 25 | 11.79 | 0.017 | 6.400 | 0.00 % | no |
| 50 | 24.88 | 0.015 | 2.900 | 0.00 % | no |
| 100 | 49.34 | 0.013 | 0.115 | 0.00 % | sí |

## Límite 2, con caché

| Usuarios | Throughput (req/s) | p50 (s) | p95 (s) | Errores | ¿Cumple RNF01? |
|---|---|---|---|---|---|
| 10 | 1.03 | 9.000 | 11.000 | 0.00 % | no |
| 25 | 1.75 | 8.700 | 25.000 | 0.00 % | no |
| 50 | 4.98 | 0.180 | 27.000 | 0.00 % | no |
| 100 | 24.85 | 0.180 | 27.000 | 0.00 % | no |
