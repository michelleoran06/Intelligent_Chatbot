"""Perfilado de memoria (Sección 15.4).

Mide la memoria del backend (tracemalloc + memoria RSS del proceso) después de 0, 50, 100 y
500 consultas variadas del conjunto de prueba, y estima el tamaño del historial del chat
para 10, 25 y 50 mensajes. Usa una base de datos y un índice temporales, así que no llena
la cola real del operador.

Uso:
    python memory_test.py
    python memory_test.py --limit-mb 512 --no-plot
"""
import argparse
import csv
import gc
import json
import os
import tempfile
import tracemalloc

_TMP_DIR = tempfile.mkdtemp(prefix="memtest_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/memtest.db"
os.environ["CHROMA_PATH"] = os.path.join(_TMP_DIR, "chroma")

from fastapi.testclient import TestClient  # noqa: E402

from knowledge_base import DEFAULT_ENTRIES  # noqa: E402
from main import app  # noqa: E402

CHECKPOINTS = [0, 50, 100, 500]
SESSION_SIZES = [10, 25, 50]


def rss_mb():
    try:
        import psutil
    except ImportError:
        return None
    return psutil.Process(os.getpid()).memory_info().rss / 10**6


def load_queries(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return [row["query"] for row in csv.DictReader(handle)]


def session_state_size(messages: int) -> float:
    """Tamaño aproximado (KB) del historial que guarda frontend.py en la sesión."""
    answers = [entry["answer"] for entry in DEFAULT_ENTRIES]
    history = []
    for i in range(messages):
        if i % 2 == 0:
            history.append({"role": "user", "content": "¿Cuánto cuestan los chilaquiles con cecina?",
                            "ticket_id": i, "allow_feedback": False})
        else:
            history.append({"role": "assistant", "content": answers[i % len(answers)],
                            "ticket_id": i, "allow_feedback": True})
    return len(json.dumps(history, ensure_ascii=False).encode("utf-8")) / 1024


def main():
    parser = argparse.ArgumentParser(description="Perfilado de memoria del backend")
    parser.add_argument("--test-set", default=os.path.join("evaluation", "test_set.csv"))
    parser.add_argument("--out-dir", default=os.path.join("evaluation", "results"))
    parser.add_argument("--limit-mb", type=float, default=512.0, help="límite de memoria del plan de hosting")
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    queries = load_queries(args.test_set)
    rows = []
    print("Iniciando backend (carga del modelo e índice)...")
    with TestClient(app) as client:
        gc.collect()
        tracemalloc.start()
        processed = 0
        for checkpoint in CHECKPOINTS:
            while processed < checkpoint:
                client.post("/api/v1/chat", json={
                    "user_id": f"mem_test_{processed % 50}",
                    "user_type": "estudiante",
                    "query": queries[processed % len(queries)],
                })
                processed += 1
            gc.collect()
            current, peak = tracemalloc.get_traced_memory()
            row = {"queries": checkpoint, "rss_mb": rss_mb(), "python_current_mb": current / 10**6,
                   "python_peak_mb": peak / 10**6}
            rows.append(row)
            rss_text = "n/d (instala psutil)" if row["rss_mb"] is None else f"{row['rss_mb']:.1f} MB"
            print(f"  {checkpoint:>4} consultas | RSS {rss_text} | Python actual {row['python_current_mb']:.2f} MB "
                  f"| pico {row['python_peak_mb']:.2f} MB")

        snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

    print("\nAsignaciones de Python más grandes (top 5):")
    for stat in snapshot.statistics("lineno")[:5]:
        print(f"  {stat.size / 1024:.1f} KB  {stat.traceback}")

    print("\nTamaño del historial de chat en la sesión:")
    session_rows = []
    for size in SESSION_SIZES:
        kb = session_state_size(size)
        session_rows.append({"messages": size, "session_kb": round(kb, 2)})
        print(f"  {size:>3} mensajes: {kb:.1f} KB")

    with open(os.path.join(args.out_dir, "memory_profile.csv"), "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with open(os.path.join(args.out_dir, "session_size.csv"), "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(session_rows[0]))
        writer.writeheader()
        writer.writerows(session_rows)

    if not args.no_plot:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib no está instalado; se omite la gráfica.")
            return
        fig, ax = plt.subplots(figsize=(7, 4.5))
        x = [r["queries"] for r in rows]
        if all(r["rss_mb"] is not None for r in rows):
            ax.plot(x, [r["rss_mb"] for r in rows], marker="o", label="Memoria del proceso (RSS)")
            ax.axhline(args.limit_mb, color="red", linestyle="--", label=f"Límite del plan ({args.limit_mb:.0f} MB)")
        ax.plot(x, [r["python_current_mb"] for r in rows], marker="s", label="Objetos de Python (tracemalloc)")
        ax.set_xlabel("Consultas procesadas")
        ax.set_ylabel("Memoria (MB)")
        ax.set_title("Memoria del backend frente al número de consultas")
        ax.grid(alpha=0.3)
        ax.legend()
        fig.tight_layout()
        path = os.path.join(args.out_dir, "memory_profile.png")
        fig.savefig(path, dpi=150)
        print(f"\nGráfica guardada en {path}")


if __name__ == "__main__":
    main()
