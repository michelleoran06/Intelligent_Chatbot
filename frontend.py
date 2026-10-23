"""Chat para estudiantes, maestros y personal administrativo (Presentation Layer).

La dirección del backend se lee de la variable de entorno BACKEND_URL
(en Streamlit Community Cloud se define en los "Secrets" de la app).
"""
import os
import random
import time

import requests
import streamlit as st

BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
MAX_MESSAGES = int(os.getenv("MAX_MESSAGES", "15"))
MAX_QUERY_LENGTH = int(os.getenv("MAX_QUERY_LENGTH", "500"))
POLL_INTERVAL_SECONDS = 1.5
POLL_ATTEMPTS = 40
USER_TYPES = ["estudiante", "maestro", "administrativo"]

# Mensajes de la Sección 2.4
MSG_SERVICE_UNAVAILABLE = "El servicio no está disponible en este momento. Por favor, intenta de nuevo en unos minutos."
MSG_OPERATORS_BUSY = (
    "Los operadores están ocupados en este momento. Si responden más tarde, verás su respuesta "
    "aquí mismo; también puedes intentar de nuevo más tarde."
)
MSG_MEMORY_FULL = "Memoria llena. Por favor recarga la página para iniciar una nueva conversación."
MSG_UNEXPECTED = "Ocurrió un error inesperado. Por favor intenta más tarde."
OPERATOR_PREFIX = "👨‍💻 **Operador:** "

st.set_page_config(page_title="Soporte Cafetería", page_icon="☕", layout="centered")

st.markdown("""
<style>
    .chat-header {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #ffffff;
        text-align: center;
        padding: 20px;
        background: linear-gradient(90deg, #2c3e50, #3498db);
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ estado de la sesión
def init_state() -> None:
    defaults = {
        "messages": [],
        "review_submitted": False,
        "pending_tickets": [],
        "user_id_num": random.randint(1000, 9999),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def add_message(role: str, content: str, ticket_id=None, allow_feedback: bool = False) -> dict:
    message = {"role": role, "content": content, "ticket_id": ticket_id, "allow_feedback": allow_feedback}
    st.session_state.messages.append(message)
    return message


# ------------------------------------------------------------------ comunicación con la API
def send_feedback(ticket_id: int, widget_key: str) -> None:
    """RF09: guarda la calificación 👍/👎 de una respuesta del bot."""
    value = st.session_state.get(widget_key)
    if value is None:
        return
    try:
        res = requests.post(f"{BASE_URL}/api/v1/ticket/{ticket_id}/feedback",
                            json={"helpful": value == 1}, timeout=5)
        if res.status_code == 200:
            st.toast("¡Gracias por calificar la respuesta!", icon="👍")
        else:
            st.toast("No se pudo guardar tu calificación.", icon="⚠️")
    except requests.exceptions.RequestException:
        st.toast("No se pudo guardar tu calificación (sin conexión).", icon="⚠️")


def fetch_ticket(ticket_id: int):
    res = requests.get(f"{BASE_URL}/api/v1/ticket/{ticket_id}", timeout=5)
    return res.json() if res.status_code == 200 else None


def render_message(message: dict) -> None:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("allow_feedback") and message.get("ticket_id"):
            key = f"feedback_{message['ticket_id']}"
            st.feedback("thumbs", key=key, on_change=send_feedback, args=(message["ticket_id"], key))


def show_assistant(content: str, ticket_id=None, allow_feedback: bool = False) -> None:
    render_message(add_message("assistant", content, ticket_id, allow_feedback))


def check_pending_tickets() -> None:
    """Muestra respuestas de operadores que llegaron después de que terminó la espera."""
    still_pending = []
    for ticket_id in st.session_state.pending_tickets:
        try:
            data = fetch_ticket(ticket_id)
        except (requests.exceptions.RequestException, ValueError):
            still_pending.append(ticket_id)
            continue
        if data and data.get("routed_to") == "human_resolved":
            add_message("assistant", f"{OPERATOR_PREFIX}{data.get('response', '')}")
        else:
            still_pending.append(ticket_id)
    st.session_state.pending_tickets = still_pending


def wait_for_operator(ticket_id: int) -> bool:
    with st.spinner("Esperando a que un operador atienda tu caso (esto puede tardar unos segundos)..."):
        for _ in range(POLL_ATTEMPTS):
            time.sleep(POLL_INTERVAL_SECONDS)
            try:
                data = fetch_ticket(ticket_id)
            except (requests.exceptions.RequestException, ValueError):
                continue
            if data and data.get("routed_to") == "human_resolved":
                show_assistant(f"{OPERATOR_PREFIX}{data.get('response', '')}")
                return True
    return False


def send_question(prompt: str, user_type: str, user_id: str, request_human: bool = False) -> None:
    render_message(add_message("user", prompt))
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/chat",
            json={"user_id": user_id, "user_type": user_type, "query": prompt, "request_human": request_human},
            timeout=60,
        )
    except requests.exceptions.RequestException:
        show_assistant(f"*{MSG_SERVICE_UNAVAILABLE}*")
        return

    try:
        data = response.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}

    if response.status_code != 200:
        if response.status_code in (502, 503, 504):  # backend dormido o caído (cold start)
            detail = MSG_SERVICE_UNAVAILABLE
        else:
            detail = data.get("detail")
            if not isinstance(detail, str) or not detail.strip():
                detail = MSG_UNEXPECTED
        show_assistant(f"*{detail}*")
        return

    ticket_id = data.get("ticket_id")
    routed_to = data.get("routed_to")
    show_assistant(data.get("response", ""), ticket_id=ticket_id,
                   allow_feedback=routed_to == "bot" and ticket_id is not None)

    if routed_to == "human" and ticket_id is not None:
        if not wait_for_operator(ticket_id):
            st.session_state.pending_tickets.append(ticket_id)
            show_assistant(f"*{MSG_OPERATORS_BUSY}*")


# ------------------------------------------------------------------ interfaz
init_state()
memory_full = len(st.session_state.messages) >= MAX_MESSAGES

with st.sidebar:
    st.title("⚙️ Opciones")
    user_type = st.selectbox("Perfil de usuario:", USER_TYPES)

    st.divider()
    st.markdown("### ⚡ Consultas rápidas")
    quick_prompt = None
    if st.button("🍽️ Menú del día", disabled=memory_full):
        quick_prompt = "¿Qué trae el menú del día?"
    if st.button("⏰ Horarios", disabled=memory_full):
        quick_prompt = "¿A qué hora abren y cierran?"
    if st.button("💳 Pagos", disabled=memory_full):
        quick_prompt = "¿Aceptan tarjeta o transferencia?"

    st.divider()
    request_operator = st.button("🙋 Hablar con un operador", disabled=memory_full)
    if st.session_state.pending_tickets:
        st.info("Tienes preguntas esperando respuesta de un operador.")
        st.button("🔄 Revisar respuesta del operador")

    st.divider()
    if st.button("🗑️ Limpiar chat"):
        st.session_state.messages = []
        st.session_state.pending_tickets = []
        st.session_state.review_submitted = False
        st.rerun()

    st.divider()
    st.markdown("### ⭐ Evalúa la cafetería")
    if not st.session_state.review_submitted:
        with st.form("review_form", clear_on_submit=True):
            estrellas = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
            rating_visual = st.radio("¿Qué calificación le das?", estrellas, index=4, horizontal=True)
            comment = st.text_area("Comentario (opcional)", max_chars=500)
            if st.form_submit_button("Enviar reseña"):
                rating_num = estrellas.index(rating_visual) + 1
                try:
                    res = requests.post(
                        f"{BASE_URL}/api/v1/reviews",
                        json={"user_type": user_type, "rating": rating_num, "comment": comment},
                        timeout=5,
                    )
                    if res.status_code == 200:
                        st.session_state.review_submitted = True
                        st.success("¡Gracias por tu opinión!")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error(f"El servidor devolvió un error {res.status_code}. Intenta de nuevo.")
                except requests.exceptions.RequestException:
                    st.error(MSG_SERVICE_UNAVAILABLE)
    else:
        st.success("✨ ¡Ya evaluaste el servicio! Limpia el chat si deseas enviar otra reseña.")

session_user_id = f"{user_type}_{st.session_state.user_id_num}"

st.markdown(
    '<div class="chat-header"><h2>☕ Asistente de Cafetería FI</h2>'
    '<p>Resuelve tus dudas sobre menús, horarios y pagos.</p></div>',
    unsafe_allow_html=True,
)

if st.session_state.pending_tickets:
    check_pending_tickets()

for past_message in st.session_state.messages:
    render_message(past_message)

if len(st.session_state.messages) >= MAX_MESSAGES:
    st.warning(MSG_MEMORY_FULL)
    st.chat_input("Escribe tu pregunta...", disabled=True)
else:
    chat_input_value = st.chat_input("Escribe tu pregunta...")
    if request_operator:
        last_question = next((m["content"] for m in reversed(st.session_state.messages) if m["role"] == "user"), None)
        operator_prompt = (f"Quiero hablar con un operador sobre: {last_question}"
                           if last_question else "Quiero hablar con un operador.")
        send_question(operator_prompt[:MAX_QUERY_LENGTH], user_type, session_user_id, request_human=True)
    elif quick_prompt or chat_input_value:
        send_question(quick_prompt or chat_input_value, user_type, session_user_id)

    if len(st.session_state.messages) >= MAX_MESSAGES:
        st.warning(MSG_MEMORY_FULL)
