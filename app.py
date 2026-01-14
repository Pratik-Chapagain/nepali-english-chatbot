import streamlit as st
import google.generativeai as genai
import os, re
from dotenv import load_dotenv

# ---------------- CONFIG ----------------
load_dotenv()

st.set_page_config(
    page_title="Kancha AI",
    page_icon="🇳🇵",
    layout="centered"
)

# ---------------- API ----------------
API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
if not API_KEY:
    st.error("GEMINI_API_KEY missing")
    st.stop()

genai.configure(api_key=API_KEY)

SYSTEM_PROMPT = """You are Kancha AI, a helpful and culturally-aware bilingual assistant fluent in both Nepali and English.

<language_handling>
- **Detect the user's language**: If the user writes in Nepali (Devanagari script or Romanized/Nepglish), respond primarily in Nepglish (Romanized Nepali) with occasional English words as natural in conversation.
- **If the user writes in English only**, respond in clear, professional English.
- **Be flexible**: Users may code-switch between Nepali and English mid-conversation. Match their style naturally.
- **Nepglish style**: Use Romanized Nepali that feels natural and conversational (e.g., "ramro cha", "k cha", "timi", "timro", "yo", "tyo").
</language_handling>

<tone_and_personality>
- **Warm and respectful**: Use culturally appropriate greetings (Namaste, dai/bhai/didi/bahini when suitable).
- **Professional yet friendly**: Be helpful without being overly casual or using excessive slang.
- **Concise and clear**: Provide direct answers. Avoid unnecessary verbosity.
- **Encouraging and supportive**: Especially when users discuss goals, education, or challenges.
</tone_and_personality>

<cultural_awareness>
- Understand Nepali context: education system (SEE, +2, MBBS entrance exams), geography (provinces, cities), cultural norms, and local references.
- Be sensitive to local concerns: affordability, family expectations, regional differences.
- Use appropriate honorifics and informal pronouns (timi/timro for peers, tapai for formal contexts).
</cultural_awareness>

<response_guidelines>
- **Answer accurately**: Provide factual, helpful information about Nepal-specific queries (colleges, locations, weather, etc.).
- **Be honest about limitations**: If you don't have current information, acknowledge it clearly.
- **Structure responses clearly**: Use short paragraphs. Avoid excessive bullet points unless requested.
- **Avoid overformatting**: No emojis unless the user uses them first. Keep formatting minimal and natural.
</response_guidelines>

<example_interactions>
User (Nepali): "MBBS ko lagi kun college ramro cha?"
You: "MBBS ko lagi Nepal ma kati ramra colleges chan. Government colleges jastai IOM, Patan Academy, ra BPKIHS dherai ramro chan - quality ni ramro cha ani fees ni kam cha. Private ma KIST, Manipal, ra Kathmandu Medical College pani popular chan. Timro budget ra location preference k ho?"

User (English): "What is the capital of Bagmati Province?"
You: "The capital of Bagmati Province is Hetauda."
</example_interactions>

Remember: Be genuinely helpful, culturally sensitive, and linguistically adaptive. Your goal is to assist users effectively while respecting Nepali culture and communication styles."""

model = genai.GenerativeModel(
    "gemini-2.5-flash-lite",
    system_instruction=SYSTEM_PROMPT
)

# ---------------- HELPERS ----------------
def contains_nepali(text):
    if any(0x0900 <= ord(c) <= 0x097F for c in text):
        return True
    return bool(re.search(r'\b(cha|ho|huncha|xaina|kati|kaha|ramro)\b', text.lower()))

def reply_to(prompt):
    """Send message to Gemini API with error handling"""
    try:
        if contains_nepali(prompt):
            prompt = f"[NEPGLISH] {prompt}"
        else:
            prompt = f"[ENGLISH ONLY] {prompt}"
        
        # API call with timeout
        response = st.session_state.chat.send_message(
            prompt,
            request_options={"timeout": 30}
        )
        return response.text
        
    except Exception as e:
        # Friendly error messages
        error_message = str(e).lower()
        
        if "quota" in error_message or "429" in str(e):
            return "**⚠️ Service Limit Reached**\n\nI've reached my usage limit for now. Please try again later or contact the administrator."
        
        elif "timeout" in error_message:
            return "**⏱️ Response Timeout**\n\nThe AI is taking too long. Try:\n• Shorter messages\n• Waiting a moment\n• Breaking complex questions into parts"
        
        elif "network" in error_message or "connection" in error_message:
            return "**🌐 Connection Issue**\n\nPlease check your internet connection and try again."
        
        elif "invalid" in error_message and "key" in error_message:
            return "**🔑 Configuration Issue**\n\nThere's a problem with the AI service setup. Please report this issue."
        
        else:
            return f"**❌ Unexpected Error**\n\nI encountered an issue: `{str(e)[:80]}...`\n\nPlease try rephrasing your question or try again in a moment."
    if contains_nepali(prompt):
        prompt = f"[NEPGLISH] {prompt}"
    else:
        prompt = f"[ENGLISH ONLY] {prompt}"
    return st.session_state.chat.send_message(prompt).text

# ---------------- STATE ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])

# ---------------- UI ----------------
st.title("Kancha AI")
st.caption("Ask me anything in English or Nepali.")

# Show suggestions only if no messages
if not st.session_state.messages:
    st.subheader("Suggestions")
    suggestions = [
        "Translate 'Good morning' to Nepali",
        "Weather in Kathmandu today",
        "Tell me a fun fact about Nepal",
        "Help me write a professional email"
    ]

    cols = st.columns(2)
    for idx, s in enumerate(suggestions):
        with cols[idx % 2]:
            if st.button(s, key=f"sug_{idx}"):
                st.session_state.messages.append({"role": "user", "content": s})
                with st.spinner("Thinking..."):
                    reply = reply_to(s)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                st.rerun()

# Display all messages
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Handle new user input
if prompt := st.chat_input("Type your message"):
    # Show user message immediately
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Show assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = reply_to(prompt)
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
    
    # Rerun to update the UI
    st.rerun()