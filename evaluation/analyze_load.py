"""Resume pruebas de carga de Locust por escalón de usuarios (Tabla 31, Figuras 18 y 19).

Lee los archivos <prefijo>_stats_history.csv que genera Locust con --csv y, para cada escalón
(número de usuarios), descarta los primeros segundos de rampa y calcula:
- throughput medio (peticiones/s);
- latencia p50 y p95 (mediana de los percentiles de ventana que reporta Locust; aproximación);
- tasa de error del escalón.

Uso:
    python evaluation/analyze_load.py evaluation/results/carga_sin_limite evaluation/results/carga_limite_2 \
        --labels "Sin límite" "Límite 2" --out evaluation/results/carga_resumen
"""
import argparse
import csv
import math
import os
from statistics import mean, median

RNF01_SECONDS = 2.5


def to_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def summarize(prefix, ramp_seconds):
    path = prefix if prefix.endswith(".csv") else f"{prefix}_stats_history.csv"
    with open(path, newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("Name") == "Aggregated"]
    steps = {}
    for row in rows:
        users = int(to_float(row.get("User Count")) or 0)
        if users:
            steps.setdefault(users, []).append(row)
    results = []
    for users, items in sorted(steps.items()):
        start = to_float(items[0]["Timestamp"])
        stable = [r for r in items if to_float(r["Timestamp"]) - start >= ramp_seconds] or items
        rps = [to_float(r["Requests/s"]) for r in stable if to_float(r["Requests/s"]) is not None]
        p50 = [to_float(r["50%"]) for r in stable if to_float(r["50%"]) is not None]
        p95 = [to_float(r["95%"]) for r in stable if to_float(r["95%"]) is not None]
        total = (to_float(stable[-1]["Total Request Count"]) or 0) - (to_float(stable[0]["Total Request Count"]) or 0)
        failed = (to_float(stable[-1]["Total Failure Count"]) or 0) - (to_float(stable[0]["Total Failure Count"]) or 0)
        results.append({
            "users": users,
            "throughput_rps": round(mean(rps), 2) if rps else None,
            "p50_s": round(median(p50) / 1000, 3) if p50 else None,
            "p95_s": round(median(p95) / 1000, 3) if p95 else None,
            "error_rate": round(failed / total, 4) if total > 0 else 0.0,
            "requests_in_step": int(total),
        })
    return results


def fmt(value, digits=2):
    return "—" if value is None else f"{value:.{digits}f}"


def main():
    parser = argparse.ArgumentParser(description="Resumen de pruebas de carga por escalón")
    parser.add_argument("prefixes", nargs="+", help="prefijos usados en locust --csv")
    parser.add_argument("--labels", nargs="+", help="nombre de cada escenario")
    parser.add_argument("--ramp-seconds", type=float, default=15.0)
    parser.add_argument("--out", default=os.path.join("evaluation", "results", "carga_resumen"))
    args = parser.parse_args()
    labels = args.labels or [os.path.basename(p) for p in args.prefixes]
    if len(labels) != len(args.prefixes):
        parser.error("--labels debe tener un nombre por cada prefijo")

    scenarios = [(label, summarize(prefix, args.ramp_seconds)) for label, prefix in zip(labels, args.prefixes)]
    lines = ["# Resumen de pruebas de carga", "",
             f"Latencias en segundos. RNF01: p95 < {RNF01_SECONDS} s. Percentiles aproximados a partir de "
             "las ventanas de Locust, descartando la rampa de cada escalón.", ""]
    for label, results in scenarios:
        lines += [f"## {label}", "", "| Usuarios | Throughput (req/s) | p50 (s) | p95 (s) | Errores | ¿Cumple RNF01? |",
                  "|---|---|---|---|---|---|"]
        for r in results:
            ok = "—" if r["p95_s"] is None else ("sí" if r["p95_s"] < RNF01_SECONDS else "no")
            lines.append(f"| {r['users']} | {fmt(r['throughput_rps'])} | {fmt(r['p50_s'], 3)} | {fmt(r['p95_s'], 3)} | "
                         f"{r['error_rate'] * 100:.2f} % | {ok} |")
        lines.append("")
    report = "\n".join(lines)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(f"{args.out}.md", "w", encoding="utf-8") as handle:
        handle.write(report)
    print(report)

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib no está instalado; se omiten las gráficas.")
        return
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    for label, results in scenarios:
        users = [r["users"] for r in results]
        ax1.plot(users, [r["p95_s"] for r in results], marker="o", label=f"p95 · {label}")
        ax1.plot(users, [r["p50_s"] for r in results], marker=".", linestyle=":", label=f"p50 · {label}")
        ax2.plot(users, [r["throughput_rps"] for r in results], marker="o", label=label)
    ax1.axhline(RNF01_SECONDS, color="red", linestyle="--", linewidth=1, label="Objetivo RNF01 (2.5 s)")
    ax1.set_xlabel("Usuarios concurrentes")
    ax1.set_ylabel("Tiempo de respuesta (s)")
    ax1.set_title("Latencia frente a usuarios concurrentes")
    ax1.grid(alpha=0.3)
    ax1.legend(fontsize=8)
    ax2.set_xlabel("Usuarios concurrentes")
    ax2.set_ylabel("Peticiones por segundo")
    ax2.set_title("Throughput frente a usuarios concurrentes")
    ax2.grid(alpha=0.3)
    ax2.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(f"{args.out}.png", dpi=150)
    print(f"\nGráfica guardada en {args.out}.png")


if __name__ == "__main__":
    main()
