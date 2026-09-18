import streamlit as st
import requests
import time

st.set_page_config(page_title="Asistente Cafetería FI", page_icon="☕")

st.markdown("""
<style>
    .stChatMessage { border-radius: 12px; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    [data-testid="stHeader"] { background-color: transparent; }
</style>
""", unsafe_allow_html=True)

st.title("☕ Asistente Virtual")
st.caption("Cafetería de la Facultad de Ingeniería. Respuestas rápidas a tus dudas.")

BASE_URL = "https://intelligent-chatbot-std8.onrender.com"

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Escribe tu pregunta aquí..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        with st.spinner("Conectando con el servidor... (puede tardar un poco si está inactivo)"):
            response = requests.post(
                f"{BASE_URL}/api/v1/chat",
                json={"user_id": "alumno_fi", "query": prompt},
                timeout=45
            )
            
        data = response.json()

        if response.status_code != 200:
            error_reply = f"⚠️ {data.get('detail', 'Error inesperado.')}"
            with st.chat_message("assistant"):
                st.markdown(error_reply)
            st.session_state.messages.append({"role": "assistant", "content": error_reply})
        else:
            bot_reply = data.get("response", "")
            
            with st.chat_message("assistant"):
                st.markdown(bot_reply)
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})

            if data.get("routed_to") == "human":
                ticket_id = data.get("ticket_id")
                with st.spinner("Transfiriendo tu caso a un operador de la cafetería..."):
                    resolved = False
                    max_attempts = 20
                    attempts = 0
                    manual_reply = ""
                    
                    while not resolved and attempts < max_attempts:
                        time.sleep(3)
                        attempts += 1
                        try:
                            check_res = requests.get(f"{BASE_URL}/api/v1/ticket/{ticket_id}", timeout=5)
                            if check_res.status_code == 200:
                                ticket_data = check_res.json()
                                if ticket_data.get("status") == "resolved" or ticket_data.get("routed_to") == "human_resolved":
                                    manual_reply = ticket_data.get("response")
                                    resolved = True
                        except requests.exceptions.RequestException:
                            pass
                            
                    if resolved:
                        with st.chat_message("assistant", avatar="🧑‍🍳"):
                            st.markdown(f"*Personal de Cafetería:* {manual_reply}")
                        st.session_state.messages.append({"role": "assistant", "content": f"*Personal de Cafetería:* {manual_reply}"})
                    else:
                        error_timeout = "⚠️ Tuvimos un problema de conexión de nuestro lado o nuestros operadores están muy ocupados. Por favor, intenta enviar tu duda nuevamente."
                        with st.chat_message("assistant"):
                            st.markdown(error_timeout)
                        st.session_state.messages.append({"role": "assistant", "content": error_timeout})

    except requests.exceptions.Timeout:
        timeout_msg = "⚠️ El servidor estaba dormido y tardó en responder. Por favor, envía tu pregunta de nuevo."
        with st.chat_message("assistant"):
            st.markdown(timeout_msg)
        st.session_state.messages.append({"role": "assistant", "content": timeout_msg})
    except requests.exceptions.RequestException:
        st.error("Error crítico de red. Verifica tu conexión a internet.")
