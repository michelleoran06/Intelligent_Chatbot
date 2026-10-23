"""Experimento de calidad del componente de IA (Fase 2, Secciones 16.4 y 16.5).

Compara cuatro configuraciones con el mismo conjunto de prueba:

    A: modelo actual (all-MiniLM-L6-v2)       sin ejemplos de rechazo  (línea base)
    B: modelo multilingüe                       sin ejemplos de rechazo
    C: modelo actual                            con ejemplos de rechazo
    D: modelo multilingüe                       con ejemplos de rechazo

Para cada una mide:
- métricas con la configuración vigente (umbral 0.70, divisor 2.5);
- la mejor combinación de umbral y divisor con precisión >= objetivo (mayor recall);
- memoria del proceso (RSS) y latencia por consulta sin caché.

Cada configuración corre en un proceso separado para que la memoria de un modelo no se mezcle
con la de otro.

AVISO: el umbral y el divisor se eligen sobre el mismo conjunto con el que se miden, así que las
métricas de la "mejor combinación" son optimistas. El resultado final debe confirmarse con un
conjunto de validación independiente (evaluation/validation_set.csv) escrito por el equipo:

    python experiment_quality.py --final evaluation/validation_set.csv --config D --threshold 0.70 --divisor 2.5

Uso:
    pip install -r requirements-experiment.txt
    python experiment_quality.py
    python experiment_quality.py --configs A C        # solo el modelo actual
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import time

from calibrate_confidence import CachedStore, build_engine, evaluate, load_test_set
from knowledge_base import DEFAULT_ENTRIES, REJECTION_EXAMPLES

DEFAULT_MULTILINGUAL = "paraphrase-multilingual-MiniLM-L12-v2"
GRID_THRESHOLDS = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]
GRID_DIVISORS = [1.5, 2.0, 2.5, 3.0]
CURRENT = (0.70, 2.5)
RENDER_LIMIT_MB = 512
SAFE_MEMORY_MB = 450  # margen para el resto del backend dentro del plan de Render


def config_table(multilingual_model):
    return {
        "A": {"model": "default", "rejection": False},
        "B": {"model": multilingual_model, "rejection": False},
        "C": {"model": "default", "rejection": True},
        "D": {"model": multilingual_model, "rejection": True},
    }


def rss_mb():
    try:
        import psutil
    except ImportError:
        return None
    return round(psutil.Process(os.getpid()).memory_info().rss / 10**6, 1)


class TimedStore:
    """Mide cuánto tarda cada consulta real a ChromaDB (cálculo del embedding + búsqueda)."""

    def __init__(self, store):
        self.store = store
        self.latencies_ms = []

    def query(self, text, n_results=20):
        started = time.perf_counter()
        hits = self.store.query(text, n_results)
        self.latencies_ms.append((time.perf_counter() - started) * 1000)
        return hits


def summarize(metrics):
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in metrics.items() if k != "details"}


def run_worker(name, cfg, test_set, precision_target, out_path):
    """Corre una configuración completa y escribe el resultado en JSON."""
    from vector_store import ChromaVectorStore

    cases = load_test_set(test_set)
    rss_start = rss_mb()
    started = time.perf_counter()
    store = ChromaVectorStore(
        path=tempfile.mkdtemp(prefix=f"experiment_{name}_"),
        collection_name=f"experiment_{name.lower()}",
        embedding_model=cfg["model"],
        rejection_examples=REJECTION_EXAMPLES if cfg["rejection"] else [],
    )
    documents = store.rebuild(DEFAULT_ENTRIES)
    build_seconds = time.perf_counter() - started

    timed = TimedStore(store)
    cached = CachedStore(timed)
    current = evaluate(build_engine(cached, *CURRENT), cases)  # primera pasada: consultas reales medidas

    grid = []
    for divisor in GRID_DIVISORS:
        for threshold in GRID_THRESHOLDS:
            metrics = evaluate(build_engine(cached, threshold, divisor), cases)
            grid.append({"threshold": threshold, "divisor": divisor, **summarize(metrics)})

    eligible = [g for g in grid if g["precision"] >= precision_target]
    best = max(eligible, key=lambda g: (g["recall"], g["f1"], g["threshold"])) if eligible else None

    latencies = sorted(timed.latencies_ms)
    p95_index = max(0, int(round(0.95 * len(latencies))) - 1)
    result = {
        "config": name,
        "model": cfg["model"],
        "rejection": cfg["rejection"],
        "documents_indexed": documents,
        "build_seconds": round(build_seconds, 1),
        "rss_start_mb": rss_start,
        "rss_end_mb": rss_mb(),
        "query_latency_mean_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "query_latency_p95_ms": round(latencies[p95_index], 1) if latencies else None,
        "current": summarize(current),
        "best": best,
        "failures_current": [d for d in current["details"] if d["outcome"] in ("FP", "FN")],
        "grid": grid,
    }
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)


def run_final(args):
    """Medición final con el conjunto de validación independiente (no se ajusta nada)."""
    from vector_store import ChromaVectorStore

    cfg = config_table(args.multilingual_model)[args.config]
    cases = load_test_set(args.final)
    store = ChromaVectorStore(
        path=tempfile.mkdtemp(prefix="final_validation_"), collection_name="final_validation",
        embedding_model=cfg["model"], rejection_examples=REJECTION_EXAMPLES if cfg["rejection"] else [],
    )
    store.rebuild(DEFAULT_ENTRIES)
    metrics = evaluate(build_engine(store, args.threshold, args.divisor), cases)
    print(f"Validación final | configuración {args.config} ({cfg['model']}, rechazo={cfg['rejection']}) "
          f"| umbral {args.threshold} | divisor {args.divisor} | {len(cases)} consultas")
    print(f"TP={metrics['TP']} FP={metrics['FP']} FN={metrics['FN']} TN={metrics['TN']}")
    for key in ("accuracy", "precision", "recall", "f1", "escalation_rate", "hit_at_1", "hit_at_3"):
        print(f"  {key:16} {metrics[key]:.3f}")
    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir, f"validacion_final_{args.config}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"config": args.config, **cfg, "threshold": args.threshold, "divisor": args.divisor,
                   **summarize(metrics), "details": metrics["details"]}, handle, ensure_ascii=False, indent=2)
    print(f"Resultado guardado en {path}")


def fmt(value, digits=3):
    return "—" if value is None else f"{value:.{digits}f}"


def main():
    parser = argparse.ArgumentParser(description="Experimento comparativo de calidad del componente de IA")
    parser.add_argument("--test-set", default=os.path.join("evaluation", "test_set.csv"))
    parser.add_argument("--out-dir", default=os.path.join("evaluation", "results", "experimento_calidad"))
    parser.add_argument("--precision-target", type=float, default=0.90)
    parser.add_argument("--multilingual-model", default=DEFAULT_MULTILINGUAL)
    parser.add_argument("--configs", nargs="+", default=["A", "B", "C", "D"])
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--worker-out", help=argparse.SUPPRESS)
    parser.add_argument("--final", help="conjunto de validación independiente para la medición final")
    parser.add_argument("--config", default="A", help="configuración para --final")
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--divisor", type=float, default=2.5)
    args = parser.parse_args()

    configs = config_table(args.multilingual_model)
    if args.worker:
        run_worker(args.worker, configs[args.worker], args.test_set, args.precision_target, args.worker_out)
        return
    if args.final:
        run_final(args)
        return

    os.makedirs(args.out_dir, exist_ok=True)
    results = []
    for name in args.configs:
        cfg = configs[name]
        print(f"\n=== Configuración {name}: modelo={cfg['model']} | rechazo={'sí' if cfg['rejection'] else 'no'} ===")
        out_path = os.path.join(args.out_dir, f"config_{name}.json")
        command = [sys.executable, os.path.abspath(__file__), "--worker", name, "--worker-out", out_path,
                   "--test-set", args.test_set, "--precision-target", str(args.precision_target),
                   "--multilingual-model", args.multilingual_model]
        completed = subprocess.run(command)
        if completed.returncode != 0 or not os.path.exists(out_path):
            print(f"La configuración {name} falló (código {completed.returncode}); se omite.")
            continue
        with open(out_path, encoding="utf-8") as handle:
            results.append(json.load(handle))

    if not results:
        print("No hay resultados.")
        return

    lines = [
        "# Experimento de calidad del componente de IA",
        "",
        f"Conjunto: `{args.test_set}` | Precisión objetivo: {args.precision_target:.2f}",
        "",
        "## Con la configuración vigente (umbral 0.70, divisor 2.5)",
        "",
        "| Config. | Modelo | Rechazo | TP | FP | FN | TN | Exactitud | Precisión | Recall | F1 | Escalamiento |"
        " Hit@1 | Hit@3 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        c = r["current"]
        lines.append(f"| {r['config']} | {r['model']} | {'sí' if r['rejection'] else 'no'} | {c['TP']} | {c['FP']} | "
                     f"{c['FN']} | {c['TN']} | {fmt(c['accuracy'])} | {fmt(c['precision'])} | {fmt(c['recall'])} | "
                     f"{fmt(c['f1'])} | {fmt(c['escalation_rate'])} | {fmt(c['hit_at_1'])} | {fmt(c['hit_at_3'])} |")
    lines += [
        "",
        f"## Mejor combinación con precisión ≥ {args.precision_target:.2f} (optimista: ajustada sobre el mismo conjunto)",
        "",
        "| Config. | Umbral | Divisor | Precisión | Recall | F1 | Escalamiento |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        b = r["best"]
        if b:
            lines.append(f"| {r['config']} | {b['threshold']:.2f} | {b['divisor']:.1f} | {fmt(b['precision'])} | "
                         f"{fmt(b['recall'])} | {fmt(b['f1'])} | {fmt(b['escalation_rate'])} |")
        else:
            lines.append(f"| {r['config']} | — | — | no alcanza la precisión objetivo | | | |")
    lines += [
        "",
        "## Recursos",
        "",
        "| Config. | Documentos | Construcción del índice (s) | RSS final (MB) | Latencia media (ms) | Latencia p95 (ms) |"
        " ¿Cabe en Render? |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        fits = "—" if r["rss_end_mb"] is None else ("sí" if r["rss_end_mb"] <= SAFE_MEMORY_MB else "no")
        lines.append(f"| {r['config']} | {r['documents_indexed']} | {r['build_seconds']} | {r['rss_end_mb']} | "
                     f"{r['query_latency_mean_ms']} | {r['query_latency_p95_ms']} | {fits} |")

    candidates = [r for r in results if r["best"] and (r["rss_end_mb"] is None or r["rss_end_mb"] <= SAFE_MEMORY_MB)]
    lines += ["", "## Recomendación automática", ""]
    if candidates:
        winner = max(candidates, key=lambda r: (r["best"]["recall"], r["best"]["f1"]))
        b = winner["best"]
        lines.append(f"Configuración **{winner['config']}** con umbral {b['threshold']:.2f} y divisor {b['divisor']:.1f}: "
                     f"precisión {fmt(b['precision'])}, recall {fmt(b['recall'])}, F1 {fmt(b['f1'])}, "
                     f"RSS {winner['rss_end_mb']} MB. Debe confirmarse con el conjunto de validación independiente.")
    else:
        lines.append("Ninguna configuración alcanza la precisión objetivo dentro del límite de memoria. "
                     "Revisar el análisis de errores antes de decidir.")
    lines += ["", "## Casos fallidos con la configuración vigente", ""]
    for r in results:
        lines.append(f"### Configuración {r['config']} ({len(r['failures_current'])} fallos)")
        lines.append("")
        lines.append("| Resultado | Categoría | S | Método | Esperado | Predicho | Consulta |")
        lines.append("|---|---|---|---|---|---|---|")
        for d in r["failures_current"]:
            lines.append(f"| {d['outcome']} | {d['category']} | {d['confidence']:.3f} | {d['method']} | "
                         f"{d['expected']} | {d['predicted'] or '—'} | {d['query']} |")
        lines.append("")

    report = "\n".join(lines)
    report_path = os.path.join(args.out_dir, "RESULTADOS_EXPERIMENTO.md")
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write(report)

    rows = []
    for r in results:
        for g in r["grid"]:
            rows.append({"config": r["config"], "model": r["model"], "rejection": r["rejection"], **g})
    with open(os.path.join(args.out_dir, "grid_completo.csv"), "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print("\n" + "\n".join(lines[:4 + 4 + len(results)]))
    print(f"\nReporte completo: {report_path}")


if __name__ == "__main__":
    main()
