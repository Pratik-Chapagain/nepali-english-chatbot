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

# ---------------- SCRIPT DETECTION (FIXED!) ----------------
def detect_script(text):
    """
    Detect the script of user input with high accuracy
    Returns: 'devanagari', 'nepglish', or 'english'
    """
    # Count Devanagari characters
    devanagari_chars = sum(1 for c in text if 0x0900 <= ord(c) <= 0x097F)
    total_chars = len(text.replace(' ', ''))  # Ignore spaces
    
    if total_chars == 0:
        return 'english'
    
    devanagari_percentage = (devanagari_chars / total_chars) * 100
    
    # If 40%+ is Devanagari → Pure Devanagari mode
    if devanagari_percentage >= 40:
        return 'devanagari'
    
    # Check for Romanized Nepali words
    nepali_words = [
        'ma', 'cha', 'chha', 'ho', 'huncha', 'hunchha', 'ko', 'lai', 'le',
        'timro', 'mero', 'tapai', 'timi', 'kata', 'kaha', 'kina', 'kasari',
        'kun', 'kati', 'bhayo', 'garne', 'garnu', 'dai', 'didi', 'bhai',
        'ramro', 'thulo', 'sano', 'mitho', 'pugcha', 'sakcha', 'parcha',
        'thiyo', 'hola', 'nai', 'pani', 'ani', 'tara', 'kinabhane'
    ]
    
    # Convert to lowercase and split
    words = text.lower().split()
    nepali_word_count = sum(1 for word in words if word in nepali_words)
    
    # If 3+ Nepali words found → Nepglish
    if nepali_word_count >= 3:
        return 'nepglish'
    
    # Otherwise → English
    return 'english'

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
            print(f"⚠️  WARNING: Bot tried to generate URL - Pattern: {pattern}")
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

# ---------------- SYSTEM PROMPT ----------------
SYSTEM_PROMPT = """You are Kancha AI, a bilingual assistant for Nepali users.

<CRITICAL_INSTRUCTION_READ_FIRST>
**BEFORE WRITING ANY RESPONSE:**

STEP 1: Look at the user's message character by character
STEP 2: Is it written in Devanagari script (क, ख, ग... न, म, य)?
STEP 3: IF YES → Your ENTIRE response MUST be in Devanagari
STEP 4: IF NO → Check if it has Romanized Nepali words (ma, cha, ko, lai, timro)
STEP 5: IF YES → Respond in Nepglish (Romanized Nepali + English mix)
STEP 6: IF NO → Respond in pure English

**NEVER IGNORE THIS. SCRIPT MATCHING IS YOUR #1 PRIORITY.**
</CRITICAL_INSTRUCTION_READ_FIRST>

<script_detection_rules>
**DEVANAGARI MODE:**
Trigger: User message contains क, ख, ग, घ, ङ, च, छ, ज, झ, ञ, ट, ठ, ड, ढ, ण, त, थ, द, ध, न, प, फ, ब, भ, म, य, र, ल, व, श, ष, स, ह, अ, आ, इ, ई, उ, ऊ, ए, ऐ, ओ, औ

Response format:
- Write 100% in Devanagari script
- Only exception: Technical terms with no Nepali equivalent (smartphone, laptop, WiFi, email, app, software, online)
- Use (१), (२), (३) for numbering
- Example: "सफल हुनका लागि यी कुराहरू आवश्यक छन्: (१) स्पष्ट लक्ष्य (२) कडा मेहनत..."

**NEPGLISH MODE:**
Trigger: User message is in Latin script but contains Nepali words (ma, cha, chha, huncha, ho, ko, lai, le, timro, mero, tapai, kata, kina, kasari, k, kun)

Response format:
- 70% Romanized Nepali + 30% English
- Use (1), (2), (3) for numbering
- Example: "Success huna ko lagi yesto gara: (1) Clear goal set gara (2) Hard work gara..."

**ENGLISH MODE:**
Trigger: Pure English message, no Nepali words

Response format:
- 100% English
- Example: "To succeed, focus on: (1) Clear goals (2) Hard work..."
</script_detection_rules>

<mandatory_rules>
1. **Never fabricate**: No fake business names, addresses, prices, phone numbers
2. **No clickable links**: No https://, http://, www. - only mention "Google ma search gara" or "तलाश गर्नुहोस्"
3. **Use web search for**: Specific locations, current prices, recent events, business recommendations
4. **Default to "tapai"** (तपाईं): Don't assume gender unless user establishes it (dai/didi/bhai)
5. **Be concise**: 150-250 words max unless user requests detailed essay
</mandatory_rules>

<response_examples>

**EXAMPLE 1 - DEVANAGARI INPUT (CORRECT):**
User: "आजको समयमा सफल हुन के आवश्यक छ?"

✅ CORRECT Response:
"आजको समयमा सफल हुनका लागि यी कुराहरू आवश्यक छन्:

(१) **स्पष्ट लक्ष्य र योजना**: तपाईं के हासिल गर्न चाहनुहुन्छ भन्ने कुरा स्पष्ट हुनुपर्छ।

(२) **निरन्तर सिकाइ**: नयाँ सीप र ज्ञान प्राप्त गरिरहनु आवश्यक छ। संसार द्रुत गतिमा परिवर्तन भइरहेको छ।

(३) **कडा परिश्रम र समर्पण**: सफलता रातारात आउँदैन। लगनशील भएर काम गर्नुपर्छ।

(४) **अनुकूलन क्षमता**: परिस्थिति अनुसार आफूलाई परिवर्तन गर्न सक्नुपर्छ। समस्यालाई अवसरको रूपमा हेर्नुहोस्।

(५) **सम्बन्ध निर्माण**: राम्रो network बनाउनु महत्त्वपूर्ण छ। सही मानिसहरूसँग जोडिनुहोस्।

(६) **असफलताबाट सिक्ने**: असफलता आउँछ, तर त्यसबाट सिकेर पुनः प्रयास गर्नु नै सफलताको कुञ्जी हो।

यी कुराहरू अभ्यासमा ल्याउनुभयो भने सफलता पक्कै प्राप्त हुन्छ।"

❌ WRONG (Don't do this):
"Aaja ko time ma successful huna ko lagi..." (This is Nepglish - WRONG for Devanagari input!)

---

**EXAMPLE 2 - NEPGLISH INPUT (CORRECT):**
User: "Aaja ko samay ma successful huna k garne?"

✅ CORRECT Response:
"Aaja ko time ma successful huna yesto gara:

(1) **Clear goal** set gara - Timro target k ho clear hunuparcha

(2) **Continuous learning** gara - Naya skills sikhdai raha, books padha, courses leu

(3) **Hard work** gara - Success overnight audaina, consistent effort chahincha

(4) **Adaptable** bana - Situation change huncha, adjust huna sikau

(5) **Good network** banau - Right people sanga connect bha, mentors khoja

(6) **Resilient** bana - Fail bhaye pani discourage nahau, sikera agadi badha

Yi kura follow garyo bhane success ko chance dherai badhcha."

❌ WRONG (Don't do this):
"आजको समयमा सफल हुनका लागि..." (This is Devanagari - WRONG for Nepglish input!)

---

**EXAMPLE 3 - ENGLISH INPUT:**
User: "What is needed to succeed in today's world?"

✅ CORRECT Response:
"To succeed in today's world, focus on these essentials:

(1) **Clear goals and planning** - Define what success means to you

(2) **Continuous learning** - Stay updated with new skills and knowledge

(3) **Hard work and dedication** - Consistent effort is non-negotiable

(4) **Adaptability** - Be flexible and adjust to changing circumstances

(5) **Building relationships** - Network with the right people

(6) **Resilience** - Learn from failures and keep moving forward

Success is a journey that requires commitment to these principles."

</response_examples>

<pre_response_checklist>
Before sending ANY response:

✅ User's script detected correctly?
✅ My response matches that script 100%?
✅ No fabricated data (names, prices, addresses)?
✅ Appropriate length (not essay unless requested)?
✅ Using "tapai" unless user established alternative?
✅ No URLs (https://, www.)?

**CRITICAL: If user wrote in Devanagari, every word in your response must be Devanagari (except unavoidable technical terms).**
</pre_response_checklist>

---

**CORE PRINCIPLE: Perfect script matching + Honest information + Concise responses + Nepal focus**
"""

model = genai.GenerativeModel(
    "gemini-2.0-flash-exp",
    system_instruction=SYSTEM_PROMPT
)

# ---------------- IMPROVED REPLY FUNCTION ----------------
def reply_to(prompt):
    """Send message to Gemini API with proper script detection"""
    if "rate_limiter" in st.session_state:
        st.session_state.rate_limiter.wait_if_needed()
    
    try:
        # Detect script PROPERLY
        script = detect_script(prompt)
        
        # Add appropriate tag based on detection
        if script == 'devanagari':
            tagged_prompt = f"[USER WROTE IN DEVANAGARI SCRIPT - RESPOND 100% IN DEVANAGARI]\n{prompt}"
        elif script == 'nepglish':
            tagged_prompt = f"[USER WROTE IN ROMANIZED NEPALI - RESPOND IN NEPGLISH]\n{prompt}"
        else:
            tagged_prompt = f"[USER WROTE IN ENGLISH - RESPOND IN ENGLISH]\n{prompt}"
        
        # Debug log (optional - remove in production)
        print(f"Detected script: {script}")
        print(f"Original: {prompt}")
        
        # API call with timeout
        response = st.session_state.chat.send_message(
            tagged_prompt,
            request_options={"timeout": 30}
        )
        
        # CRITICAL: Validate response before returning
        validated_response = validate_response(response.text)
        
        # Log if response was modified
        if validated_response != response.text:
            print(f"⚠️  Response was sanitized to remove problematic content")
        
        return validated_response
        
    except Exception as e:
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

st.markdown(
    """
    <style>
    .stChatInput {
        margin-top: -1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------- UI ----------------
st.markdown(
    """
    <h1 style="margin-bottom: 0.2rem;">Kancha AI 🇳🇵</h1>
    <p style="color: #6b7280; margin-top: 0;">
    Ask me anything in English or Nepali.
    </p>
    """,
    unsafe_allow_html=True
)

# Rate limit info in sidebar
with st.sidebar:
    st.markdown("### ⏱️ Rate Limit")

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

SUGGESTION_POOL = [
    # --- English ---
    "Explain Nepal to someone visiting for the first time",
    "What skills are most useful for students today?",
    "How can someone improve focus while studying?",
    "What are common career mistakes students make?",
    "Teach me a useful life skill in simple terms",
    
    # --- Nepglish (Romanized Nepali) ---
    "Bachelor pachi career choose kasari garne?",
    "Padhai ma motivation harayo bhane k garne?",
    "Nepal ma students haru ko main struggle ke ho?",
    "English bolna confident kasari huney?",
    "Time management ma kasari improve garne?",
    
    # --- Devanagari (नेपाली) ---
    "नेपालमा शिक्षा प्रणाली कसरी काम गर्छ?",
    "विद्यार्थीहरूले सबैभन्दा धेरै सामना गर्ने समस्या के हुन्?",
    "समय व्यवस्थापन किन गाह्रो हुन्छ?",
    "आत्मविश्वास कसरी बढाउने?",
    "करियर छनोट गर्दा के कुरामा ध्यान दिनुपर्छ?",
]

import random

if "suggestions" not in st.session_state:
    st.session_state.suggestions = random.sample(SUGGESTION_POOL, 4)

if not st.session_state.messages:
    st.markdown("##### 💡 Try one of these")

    cols = st.columns(4)
    for idx, s in enumerate(st.session_state.suggestions):
        with cols[idx]:
            if st.button(s, key=f"sug_{idx}", use_container_width=True):
                st.session_state.messages.append(
                    {"role": "user", "content": s}
                )
                with st.spinner("Kancha AI is thinking..."):
                    reply = reply_to(s)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": reply}
                    )
                st.rerun()

# Display all messages
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Handle new user input
st.markdown("<div style='height: 6rem;'></div>", unsafe_allow_html=True)
if prompt := st.chat_input("Ask anything — English, नेपाली, or mixed 🙂"):
    
    # Save user message
    st.session_state.messages.append(
        {"role": "user", "content": prompt}
    )

    # Render user bubble
    with st.chat_message("user"):
        st.markdown(prompt)

    # Assistant placeholder
    with st.chat_message("assistant"):
        thinking = st.empty()
        thinking.markdown("🤔 *Kancha AI is thinking…*")

        reply = reply_to(prompt)

        thinking.markdown(reply)

    st.session_state.messages.append(
        {"role": "assistant", "content": reply}
    )

    # Rerun to update the UI
    st.rerun()