
import streamlit as st
from google import genai

# Page Config
st.set_page_config(page_title="Nepali AI Chatbot",)
st.title("🇳🇵 Nepali-English Chatbot")

# 🔐 Setup Client (Replace with your actual key)
API_KEY = "AIzaSyDdGKGlnez2d2PkjU2OEc2JLdsTk0tY2P4"
client = genai.Client(api_key=API_KEY)

# Initialize Chat History in Streamlit state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Input
if prompt := st.chat_input("नमस्ते! म तपाईंलाई कसरी मद्दत गर्न सक्छु?"):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate Response
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        full_response = response.text
        
        # Add AI response to history
        with st.chat_message("assistant"):
            st.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        
    except Exception as e:
        st.error(f"Error: {e}")