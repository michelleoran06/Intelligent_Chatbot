import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Panel de Operador", page_icon="🎧", layout="wide")

st.markdown("""
<style>
    .header-box {
        background-color: #2c3e50;
        color: white;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        margin-bottom: 25px;
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
        st.error("Error conectando con el servidor. Verifica que el backend esté corriendo.")
        return pd.DataFrame()

df = load_escalated_cases()

if not df.empty:
    st.subheader(f"En cola: {len(df)} chats pendientes")
    st.dataframe(df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("Atender caso")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        case_id = st.selectbox("ID del ticket a responder:", df['id'])
    with col2:
        respuesta = st.text_area("Escribe tu respuesta para el usuario:")
        
    if st.button("Enviar Respuesta y Cerrar Caso", type="primary"):
        if respuesta.strip():
            try:
                res = requests.post(
                    f"{BASE_URL}/api/v1/ticket/{case_id}/resolve",
                    json={"manual_response": respuesta},
                    timeout=10
                )
                if res.status_code == 200:
                    st.success(f"¡Excelente! Respuesta enviada. El ticket {case_id} ha sido resuelto.")
                    st.rerun()
                else:
                    st.error("Ocurrió un error al intentar cerrar el caso.")
            except Exception:
                st.error("Error conectando con la API para resolver el caso.")
        else:
            st.warning("Por favor escribe una respuesta antes de enviar.")
else:
    st.info("¡Todo al día! No hay chats en la cola de espera.")

st.markdown("---")
if st.button("🔄 Actualizar tabla manualmente"):
    st.rerun()