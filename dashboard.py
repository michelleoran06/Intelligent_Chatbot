import streamlit as st
import pandas as pd
import requests
import time

st.set_page_config(page_title="Dashboard Cafetería", page_icon="🎧", layout="wide")

st.markdown("""
<style>
    .metric-card { background-color: #1e1e1e; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("🎧 Panel de Operador - Cafetería FI")
st.markdown("---")

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
        st.error("Error conectando con la base de datos central.")
        return pd.DataFrame()

df = load_escalated_cases()

if not df.empty:
    st.dataframe(
        df[['id', 'timestamp', 'query']], 
        use_container_width=True, 
        hide_index=True
    )
    
    st.markdown("### Atender ticket pendiente")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        case_id = st.selectbox("Selecciona el ID del ticket:", df['id'])
    with col2:
        respuesta = st.text_area("Respuesta del operador:", height=100)
        
    if st.button("Enviar respuesta y cerrar ticket", type="primary"):
        if respuesta.strip():
            try:
                res = requests.post(
                    f"{BASE_URL}/api/v1/ticket/{case_id}/resolve",
                    json={"manual_response": respuesta},
                    timeout=10
                )
                if res.status_code == 200:
                    st.success(f"Ticket {case_id} cerrado correctamente.")
                    time.sleep(1)
                    st.rerun()
            except Exception:
                st.error("Error enviando la resolución.")
        else:
            st.warning("Debes escribir una respuesta.")
else:
    st.info("Todo en orden. No hay alumnos esperando respuesta en este momento.")

time.sleep(10)
st.rerun()
