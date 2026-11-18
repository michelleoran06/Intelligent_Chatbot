"""Revalidación de la Fase 3 (sección 3.4 de PLAN_CORRECCIONES.md).

Corre los conjuntos etiquetados con ChromaDB real y la MISMA decisión que /api/v1/chat
(rag_pipeline.decide). Con "responde la pregunta" como clase positiva, igual que en M3:
TP = responde con la entrada esperada; FP = responde mal o responde algo que debía escalar;
FN = no responde algo que sí sabía; TN = no responde algo fuera de alcance (escala o avisa que es
de otro tema).

Reporta accuracy, precision, recall, F1, matriz de confusión, % escalado al operador, % avisado como
fuera de tema, latencia promedio de Gemini y, para proponer OUT_OF_SCOPE_CONFIDENCE, la confianza
S más baja de las preguntas que sí se pueden responder.

Uso (las keys se leen del entorno o de tu .env; nunca se imprimen):
    python evaluate_rag.py --no-llm                 # solo recuperación (sin gastar cuota)
    python evaluate_rag.py                          # con Gemini (necesita GEMINI_API_KEY_1 y GEMINI_MODEL)
    python evaluate_rag.py --sets evaluation/validation_set.csv
"""
import argparse
import csv
import inspect
import os
import statistics
import tempfile
import time


def load_dotenv(path: str = ".env") -> None:
    """Lee KEY=VALUE de .env sin sobrescribir lo que ya está en el entorno (no imprime nada)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip("'\""))


ESCALATE = "ESCALATE"
# Métricas reportadas en M3; corresponden a validation_set (sin Gemini se reproducen exactas)
M3 = {"accuracy": 0.875, "precision": 0.9545, "recall": 0.84, "f1": 0.8936}
M3_SET = "validation_set"
# Tipo de respuesta que representa cada ruta (E-027). "aclarar" no cuenta como respuesta resuelta.
ROUTE_TIPO = {"llm": "responder", "retrieval": "responder", "clarify": "aclarar",
              "out_of_scope": "fuera_de_tema", "human": "escalar"}
TIPOS = ("responder", "aclarar", "fuera_de_tema", "escalar")


def history_for(case, engine):
    """Turno anterior del caso (columna prev_query); la respuesta del bot es la entrada que recupera."""
    prev = (case.get("prev_query") or "").strip()
    if not prev:
        return []
    result = engine.retrieve(prev)
    return [{"user": prev, "bot": result.answer or ""}]


def evaluate(cases, engine, llm, out_of_scope_confidence, context_k, delay=0.0):
    import rag_pipeline
    from input_validation import normalize_text

    counts = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    routes, tipos = {}, {}
    latencies, details = [], []
    for case in cases:
        query, expected = case["query"], case["expected"]
        history = history_for(case, engine)
        started = time.perf_counter()
        if "history" in inspect.signature(rag_pipeline.decide).parameters:  # versión con contexto (E-027)
            retrieval = engine.retrieve(query, previous=history[-1]["user"] if history else None)
            decision = rag_pipeline.decide(query, normalize_text(query), retrieval, engine, llm,
                                           out_of_scope_confidence, context_k, history=history)
        else:  # versión anterior: cada mensaje se evalúa solo
            retrieval = engine.retrieve(query)
            decision = rag_pipeline.decide(query, normalize_text(query), retrieval, engine, llm,
                                           out_of_scope_confidence, context_k)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if decision.llm_answer is not None and not decision.llm_answer.cached:
            latencies.append(decision.llm_answer.latency_ms)
        if llm is not None and decision.route != "out_of_scope" and delay:
            time.sleep(delay)  # respeta el límite por minuto del plan gratuito
        answerable = expected != ESCALATE
        if decision.answered:
            outcome = "TP" if answerable and decision.kb_id == expected else "FP"
        else:
            outcome = "FN" if answerable else "TN"
        counts[outcome] += 1
        routes[decision.route] = routes.get(decision.route, 0) + 1
        tipo = ROUTE_TIPO.get(decision.route, decision.route)
        tipos[tipo] = tipos.get(tipo, 0) + 1
        details.append({
            "query": query,
            "category": case.get("category", ""),
            "expected": expected,
            "route": decision.route,
            "predicted": decision.kb_id or "",
            "retrieval_kb": retrieval.kb_id or "",
            "retrieval_method": retrieval.method,
            "confidence": retrieval.confidence,
            "llm_key": decision.llm_answer.key_label if decision.llm_answer else "",
            "llm_answer": decision.llm_answer.text if decision.llm_answer else "",
            "decision_ms": round(elapsed_ms, 1),
            "outcome": outcome,
            "expected_tipo": case.get("expected_tipo", ""),
            "tipo": tipo,
            "prev_query": case.get("prev_query", ""),
        })
    tp, fp, fn, tn = counts["TP"], counts["FP"], counts["FN"], counts["TN"]
    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    answerable_conf = [d["confidence"] for d in details if d["expected"] != ESCALATE and d["retrieval_method"] != "rejected"]
    return {
        **counts, "N": total,
        "accuracy": (tp + tn) / total if total else 0.0,
        "precision": precision, "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "escalated_pct": routes.get("human", 0) / total if total else 0.0,
        "out_of_scope_pct": routes.get("out_of_scope", 0) / total if total else 0.0,
        "routes": routes,
        "tipo_pct": {t: tipos.get(t, 0) / total if total else 0.0 for t in TIPOS},
        "tipo_accuracy": _tipo_accuracy(details),
        # con Gemini configurado, "retrieval" significa que ninguna key respondió (cuota, error o timeout)
        "llm_fallbacks": routes.get("retrieval", 0) if llm is not None else 0,
        "llm_latency_avg_ms": statistics.mean(latencies) if latencies else None,
        "llm_latency_p95_ms": sorted(latencies)[int(0.95 * (len(latencies) - 1))] if latencies else None,
        "min_answerable_confidence": min(answerable_conf) if answerable_conf else None,
        "details": details,
    }


def _tipo_accuracy(details):
    labeled = [d for d in details if d["expected_tipo"]]
    if not labeled:
        return None
    return sum(1 for d in labeled if d["tipo"] == d["expected_tipo"]) / len(labeled)


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summary_md(name, m, mode):
    def pct(v):
        return "n/d" if v is None else f"{v * 100:.1f} %"

    def ms(v):
        return "n/d" if v is None else f"{v:,.0f} ms"

    m3 = M3 if name == M3_SET else {key: None for key in M3}

    lines = [
        f"### {name} ({mode}, N = {m['N']})", "",
        "| Métrica | M3 | Fase 3 |", "|---|---|---|",
        f"| Accuracy | {pct(m3['accuracy'])} | {pct(m['accuracy'])} |",
        f"| Precision | {pct(m3['precision'])} | {pct(m['precision'])} |",
        f"| Recall | {pct(m3['recall'])} | {pct(m['recall'])} |",
        f"| F1 | {pct(m3['f1'])} | {pct(m['f1'])} |",
        f"| Escaladas al operador | | {pct(m['escalated_pct'])} |",
        f"| Avisadas como fuera de tema | | {pct(m['out_of_scope_pct'])} |",
        f"| Latencia promedio de Gemini | | {ms(m['llm_latency_avg_ms'])} |",
        f"| Latencia p95 de Gemini | | {ms(m['llm_latency_p95_ms'])} |", "",
        "| Tasa | Valor |", "|---|---|",
        f"| Respondidas (resueltas) | {pct(m['tipo_pct']['responder'])} |",
        f"| Pidió aclarar (no resuelta) | {pct(m['tipo_pct']['aclarar'])} |",
        f"| Fuera de tema | {pct(m['tipo_pct']['fuera_de_tema'])} |",
        f"| **Escaladas al operador (ticket)** | **{pct(m['tipo_pct']['escalar'])}** |",
        f"| Tipo correcto (casos con `expected_tipo`) | {pct(m['tipo_accuracy'])} |", "",
        f"Matriz de confusión: TP = {m['TP']}, FP = {m['FP']}, FN = {m['FN']}, TN = {m['TN']}. "
        f"Rutas: {m['routes']}. Respaldos sin Gemini: {m['llm_fallbacks']}. S mínima de una pregunta respondible: {m['min_answerable_confidence']}.", "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Revalidación de la Fase 3 (RAG con Gemini)")
    parser.add_argument("--sets", nargs="+", default=[os.path.join("evaluation", "validation_set.csv"),
                                                      os.path.join("evaluation", "test_set.csv")])
    parser.add_argument("--no-llm", action="store_true", help="solo recuperación, sin llamar a Gemini")
    parser.add_argument("--out-dir", default=os.path.join("evaluation", "results", "m4_fase3"))
    parser.add_argument("--out-of-scope-confidence", type=float, default=None)
    parser.add_argument("--delay", type=float, default=4.0,
                        help="segundos de pausa después de cada llamada a Gemini (con ~6 s de latencia, <10 por minuto)")
    parser.add_argument("--tag", default=None, help="sufijo de los archivos de salida, p. ej. antes o despues")
    args = parser.parse_args()

    load_dotenv()
    os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="evaluate_rag_"))
    import config
    import llm_client
    from knowledge_base import DEFAULT_ENTRIES, REJECTION_EXAMPLES
    from nlp_engine import NLPEngine
    from vector_store import ChromaVectorStore

    llm = None if args.no_llm else llm_client.from_config()
    mode = "solo recuperación" if llm is None else f"Gemini {config.GEMINI_MODEL}"
    if llm is not None and not llm.available:
        parser.error("Falta GEMINI_API_KEY_1 o GEMINI_MODEL en el entorno o en .env (o usa --no-llm).")
    cut = config.OUT_OF_SCOPE_CONFIDENCE if args.out_of_scope_confidence is None else args.out_of_scope_confidence

    store = ChromaVectorStore(path=tempfile.mkdtemp(prefix="evaluate_rag_chroma_"), collection_name="evaluate_rag",
                              rejection_examples=REJECTION_EXAMPLES if config.USE_REJECTION_EXAMPLES else [])
    store.rebuild(DEFAULT_ENTRIES)
    engine = NLPEngine(store=store, confidence_threshold=config.CONFIDENCE_THRESHOLD, divisor=config.CONFIDENCE_DIVISOR,
                       min_keyword_matches=config.MIN_KEYWORD_MATCHES, n_results=config.SEMANTIC_RESULTS, cache_size=0)
    engine.set_knowledge_base(DEFAULT_ENTRIES)

    os.makedirs(args.out_dir, exist_ok=True)
    tag = args.tag or ("sin_llm" if llm is None else "con_llm")
    report = [f"# Revalidación Fase 3 ({mode})", "",
              f"Umbral {config.CONFIDENCE_THRESHOLD}, divisor {config.CONFIDENCE_DIVISOR}, "
              f"OUT_OF_SCOPE_CONFIDENCE {cut}, contexto top-{config.LLM_CONTEXT_ENTRIES}.", ""]
    for path in args.sets:
        with open(path, newline="", encoding="utf-8") as handle:
            cases = [row for row in csv.DictReader(handle) if row.get("query")]
        metrics = evaluate(cases, engine, llm, cut, config.LLM_CONTEXT_ENTRIES, 0.0 if llm is None else args.delay)
        name = os.path.splitext(os.path.basename(path))[0]
        write_csv(os.path.join(args.out_dir, f"{name}_{tag}.csv"), metrics["details"])
        block = summary_md(name, metrics, mode)
        if metrics["llm_fallbacks"]:
            block += (f"\n> Atención: {metrics['llm_fallbacks']} preguntas usaron el respaldo porque Gemini no respondió "
                      "(cuota o error). Esas no miden a Gemini; sube --delay o corre otro día.\n")
        print(block)
        report.append(block)
        for d in metrics["details"]:
            if d["outcome"] in ("FP", "FN"):
                print(f"  {d['outcome']}: {d['query']} -> {d['route']} {d['predicted'] or '-'} "
                      f"(esperada {d['expected']}, S={d['confidence']})")
            elif d["expected_tipo"] and d["tipo"] != d["expected_tipo"]:
                print(f"  TIPO: {d['query']} -> {d['tipo']} (esperado {d['expected_tipo']})")
    with open(os.path.join(args.out_dir, f"resumen_{tag}.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(report))
    print(f"Resultados en {args.out_dir}/")


if __name__ == "__main__":
    main()
