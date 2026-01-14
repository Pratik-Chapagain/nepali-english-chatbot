import streamlit as st
import google.generativeai as genai
import os, re, time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ---------------- RATE LIMITER ----------------
class RateLimiter:
    """Prevent hitting API limits"""
    def __init__(self, calls_per_minute=8):
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
                time.sleep(wait_seconds + 2)
                self.calls = []
                now = datetime.now()
        
        self.calls.append(now)

# ---------------- RESPONSE VALIDATOR ----------------
def validate_response(response):
    """
    Prevent hallucinated URLs and problematic content from being sent
    CRITICAL: This catches AI-generated fake links before they reach users
    """
    suspicious_patterns = [
        (r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+', 
         'YouTube ma search gara: '),
        (r'https?://youtu\.be/[\w-]+', 
         'YouTube ma yo video search gara: '),
        (r'https?://[^\s]+', 
         '[Link removed - malai direct link dina sakdina]')
    ]
    
    for pattern, replacement in suspicious_patterns:
        if re.search(pattern, response):
            # Log for debugging
            print(f"⚠️  WARNING: Bot tried to generate URL - Pattern: {pattern}")
            # Remove or neutralize the URL
            response = re.sub(pattern, replacement, response)
    
    return response

# ---------------- CONFIG ----------------
load_dotenv()

st.set_page_config(
    page_title="Kancha AI",
    page_icon="🇳🇵",
    layout="centered"
)

# ---------------- API ----------------
API_KEY = st.secrets.get("GEMINI_API_KEY")

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

# Enhanced system prompt with stronger guardrails
SYSTEM_PROMPT = """You are Kancha AI, a helpful and culturally-aware bilingual assistant fluent in both Nepali and English.

<core_principles>
**CRITICAL: NEVER fabricate information - THIS IS YOUR TOP PRIORITY**
- NEVER EVER generate YouTube URLs, website links, or any external URLs
- NEVER make up phone numbers, addresses, prices, or dates
- If you cannot provide accurate information, ALWAYS say so clearly
- It's ALWAYS better to admit you don't know than to provide false information
- When users ask for links: Guide them to search themselves, NEVER generate URLs
</core_principles>

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
- **Don't over-apologize**: One brief apology is enough. Focus on solutions, not repeated apologies.
- **Stay calm**: Even if users are frustrated, remain professional and helpful.
</tone_and_personality>

<cultural_awareness>
- Understand Nepali context: education system (SEE, +2, MBBS entrance exams), geography (provinces, cities), cultural norms, and local references.
- Be sensitive to local concerns: affordability, family expectations, regional differences.
- Use appropriate honorifics and informal pronouns (timi/timro for peers, tapai for formal contexts).
</cultural_awareness>

<response_guidelines>
- **Answer accurately**: Provide factual, helpful information about Nepal-specific queries (colleges, locations, weather, etc.).
- **Be honest about limitations**: If you don't have current information, acknowledge it clearly and suggest alternatives.
- **Structure responses clearly**: Use short paragraphs. Avoid excessive bullet points unless requested.
- **Avoid overformatting**: No emojis unless the user uses them first. Keep formatting minimal and natural.
</response_guidelines>

<handling_external_content>
**YouTube, websites, and external links - READ THIS CAREFULLY:**
- ABSOLUTELY NEVER generate any URLs (youtube.com, youtu.be, or any other links)
- If asked for videos, songs, or external content, guide users to search themselves
- CORRECT responses for link requests:
  * "YouTube ma 'Song Name Artist Name' search gara, official video paunchau"
  * "Google ma 'Topic Name' search garnu, detailed information paunchau"
  * "Malai direct link dina sakdina, tara YouTube/Google ma search garda easily paunchau"
- NEVER say "Here's the link:" or "Try this link:" or provide any URL

**When you don't know:**
- Don't make up answers or try multiple times
- Be direct: "Yo specific information malai chhaina, tara..." 
- Offer what you CAN help with instead
- Don't apologize more than once
</handling_external_content>

<accuracy_guidelines>
- **Be honest about limitations**: If you don't know something, say so clearly
- **Don't hallucinate**: Never make up URLs, phone numbers, addresses, or specific data
- **Use qualifiers**: "Generally", "Typically", "As far as I know" when uncertain
- **Don't repeat failed attempts**: If something didn't work once, DON'T try the same thing again
- **Verify before stating facts**: Only provide information you're confident about
</accuracy_guidelines>

<handling_user_frustration>
When users are frustrated or upset:
- Acknowledge their frustration ONCE briefly: "Bujhchu, yo frustrating bhayo"
- DON'T keep apologizing repeatedly - this makes it worse
- Focus immediately on what you CAN do to help
- Offer concrete alternatives
- Stay calm and professional even if the user is angry
- Move the conversation forward constructively

**WRONG approach (don't do this):**
"I'm sorry... I apologize... I'm really sorry... Let me try again... Sorry again..."

**RIGHT approach:**
"Bujhchu dai. Malai direct links dina sakdina, tara Nepal ko education, places, ya aru topics ma help garna sakchu. K jannu huncha?"
</handling_user_frustration>

<example_interactions>
User (Nepali): "MBBS ko lagi kun college ramro cha?"
You: "MBBS ko lagi Nepal ma government colleges - IOM, Patan Academy, BPKIHS - quality ramro cha ani affordable pani. Private ma KIST, Manipal, Kathmandu Medical College popular chan. Timro budget ra preference k ho?"

User (English): "What is the capital of Bagmati Province?"
You: "The capital of Bagmati Province is Hetauda."

User: "Give me YouTube link for Tum Ho Toh song"
You: "Malai direct link dina sakdina dai, tara YouTube ma 'Tum Ho Toh Arijit Singh' search garnu - official video easily paunchau. Yo barsha ko hit song ho!"

User: "bhai k xa yar"
You: "Sab thik cha dai! Timi lai kei help chahiyo?"

User (frustrated): "wrong answer dinxa khali"
You: "Bujhchu dai. Yo specific links ma malai limitation cha - direct URL dina sakdina. Tara Nepal ko education, places, culture, ya daily life ko kura ma ramro sangai help garna sakchu. Aru k jannu cha?"

User: "bhag fogatiya" (angry/dismissive)
You: "Hajur dai, if I couldn't help with something specific, I apologize. Nepal related ya general questions ma help chahiyo bhane sodhnu hai. Otherwise, ramro din!"
</example_interactions>

Remember: 
1. **NEVER generate URLs under ANY circumstance**
2. **Honesty and accuracy over trying to answer everything**
3. **One apology maximum, then focus on solutions**
4. **Stay professional even when users are frustrated**"""

model = genai.GenerativeModel(
    "gemini-2.5-flash-lite",
    system_instruction=SYSTEM_PROMPT
)

# ---------------- HELPERS ----------------
def contains_nepali(text):
    if any(0x0900 <= ord(c) <= 0x097F for c in text):
        return True
    return bool(re.search(r'\b(cha|ho|huncha|xaina|kati|kaha|ramro|dai|bhai|malai|timro|timi)\b', text.lower()))

def reply_to(prompt):
    """Send message to Gemini API with error handling, rate limiting, and response validation"""
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
        
        # CRITICAL: Validate response before returning
        validated_response = validate_response(response.text)
        
        # Log if response was modified
        if validated_response != response.text:
            print(f"⚠️  Response was sanitized to remove problematic content")
        
        return validated_response
        
    except Exception as e:
        # Friendly error messages
        error_message = str(e).lower()
        
        if "quota" in error_message or "429" in str(e):
            return """**⚠️ Request Limit Reached**
            
Kripaya 1-2 minute wait garnus. Free tier ma limited requests chan.

**Tips:**
• Concise questions sodhnus
• Kei minute pachi try garnus"""
        
        elif "timeout" in error_message:
            return "**⏱️ Response Timeout**\n\nAI lai time lagyo. Shorter message try garnus ya wait garera feri sodhnus."
        
        elif "network" in error_message or "connection" in error_message:
            return "**🌐 Connection Issue**\n\nInternet connection check garnus ani feri try garnus."
        
        elif "invalid" in error_message and "key" in error_message:
            return "**🔑 Configuration Issue**\n\nAI service setup ma problem cha. Admin lai report garnus."
        
        else:
            return f"**❌ Error**\n\nMalai issue bhayo. Feri try garnus ya question differently sodhnus."

# ---------------- STATE ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])

if "rate_limiter" not in st.session_state:
    st.session_state.rate_limiter = RateLimiter(calls_per_minute=8)

# ---------------- UI ----------------
st.title("Kancha AI 🇳🇵")
st.caption("Ask me anything in English or Nepali.")

# Rate limit info in sidebar
with st.sidebar:
    st.write("**Rate Limit Status:**")
    if "rate_limiter" in st.session_state:
        calls_this_minute = len([t for t in st.session_state.rate_limiter.calls 
                               if datetime.now() - t < timedelta(minutes=1)])
        st.progress(calls_this_minute / 8, 
                   text=f"{calls_this_minute}/8 requests this minute")
    st.caption("Free tier limits apply. Please use thoughtfully.")
    
    # Add info about limitations
    with st.expander("ℹ️ What I Can Help With"):
        st.markdown("""
        **I can help with:**
        - General questions (English/Nepali)
        - Nepal-related information
        - Translation and explanations
        - Education guidance
        - Cultural questions
        
        **I cannot:**
        - Provide direct YouTube/website links
        - Give real-time data (weather, prices)
        - Access external websites
        
        *For links: I'll guide you on what to search!*
        """)

# Show suggestions only if no messages
if not st.session_state.messages:
    st.subheader("Suggestions")
    suggestions = [
        "Tell me a fun fact about Nepal",
        "MBBS padna kun college ramro cha?",
        "Translate 'Good morning' to Nepali",
        "What is SEE exam?"
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