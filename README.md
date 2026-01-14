Kancha AI – Nepali & English Chatbot

Kancha AI is a bilingual conversational AI chatbot designed for Nepali and English users. It intelligently adapts to the user’s language (English, Nepali in Devanagari, or Romanized Nepali / Nepglish) and responds in a culturally aware, natural, and helpful manner.

The project focuses on real-world AI deployment, secure API usage, and clean conversational UX using Google’s Gemini models and Streamlit.

🚀 Live Demo

🔗 Deployed App:
https://nepali-english-chatbot-j2ajeyz2a6vfyadaeubuvu.streamlit.app/

✨ Features

🌐 Bilingual Support: English + Nepali (Devanagari & Romanized Nepali)

🧠 Language Detection: Automatically detects user language and adapts responses

🇳🇵 Cultural Awareness: Nepali education system, locations, social context

💬 Persistent Chat History using Streamlit session state

🔐 Secure API Key Management (no hard-coded secrets)

📱 Responsive UI (works on mobile & desktop)

🛠 Tech Stack

Python

Streamlit – frontend & deployment

Google Gemini API (google.generativeai)

Environment Variables & Streamlit Secrets

🧩 Architecture Overview

User input is captured via st.chat_input

Language is detected using:

Unicode range for Devanagari

Regex for common Nepali words

Prompt is dynamically adapted:

[NEPGLISH] or [ENGLISH ONLY]

Gemini model processes input using a custom system prompt

Response is rendered using Streamlit’s chat UI

Chat history is preserved using st.session_state
