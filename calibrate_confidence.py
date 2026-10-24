"""Validación del componente de IA y calibración del umbral y del divisor (Sección 16).

Usa el conjunto etiquetado evaluation/test_set.csv (consulta, entrada esperada o ESCALATE,
categoría) y calcula, con "respondido automáticamente" como clase positiva:

- Matriz de confusión: TP (responde y acierta), FP (responde mal o responde algo fuera de
  alcance), FN (escala algo que sí sabía), TN (escala algo fuera de alcance).
- Exactitud, precisión, recall, F1, tasa de escalamiento y hit rate @1 / @3.
- Barrido del umbral (Tabla 21) y del divisor (Tabla 22).
- Recomendación: mayor recall con precisión >= objetivo.

Uso:
    python calibrate_confidence.py
    python calibrate_confidence.py --precision-target 0.9 --no-plot
    python calibrate_confidence.py --embedding-model paraphrase-multilingual-MiniLM-L12-v2 --rejection
"""
import argparse
import csv
import os
import tempfile
from collections import defaultdict
from typing import Dict, List

import config
from knowledge_base import DEFAULT_ENTRIES, REJECTION_EXAMPLES
from nlp_engine import NLPEngine

ESCALATE = "ESCALATE"
THRESHOLDS = [0.60, 0.65, 0.70, 0.75, 0.80]
DIVISORS = [2.0, 2.5, 3.0]
BASE_THRESHOLD = 0.70
BASE_DIVISOR = 2.5


class CachedStore:
    """Envuelve el vector store para consultar ChromaDB una sola vez por pregunta."""

    def __init__(self, store):
        self.store = store
        self._memo = {}

    def query(self, text, n_results=10):
        key = (text, n_results)
        if key not in self._memo:
            self._memo[key] = self.store.query(text, n_results)
        return self._memo[key]


def load_test_set(path: str) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row.get("query")]


def build_engine(store, threshold: float, divisor: float) -> NLPEngine:
    engine = NLPEngine(
        store=store,
        confidence_threshold=threshold,
        divisor=divisor,
        keyword_confidence=config.KEYWORD_CONFIDENCE,
        min_keyword_matches=config.MIN_KEYWORD_MATCHES,
        n_results=config.SEMANTIC_RESULTS,
        cache_size=0,
    )
    engine.set_knowledge_base(DEFAULT_ENTRIES)
    return engine


def evaluate(engine: NLPEngine, cases: List[dict]) -> Dict:
    counts = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    hits_at_1 = hits_at_3 = answerable = 0
    details = []
    for case in cases:
        expected = case["expected"]
        result = engine.retrieve(case["query"])
        answered = result.confidence >= engine.confidence_threshold
        expected_answerable = expected != ESCALATE
        if answered:
            outcome = "TP" if expected_answerable and result.kb_id == expected else "FP"
        else:
            outcome = "FN" if expected_answerable else "TN"
        counts[outcome] += 1
        if expected_answerable:
            answerable += 1
            hits_at_1 += expected in result.candidates[:1]
            hits_at_3 += expected in result.candidates[:3]
        details.append({
            "query": case["query"],
            "category": case.get("category", ""),
            "expected": expected,
            "predicted": result.kb_id or "",
            "method": result.method,
            "confidence": result.confidence,
            "distance": "" if result.distance is None else result.distance,
            "decision": "answer" if answered else "escalate",
            "outcome": outcome,
        })

    tp, fp, fn, tn = counts["TP"], counts["FP"], counts["FN"], counts["TN"]
    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        **counts,
        "N": total,
        "accuracy": (tp + tn) / total if total else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "escalation_rate": (fn + tn) / total if total else 0.0,
        "hit_at_1": hits_at_1 / answerable if answerable else 0.0,
        "hit_at_3": hits_at_3 / answerable if answerable else 0.0,
        "details": details,
    }


def print_confusion(metrics: Dict) -> None:
    print("\nMatriz de confusión (umbral 0.70, divisor 2.5) — Tabla 19")
    print(f"{'':28}{'Esperado: respondible':>24}{'Esperado: ESCALATE':>22}")
    print(f"{'Sistema responde (S>=0.70)':28}{'TP = ' + str(metrics['TP']):>24}{'FP = ' + str(metrics['FP']):>22}")
    print(f"{'Sistema escala (S<0.70)':28}{'FN = ' + str(metrics['FN']):>24}{'TN = ' + str(metrics['TN']):>22}")


def print_metrics(metrics: Dict) -> None:
    print("\nMétricas de validación — Tabla 20")
    for label, key in [("Exactitud", "accuracy"), ("Precisión", "precision"), ("Recall", "recall"),
                       ("F1-score", "f1"), ("Tasa de escalamiento", "escalation_rate"),
                       ("Hit rate @1", "hit_at_1"), ("Hit rate @3", "hit_at_3")]:
        print(f"  {label:22} {metrics[key]:.3f}")


def print_failures(metrics: Dict) -> None:
    failures = [d for d in metrics["details"] if d["outcome"] in ("FP", "FN")]
    print(f"\nCasos fallidos para el análisis de errores (Sección 16.5): {len(failures)}")
    by_category = defaultdict(list)
    for detail in failures:
        by_category[detail["category"]].append(detail)
    for category, items in sorted(by_category.items()):
        print(f"  [{category}]")
        for d in items:
            print(f"    {d['outcome']} | S={d['confidence']:.3f} | {d['method']:8} | esperado={d['expected']:13} "
                  f"| predicho={d['predicted'] or '-':13} | {d['query']}")


def write_csv(path: str, rows: List[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_threshold_sweep(rows: List[dict], path: str) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib no está instalado; se omite la gráfica.")
        return
    thresholds = [r["threshold"] for r in rows]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for key, label in [("precision", "Precisión"), ("recall", "Recall"), ("f1", "F1-score")]:
        ax.plot(thresholds, [r[key] for r in rows], marker="o", label=label)
    ax.axvline(BASE_THRESHOLD, color="gray", linestyle="--", linewidth=1, label="Umbral actual (0.70)")
    ax.set_xlabel("Umbral de confianza")
    ax.set_ylabel("Valor")
    ax.set_ylim(0, 1.05)
    ax.set_title("Precisión, recall y F1 según el umbral (divisor 2.5)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"Gráfica guardada en {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validación del componente de IA")
    parser.add_argument("--test-set", default=os.path.join("evaluation", "test_set.csv"))
    parser.add_argument("--out-dir", default=os.path.join("evaluation", "results"))
    parser.add_argument("--precision-target", type=float, default=0.90)
    parser.add_argument("--no-plot", action="store_true")
    parser.add_argument("--embedding-model", default=config.EMBEDDING_MODEL,
                        help='modelo de embeddings ("default" = all-MiniLM-L6-v2)')
    parser.add_argument("--rejection", action="store_true", default=config.USE_REJECTION_EXAMPLES,
                        help="indexar los ejemplos de rechazo")
    args = parser.parse_args()

    from vector_store import ChromaVectorStore

    os.makedirs(args.out_dir, exist_ok=True)
    cases = load_test_set(args.test_set)
    print(f"Conjunto de prueba: {len(cases)} consultas ({args.test_set})")
    print(f"Modelo de embeddings: {args.embedding_model} | ejemplos de rechazo: {'sí' if args.rejection else 'no'}")
    print("Construyendo el índice vectorial (la primera vez se descarga el modelo)...")
    store = ChromaVectorStore(path=tempfile.mkdtemp(prefix="calibration_chroma_"), collection_name="calibration_kb",
                              embedding_model=args.embedding_model,
                              rejection_examples=REJECTION_EXAMPLES if args.rejection else [])
    store.rebuild(DEFAULT_ENTRIES)
    cached = CachedStore(store)

    baseline = evaluate(build_engine(cached, BASE_THRESHOLD, BASE_DIVISOR), cases)
    print_confusion(baseline)
    print_metrics(baseline)
    print_failures(baseline)
    write_csv(os.path.join(args.out_dir, "baseline_details.csv"), baseline["details"])

    print("\nBarrido del umbral (divisor 2.5) — Tabla 21")
    print(f"  {'Umbral':>7} {'Precisión':>10} {'Recall':>8} {'F1':>7} {'Escalamiento':>13}")
    threshold_rows = []
    for threshold in THRESHOLDS:
        m = evaluate(build_engine(cached, threshold, BASE_DIVISOR), cases)
        threshold_rows.append({"threshold": threshold, "precision": m["precision"], "recall": m["recall"],
                               "f1": m["f1"], "escalation_rate": m["escalation_rate"]})
        print(f"  {threshold:>7.2f} {m['precision']:>10.3f} {m['recall']:>8.3f} {m['f1']:>7.3f} "
              f"{m['escalation_rate']:>13.3f}")
    write_csv(os.path.join(args.out_dir, "threshold_sweep.csv"), threshold_rows)

    print("\nBarrido del divisor (umbral 0.70) — Tabla 22")
    print(f"  {'Divisor':>7} {'d aceptada <=':>14} {'Precisión':>10} {'Recall':>8} {'F1':>7}")
    divisor_rows = []
    for divisor in DIVISORS:
        m = evaluate(build_engine(cached, BASE_THRESHOLD, divisor), cases)
        accepted = (1 - BASE_THRESHOLD) * divisor
        divisor_rows.append({"divisor": divisor, "max_distance": round(accepted, 3), "precision": m["precision"],
                             "recall": m["recall"], "f1": m["f1"]})
        print(f"  {divisor:>7.1f} {accepted:>14.2f} {m['precision']:>10.3f} {m['recall']:>8.3f} {m['f1']:>7.3f}")
    write_csv(os.path.join(args.out_dir, "divisor_sweep.csv"), divisor_rows)

    print(f"\nSelección: mayor recall con precisión >= {args.precision_target:.2f}")
    candidates = []
    for divisor in DIVISORS:
        for threshold in THRESHOLDS:
            m = evaluate(build_engine(cached, threshold, divisor), cases)
            if m["precision"] >= args.precision_target:
                candidates.append((m["recall"], m["f1"], threshold, divisor, m["precision"]))
    if candidates:
        recall, f1, threshold, divisor, precision = max(candidates)
        print(f"  Recomendado: umbral {threshold:.2f}, divisor {divisor:.1f} "
              f"(precisión {precision:.3f}, recall {recall:.3f}, F1 {f1:.3f})")
        if (threshold, divisor) != (BASE_THRESHOLD, BASE_DIVISOR):
            print("  Si se adopta, hay que cambiarlo en config.py, los requisitos, los diagramas y el documento.")
    else:
        print("  Ninguna combinación alcanza la precisión objetivo; revisar el análisis de errores.")

    if not args.no_plot:
        plot_threshold_sweep(threshold_rows, os.path.join(args.out_dir, "precision_recall_threshold.png"))
    print(f"\nResultados guardados en {args.out_dir}/")


if __name__ == "__main__":
    main()
