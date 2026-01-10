import streamlit as st
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Page configuration
st.set_page_config(page_title="Nepali AI Chatbot")
st.title("Nepali-English Chatbot")

# Clear button with immediate action
if st.button("🧹 Clear Chat", type="secondary"):
    st.session_state.messages = []
    st.rerun()

API_KEY = os.getenv("GEMINI_API_KEY") 

if not API_KEY:
    st.error("GEMINI_API_KEY not found. Please check your .env file.")
    st.stop()

# Configure Gemini
genai.configure(api_key=API_KEY)

# Initialize model (Updated to a standard stable version)
model = genai.GenerativeModel("gemini-2.5-flash-lite")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        
SYSTEM_PROMPT ="""
## Persona
You are "Kancha," a smart, street-savvy, and helpful Nepali assistant. You speak like a local human—helpful but direct. You use "Nepglish" (Romanized Nepali + English) naturally.

## Strict Rules of Engagement:
1. **The 3-Sentence Rule:** Never write more than 3-4 sentences in a single response unless the user asks for a "detailed guide" or "long report." 
2. **Forced Clarification:** For broad topics (e.g., "making money," "traveling," "investing"), you MUST ask the user 1-2 specific questions about their situation before giving advice.
3. **No Hallucinations:** If a user mentions a fake date or technology in history, correct them firmly. (Note: Nepal's first census was 1911 AD).
4. **Natural Nepali:** Avoid repetitive phrases like "kasto kasto" or "vanna milnecha." Use natural spoken Nepali markers like "hai," "ni," "cha ni," and "khasma."
5. **No "Walls of Text":** Use bullet points ONLY if listing items, and never more than 3 items at a time.
"""


# Chat input
if prompt := st.chat_input("नमस्ते! म तपाईंलाई कसरी मद्दत गर्न सक्छु?"):
    # Display and store user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    st.session_state.messages.append({"role": "user", "content": prompt})

    try:
        history = [
            {
                "role": "user" if msg["role"] == "user" else "model",
                "parts": [msg["content"]],
            }
            for msg in st.session_state.messages[:-1] # Previous history
        ]

        # Start a chat session with history
        chat = model.start_chat(history=history)
        
        # Generate response
        response = chat.send_message(prompt)
        reply = response.text

        # Display and store assistant message
        with st.chat_message("assistant"):
            st.markdown(reply)
        
        st.session_state.messages.append({"role": "assistant", "content": reply})

    except Exception as e:
        st.error(f"Something went wrong: {e}")

        