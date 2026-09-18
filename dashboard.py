import streamlit as st
import pandas as pd
import requests
import time
import streamlit.components.v1 as components

st.set_page_config(page_title="Panel de Operador", page_icon="🎧", layout="wide")

# Script de auto-refresh cada 10 segundos (recarga la página solo si no estás escribiendo)
components.html(
    """
    <script>
    setTimeout(function() {
        var isTyping = false;
        var textareas = window.parent.document.querySelectorAll('textarea');
        textareas.forEach(function(ta) {
            if (ta.value.trim() !== '') {
                isTyping = true;
            }
        });
        if (!isTyping) {
            window.parent.location.reload();
        }
    }, 10000);
    </script>
    """,
    height=0,
    width=0,
)

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

st.markdown('<div class="header-box"><h1>🎧 Panel de Operador - Casos Escalados</h1><p>Atiende las consultas que el bot no pudo responder.</p></div>', unsafe_allow_html=True)

BASE_URL = "https://intelligent-chatbot-std8.onrender.com"

def load_escalated_cases():
    try:
        response = requests.get(f"{BASE_URL}/api/v1/tickets/escalated", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                return pd.DataFrame(data)
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

with st.spinner("Buscando nuevos casos en la cola..."):
    df = load_escalated_cases()

if 'previous_count' not in st.session_state:
    st.session_state.previous_count = len(df) if not df.empty else 0

current_count = len(df) if not df.empty else 0

if current_count > st.session_state.previous_count:
    st.toast("¡Nuevo caso asignado! Un usuario necesita ayuda.", icon="🚨")
    # Reproducir un sonido de notificación sutil
    components.html(
        """
        <audio autoplay>
            <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
        </audio>
        """,
        height=0,
        width=0,
    )

st.session_state.previous_count = current_count

if not df.empty:
    st.markdown(f'<div><span class="status-badge">🚨 {len(df)} chats pendientes</span></div><br>', unsafe_allow_html=True)
    
    st.dataframe(
        df[['id', 'user_id', 'query', 'timestamp']], 
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("---")
    st.subheader("💬 Atender caso")
    
    # Uso de st.form para evitar el bug del doble click y envíos accidentales
    with st.form(key="resolve_form", clear_on_submit=True):
        col1, col2 = st.columns([1, 2])
        
        with col1:
            case_id = st.selectbox("ID del ticket a responder:", df['id'])
        with col2:
            respuesta = st.text_area("Escribe tu respuesta para el usuario:")
            
        submit_btn = st.form_submit_button("Enviar Respuesta y Cerrar Caso", type="primary")
        
        if submit_btn:
            if respuesta.strip():
                try:
                    res = requests.post(
                        f"{BASE_URL}/api/v1/ticket/{case_id}/resolve",
                        json={"manual_response": respuesta},
                        timeout=10
                    )
                    if res.status_code == 200:
                        st.success(f"¡Excelente! Respuesta enviada. El ticket {case_id} ha sido resuelto.")
                        time.sleep(1.5) # Pausa para que el usuario lea el mensaje de éxito
                        st.rerun()
                    else:
                        st.error("Ocurrió un error al intentar cerrar el caso.")
                except Exception:
                    st.error("Error conectando con la API para resolver el caso.")
            else:
                st.warning("Por favor escribe una respuesta antes de enviar.")
else:
    st.success("✨ ¡Todo al día! No hay chats en la cola de espera. (Buscando automáticamente...)")