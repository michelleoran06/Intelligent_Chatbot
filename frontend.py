import streamlit as st
import requests
import time

st.set_page_config(page_title="Soporte Cafetería", page_icon="☕", layout="centered")

st.markdown("""
<style>
    .stApp {
        background-color: #f7f9fc;
    }
    .chat-header {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #2c3e50;
        text-align: center;
        padding: 20px;
        background: white;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .bot-msg {
        background-color: #e3f2fd;
        border-radius: 10px;
        padding: 10px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="chat-header"><h2>☕ Asistente de Cafetería FI</h2><p>Resuelve tus dudas sobre menús, horarios y pagos.</p></div>', unsafe_allow_html=True)

BASE_URL = "https://intelligent-chatbot-std8.onrender.com"

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Escribe tu pregunta..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/chat",
            json={"user_id": "usuario_demo", "query": prompt},
            timeout=10
        )
        
        data = response.json()

        if response.status_code != 200:
            error_reply = data.get('detail', 'Ocurrió un error inesperado. Por favor intenta más tarde.')
            with st.chat_message("assistant"):
                st.markdown(f"*{error_reply}*")
            st.session_state.messages.append({"role": "assistant", "content": f"*{error_reply}*"})
        else:
            bot_reply = data.get("response", "")
            
            with st.chat_message("assistant"):
                st.markdown(bot_reply)
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})

            if data.get("routed_to") == "human":
                ticket_id = data.get("ticket_id")
                with st.spinner("Esperando a que un operador atienda tu caso (esto puede tardar unos segundos)..."):
                    resolved = False
                    attempts = 0
                    max_attempts = 20 # Wait up to 60 seconds
                    
                    while not resolved and attempts < max_attempts:
                        time.sleep(3)
                        attempts += 1
                        try:
                            check_res = requests.get(f"{BASE_URL}/api/v1/ticket/{ticket_id}", timeout=5)
                            if check_res.status_code == 200:
                                ticket_data = check_res.json()
                                if ticket_data.get("routed_to") == "human_resolved":
                                    manual_reply = ticket_data.get("response")
                                    resolved = True
                                    
                                    with st.chat_message("assistant"):
                                        st.markdown(f"👨‍💻 **Operador:** {manual_reply}")
                                    st.session_state.messages.append({"role": "assistant", "content": f"👨‍💻 **Operador:** {manual_reply}"})
                        except requests.exceptions.RequestException:
                            pass # Ignore temporary connection errors during polling
                    
                    if not resolved:
                        timeout_msg = "Lo siento, nuestros operadores están ocupados en este momento. Por favor, intenta de nuevo más tarde."
                        with st.chat_message("assistant"):
                            st.markdown(f"*{timeout_msg}*")
                        st.session_state.messages.append({"role": "assistant", "content": f"*{timeout_msg}*"})

    except requests.exceptions.RequestException:
        st.error("El servidor está tomando un descanso o hay problemas de conexión. Por favor, intenta de nuevo en unos minutos.")