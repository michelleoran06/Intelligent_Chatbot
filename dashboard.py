import streamlit as st
import pandas as pd
import requests

st.set_page_config(layout="wide")
st.title("Panel de Operador - Casos Escalados")

BASE_URL = "https://intelligent-chatbot-std8.onrender.com"

def load_escalated_cases():
    try:
        response = requests.get(f"{BASE_URL}/api/v1/tickets/escalated")
        if response.status_code == 200:
            data = response.json()
            if data:
                return pd.DataFrame(data)
        return pd.DataFrame()
    except Exception:
        st.error("Error conectando con el servidor.")
        return pd.DataFrame()

df = load_escalated_cases()

if not df.empty:
    st.dataframe(df, use_container_width=True)
    
    st.subheader("Atender caso")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        case_id = st.selectbox("ID del ticket:", df['id'])
    with col2:
        respuesta = st.text_area("Respuesta manual:")
        
    if st.button("Resolver caso"):
        if respuesta.strip():
            try:
                res = requests.post(
                    f"{BASE_URL}/api/v1/ticket/{case_id}/resolve",
                    json={"manual_response": respuesta}
                )
                if res.status_code == 200:
                    st.success(f"Respuesta enviada. El ticket {case_id} ha sido cerrado.")
                    st.rerun()
            except Exception:
                st.error("Error conectando con la API.")
        else:
            st.warning("Escribe una respuesta antes de enviar.")
else:
    st.info("No hay chats en la cola de espera.")

if st.button("Actualizar tabla"):
    st.rerun()
