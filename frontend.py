import streamlit as st
import requests
import time

st.title("Intelligent Chatbot - Soporte")

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
            "https://intelligent-chatbot-std8.onrender.com",
            json={"user_id": "usuario_demo", "query": prompt}
        )
        
        data = response.json()

        if response.status_code != 200:
            error_reply = f"⚠️ {data.get('detail', 'Ocurrió un error inesperado.')}"
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
                with st.spinner("Esperando a que un operador atienda tu caso..."):
                    resolved = False
                    while not resolved:
                        time.sleep(3)
                        check_res = requests.get(f"[https://intelligent-chatbot-std8.onrender.com/api/v1/ticket/](https://intelligent-chatbot-std8.onrender.com/api/v1/ticket/){ticket_id}")
                        if check_res.status_code == 200:
                            ticket_data = check_res.json()
                            if ticket_data.get("routed_to") == "human_resolved":
                                manual_reply = ticket_data.get("response")
                                resolved = True
                                
                    with st.chat_message("assistant"):
                        st.markdown(f"**Operador:** {manual_reply}")
                    st.session_state.messages.append({"role": "assistant", "content": f"**Operador:** {manual_reply}"})

    except requests.exceptions.RequestException:
        st.error("Error de conexión. Verifica que el servidor esté funcionando.")
