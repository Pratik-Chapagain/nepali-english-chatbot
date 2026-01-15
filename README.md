# 🇳🇵 Kancha AI – Nepali & English Chatbot

Kancha AI is a bilingual conversational AI chatbot designed for Nepali and English users. It intelligently adapts to the user’s language (English, Nepali in Devanagari, or Romanized Nepali / Nepglish) and responds in a culturally aware, natural, and helpful manner.

The project focuses on real-world AI deployment, secure API usage, and a clean conversational user experience using **Google Gemini** and **Streamlit**.

---

## 🚀 Live Demo

🔗 **Deployed App:**  
https://nepali-english-chatbot-j2ajeyz2a6vfyadaeubuvu.streamlit.app/

---

## ✨ Features

- 🌐 **Bilingual Support** – English + Nepali (Devanagari & Romanized Nepali)
- 🧠 **Language Detection** – Automatically detects user language and adapts responses
- 🇳🇵 **Cultural Awareness** – Nepali education system, locations, and social context
- 💬 **Persistent Chat History** using Streamlit session state
- 🔐 **Secure API Key Management** – No hard-coded secrets
- 📱 **Responsive UI** – Works on mobile and desktop

---

## 🛠 Tech Stack

- **Python**
- **Streamlit** – frontend & deployment
- **Google Gemini API** (`google.generativeai`)
- **Environment Variables & Streamlit Secrets**

---

## 🧩 Architecture Overview

1. User input is captured using `st.chat_input`
2. Language is detected using:
   - Unicode range for Devanagari
   - Regex matching common Nepali words
3. Prompt is dynamically adapted:
   - `[NEPGLISH]` or `[ENGLISH ONLY]`
4. Gemini model processes input using a custom system prompt
5. Response is rendered using Streamlit’s chat UI
6. Chat history is preserved using `st.session_state`

---

## 📄 License

This project is built for learning, experimentation, and portfolio purposes.
