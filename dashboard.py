"""Panel de operador y administrador (Presentation Layer).

- Casos pendientes: la cola se actualiza sola cada pocos segundos (polling, Sección 6).
- Estadísticas (RF08), reseñas del lugar (RF11), base de conocimiento (RF03) y errores.

Variables de entorno: BACKEND_URL y, si el backend lo exige, ADMIN_TOKEN.
"""
import os
import time

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
REFRESH_SECONDS = int(os.getenv("DASHBOARD_REFRESH_SECONDS", "10"))
ALERT_SOUND_URL = "https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3"
CONNECTION_ERROR = "No se pudo conectar con la API. Revisa que el backend esté en ejecución."

st.set_page_config(page_title="Panel de Operador y Admin", page_icon="🎧", layout="wide")

st.markdown("""
<style>
    .header-box {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .status-badge {
        background-color: #ff4b4b;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 14px;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.05); opacity: 0.8; }
        100% { transform: scale(1); opacity: 1; }
    }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="header-box"><h1>🎧 Panel de Operador y Administrador</h1>'
    '<p>Casos escalados, estadísticas, reseñas y base de conocimiento.</p></div>',
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ utilidades HTTP
def api_get(path: str):
    try:
        res = requests.get(f"{BASE_URL}{path}", timeout=10)
    except requests.exceptions.RequestException:
        return None, CONNECTION_ERROR
    if res.status_code != 200:
        return None, f"La API respondió con el código {res.status_code}."
    try:
        return res.json(), None
    except ValueError:
        return None, "La API devolvió una respuesta no válida."


def api_send(method: str, path: str, payload=None):
    headers = {"X-Admin-Token": ADMIN_TOKEN} if ADMIN_TOKEN else {}
    try:
        return requests.request(method, f"{BASE_URL}{path}", json=payload, headers=headers, timeout=15), None
    except requests.exceptions.RequestException:
        return None, CONNECTION_ERROR


def error_detail(res) -> str:
    try:
        data = res.json()
    except ValueError:
        return f"código {res.status_code}"
    detail = data.get("detail") if isinstance(data, dict) else None
    errors = data.get("errors") if isinstance(data, dict) else None
    text = detail if isinstance(detail, str) else f"código {res.status_code}"
    if errors:
        text += " " + "; ".join(f"{e.get('field')}: {e.get('error')}" for e in errors)
    return text


def format_ms(value) -> str:
    return "—" if value is None else f"{value:,.0f} ms"


# ------------------------------------------------------------------ casos pendientes (RF06, RF07)
@st.fragment(run_every=REFRESH_SECONDS)
def queue_monitor():
    data, error = api_get("/api/v1/tickets/escalated")
    if error:
        st.error(error)
        return
    tickets = data or []
    count = len(tickets)
    previous = st.session_state.get("previous_count")
    if previous is not None and count > previous:
        st.toast("¡Nuevo caso asignado! Un usuario necesita ayuda.", icon="🚨")
        components.html(
            f'<audio autoplay><source src="{ALERT_SOUND_URL}" type="audio/mpeg"></audio>',
            height=0, width=0,
        )
    st.session_state.previous_count = count

    if not tickets:
        st.success("✨ ¡Todo al día! No hay chats en la cola de espera.")
        return
    st.markdown(f'<div><span class="status-badge">🚨 {count} chats pendientes</span></div><br>',
                unsafe_allow_html=True)
    df = pd.DataFrame(tickets)
    columns = [c for c in ["id", "user_id", "user_type", "query", "timestamp"] if c in df.columns]
    st.dataframe(df[columns], hide_index=True)
    st.caption(f"La cola se actualiza sola cada {REFRESH_SECONDS} s. Si llegó un caso nuevo, "
               "pulsa «Actualizar lista de casos» para poder responderlo.")


def resolve_section():
    st.subheader("💬 Atender caso")
    st.button("🔄 Actualizar lista de casos")
    data, error = api_get("/api/v1/tickets/escalated")
    if error:
        st.error(error)
        return
    if not data:
        st.caption("No hay casos para responder.")
        return

    labels = {t["id"]: f"#{t['id']} · {t.get('user_type', '')} · {t.get('query', '')[:80]}" for t in data}
    with st.form("resolve_form", clear_on_submit=True):
        case_id = st.selectbox("Ticket a responder:", list(labels), format_func=lambda i: labels[i])
        respuesta = st.text_area("Respuesta para el usuario:", max_chars=2000)
        submitted = st.form_submit_button("Enviar respuesta y cerrar caso", type="primary")

    if not submitted:
        return
    if not respuesta.strip():
        st.warning("Por favor escribe una respuesta antes de enviar.")
        return
    res, err = api_send("POST", f"/api/v1/ticket/{case_id}/resolve", {"manual_response": respuesta.strip()})
    if err:
        st.error(err)
    elif res.status_code == 200:
        st.success(f"Respuesta enviada. El ticket {case_id} quedó resuelto.")
        time.sleep(1.2)
        st.rerun()
    elif res.status_code in (404, 409):
        st.warning("Ese caso ya fue atendido o ya no existe. Actualiza la lista.")
    else:
        st.error(f"No se pudo cerrar el caso: {error_detail(res)}")


# ------------------------------------------------------------------ estadísticas (RF08)
def stats_section():
    st.subheader("📊 Estadísticas de uso y desempeño")
    st.button("🔄 Actualizar estadísticas")
    data, error = api_get("/api/v1/stats")
    if error:
        st.error(error)
        return
    overall = (data or {}).get("overall") or {}
    by_type = (data or {}).get("by_user_type") or []
    if not overall.get("total"):
        st.info("Sin datos todavía.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Conversaciones", overall["total"])
    c2.metric("Resueltas por el bot", overall["answered_by_bot"])
    c3.metric("Tasa de escalamiento", f"{overall['escalation_rate'] * 100:.1f} %")
    c4.metric("Tiempo medio de respuesta", format_ms(overall.get("avg_response_ms")))
    c5.metric("Percentil 95", format_ms(overall.get("p95_response_ms")))

    rated = overall["positive_feedback"] + overall["negative_feedback"]
    if rated:
        st.caption(f"Calificaciones de respuestas: 👍 {overall['positive_feedback']} · "
                   f"👎 {overall['negative_feedback']} ({overall['positive_feedback'] / rated * 100:.0f} % útiles)")

    df = pd.DataFrame(by_type)
    st.markdown("**Por tipo de usuario**")
    st.bar_chart(df.set_index("user_type")[["answered_by_bot", "escalated"]])
    st.dataframe(df, hide_index=True)


# ------------------------------------------------------------------ reseñas del lugar (RF11)
def reviews_section():
    st.subheader("⭐ Reseñas de la cafetería")
    st.button("🔄 Actualizar reseñas")
    data, error = api_get("/api/v1/reviews")
    if error:
        st.error(error)
        return
    if not data:
        st.info("Aún no hay reseñas.")
        return
    df = pd.DataFrame(data)
    st.metric(label="Calificación promedio", value=f"{df['rating'].mean():.1f} / 5", delta=f"{len(df)} reseñas",
              delta_color="off")
    st.dataframe(df, hide_index=True)


# ------------------------------------------------------------------ base de conocimiento (RF03)
def knowledge_base_section():
    st.subheader("📚 Base de conocimiento")
    if not ADMIN_TOKEN:
        st.caption("Sin ADMIN_TOKEN configurado: el backend acepta cambios sin token (recomendable solo en local).")
    data, error = api_get("/api/v1/kb")
    if error:
        st.error(error)
        return
    entries = {entry["id"]: entry for entry in (data or [])}
    if entries:
        st.dataframe(pd.DataFrame([
            {
                "id": e["id"],
                "categoría": e["category"],
                "respuesta": e["answer"],
                "preguntas": len(e["questions"]),
                "palabras clave": ", ".join(e["keywords"]),
            }
            for e in entries.values()
        ]), hide_index=True)

    new_label = "➕ Nueva entrada"
    choice = st.selectbox("Entrada a crear o editar:", [new_label] + list(entries))
    is_new = choice == new_label
    entry = entries.get(choice, {})

    with st.form(f"kb_form_{choice}"):
        kb_id = st.text_input("Identificador (minúsculas, números y _)", value=entry.get("id", ""), disabled=not is_new)
        category = st.text_input("Categoría", value=entry.get("category", ""))
        answer = st.text_area("Respuesta que verá el usuario", value=entry.get("answer", ""), height=120)
        questions = st.text_area("Preguntas de ejemplo (una por línea)",
                                 value="\n".join(entry.get("questions", [])), height=160)
        keywords = st.text_input("Palabras clave de respaldo (separadas por comas)",
                                 value=", ".join(entry.get("keywords", [])))
        saved = st.form_submit_button("Guardar", type="primary")

    if saved:
        payload = {
            "category": category.strip(),
            "answer": answer.strip(),
            "questions": [q.strip() for q in questions.splitlines() if q.strip()],
            "keywords": [k.strip() for k in keywords.split(",") if k.strip()],
        }
        if is_new:
            payload["id"] = kb_id.strip()
            res, err = api_send("POST", "/api/v1/kb", payload)
        else:
            res, err = api_send("PUT", f"/api/v1/kb/{choice}", payload)
        if err:
            st.error(err)
        elif res.status_code in (200, 201):
            st.success("Guardado. El chatbot usará el cambio en cuanto termine la reindexación (unos segundos).")
            time.sleep(1.2)
            st.rerun()
        else:
            st.error(f"No se pudo guardar: {error_detail(res)}")

    if not is_new:
        with st.expander("🗑️ Eliminar esta entrada"):
            confirm = st.checkbox(f"Confirmo que quiero eliminar «{choice}»", key=f"confirm_{choice}")
            if st.button("Eliminar", disabled=not confirm, key=f"delete_{choice}"):
                res, err = api_send("DELETE", f"/api/v1/kb/{choice}")
                if err:
                    st.error(err)
                elif res.status_code == 200:
                    st.success("Entrada eliminada.")
                    time.sleep(1.2)
                    st.rerun()
                else:
                    st.error(f"No se pudo eliminar: {error_detail(res)}")


# ------------------------------------------------------------------ errores del sistema
def errors_section():
    st.subheader("⚠️ Registro de errores")
    st.button("🔄 Actualizar errores")
    data, error = api_get("/api/v1/errors")
    if error:
        st.error(error)
    elif data:
        st.dataframe(pd.DataFrame(data), hide_index=True)
    else:
        st.success("Sin errores registrados.")


tab_queue, tab_stats, tab_reviews, tab_kb, tab_errors = st.tabs(
    ["🚨 Casos pendientes", "📊 Estadísticas", "⭐ Reseñas", "📚 Base de conocimiento", "⚠️ Errores"]
)
with tab_queue:
    queue_monitor()
    st.markdown("---")
    resolve_section()
with tab_stats:
    stats_section()
with tab_reviews:
    reviews_section()
with tab_kb:
    knowledge_base_section()
with tab_errors:
    errors_section()
