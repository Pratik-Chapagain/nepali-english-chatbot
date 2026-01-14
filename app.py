import streamlit as st
import google.generativeai as genai  # CHANGED: Use OLD package
import os, re, time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ---------------- RATE LIMITER ----------------
class RateLimiter:
    """Prevent hitting API limits"""
    def __init__(self, calls_per_minute=8):  # Conservative limit for free tier
        self.calls_per_minute = calls_per_minute
        self.calls = []
    
    def wait_if_needed(self):
        """Wait if rate limit is reached"""
        now = datetime.now()
        
        # Remove calls older than 1 minute
        self.calls = [t for t in self.calls 
                     if now - t < timedelta(minutes=1)]
        
        # If limit reached, wait
        if len(self.calls) >= self.calls_per_minute:
            oldest = self.calls[0]
            wait_seconds = 60 - (now - oldest).seconds
            if wait_seconds > 0:
                time.sleep(wait_seconds + 2)  # Extra buffer
                self.calls = []  # Reset after waiting
                now = datetime.now()
        
        self.calls.append(now)

# ---------------- CONFIG ----------------
load_dotenv()

st.set_page_config(
    page_title="Kancha AI",
    page_icon="🇳🇵",
    layout="centered"
)

# ---------------- API ----------------
# Try Streamlit Cloud Secrets first (production)
API_KEY = st.secrets.get("GEMINI_API_KEY")

# Fallback to .env only for local development
if not API_KEY:
    load_dotenv()
    API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    st.error("""
    ## 🔑 API Key Configuration
    
    **For Production (Streamlit Cloud):**
    1. Go to your app at: https://share.streamlit.io/
    2. Click ⚙️ Settings → Secrets
    3. Add: `GEMINI_API_KEY = "your-actual-key"`
    
    **For Local Development:**
    1. Create `.streamlit/secrets.toml`
    2. Add: `GEMINI_API_KEY = "your-key"`
    
    Get a key from: https://makersuite.google.com/app/apikey
    """)
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
    """Send message to Gemini API with error handling and rate limiting"""
    # Apply rate limiting
    if "rate_limiter" in st.session_state:
        st.session_state.rate_limiter.wait_if_needed()
    
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
            return """**⚠️ Rate Limit Management**
            
To ensure fair usage for all users, I'm managing request limits.

**Please:**
• Wait 30-60 seconds before next message
• Use concise questions
• Try again in a few minutes

Free tier has limited requests per hour. Contact admin for higher limits."""
        
        elif "timeout" in error_message:
            return "**⏱️ Response Timeout**\n\nThe AI is taking too long. Try:\n• Shorter messages\n• Waiting a moment\n• Breaking complex questions into parts"
        
        elif "network" in error_message or "connection" in error_message:
            return "**🌐 Connection Issue**\n\nPlease check your internet connection and try again."
        
        elif "invalid" in error_message and "key" in error_message:
            return "**🔑 Configuration Issue**\n\nThere's a problem with the AI service setup. Please report this issue."
        
        else:
            return f"**❌ Unexpected Error**\n\nI encountered an issue: `{str(e)[:80]}...`\n\nPlease try rephrasing your question."

# ---------------- STATE ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])

# Initialize rate limiter
if "rate_limiter" not in st.session_state:
    st.session_state.rate_limiter = RateLimiter(calls_per_minute=8)

# ---------------- UI ----------------
st.title("Kancha AI 🇳🇵")
st.caption("Ask me anything in English or Nepali.")

# Add rate limit info to sidebar
with st.sidebar:
    st.write("**Rate Limit Status:**")
    if "rate_limiter" in st.session_state:
        calls_this_minute = len([t for t in st.session_state.rate_limiter.calls 
                               if datetime.now() - t < timedelta(minutes=1)])
        st.progress(calls_this_minute / 8, 
                   text=f"{calls_this_minute}/8 requests this minute")
    st.caption("Free tier limits apply. Please use thoughtfully.")

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
            if st.button(s, key=f"sug_{idx}", use_container_width=True):
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
if prompt := st.chat_input("Type your message in English or Nepali"):
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