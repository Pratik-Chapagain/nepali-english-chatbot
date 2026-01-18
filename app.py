import streamlit as st
import google.generativeai as genai
import os, re, time, json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ---------------- RATE LIMITER ----------------
class RateLimiter:
    """Prevent hitting API limits"""
    def __init__(self, calls_per_minute=5):
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

# ---------------- SCRIPT DETECTION ----------------
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
            response = re.sub(pattern, replacement, response)
    
    return response

# ---------------- QUERY HISTORY MANAGER ----------------
def add_to_history(query):
    """Add query to recent history (max 5)"""
    if "query_history" not in st.session_state:
        st.session_state.query_history = []
    
    # Don't add duplicates or commands
    if query not in st.session_state.query_history and not query.startswith('/'):
        st.session_state.query_history.insert(0, query)
        # Keep only last 5
        st.session_state.query_history = st.session_state.query_history[:5]

def get_history():
    """Get query history"""
    return st.session_state.get("query_history", [])

# ---------------- FAQ HANDLER ----------------
FAQ_DATABASE = {
    # English FAQs
    "what is kancha ai": {
        "en": "Kancha AI is a bilingual AI assistant designed specifically for Nepali users. I can help with questions in English, Devanagari (नेपाली), or Romanized Nepali (Nepglish). I understand Nepal's culture, education system, and daily life.",
        "ne": "Kancha AI एक bilingual AI assistant हो जुन विशेष गरी नेपाली प्रयोगकर्ताहरूको लागि design गरिएको छ। म अंग्रेजी, देवनागरी (नेपाली), वा Romanized Nepali (Nepglish) मा प्रश्नहरूको उत्तर दिन सक्छु।",
        "np": "Kancha AI Nepal ko lagi banayeko bilingual AI assistant ho. Ma English, Devanagari (नेपाली), ya Romanized Nepali (Nepglish) ma help garna sakchu."
    },
    "who made you": {
        "en": "I was created to serve the Nepali community with culturally-aware AI assistance. I'm built using Google's Gemini AI with a custom system designed for Nepali users.",
        "ne": "म नेपाली समुदायलाई culturally-aware AI assistance प्रदान गर्न बनाइएको हुँ। म Google को Gemini AI प्रयोग गरेर नेपाली प्रयोगकर्ताहरूको लागि विशेष design गरिएको छु।",
        "np": "Ma Nepali community lai help garna banayeko chu. Google ko Gemini AI use garera Nepali users ko lagi special design gareko chu."
    },
    "what can you do": {
        "en": "I can help with:\n• General questions in English/Nepali\n• Nepal-related information (education, culture, daily life)\n• Study tips and career guidance\n• Language translation\n• Summarizing text\n• Cultural explanations",
        "ne": "म यी कुरामा मद्दत गर्न सक्छु:\n• English/Nepali मा सामान्य प्रश्नहरू\n• Nepal-related जानकारी (शिक्षा, संस्कृति, दैनिक जीवन)\n• अध्ययन tips र करियर guidance\n• भाषा अनुवाद\n• Text summarize गर्न\n• सांस्कृतिक व्याख्या",
        "np": "Ma yi kura ma help garna sakchu:\n• English/Nepali ma general questions\n• Nepal-related info (education, culture, daily life)\n• Study tips ra career guidance\n• Language translation\n• Text summarize garna\n• Cultural explanations"
    },
    "see exam": {
        "en": "SEE (Secondary Education Examination) is Nepal's grade 10 board exam conducted by the National Examinations Board (NEB). It's a crucial exam that determines eligibility for higher secondary education (+2).",
        "ne": "SEE (Secondary Education Examination) नेपालको कक्षा १० को board exam हो जुन राष्ट्रिय परीक्षा बोर्ड (NEB) द्वारा सञ्चालन गरिन्छ। यो उच्च माध्यमिक शिक्षा (+2) को लागि योग्यता निर्धारण गर्ने महत्त्वपूर्ण परीक्षा हो।",
        "np": "SEE (Secondary Education Examination) Nepal ko grade 10 ko board exam ho jun National Examinations Board (NEB) le conduct garchha. Yo higher secondary education (+2) ko lagi eligibility determine garne important exam ho."
    },
    "dashain": {
        "en": "Dashain is Nepal's biggest and most important festival, celebrated for 15 days in September/October. It symbolizes the victory of good over evil and is a time for family reunions, receiving Tika and blessings from elders.",
        "ne": "दशैं नेपालको सबैभन्दा ठूलो र महत्त्वपूर्ण चाड हो, जुन सेप्टेम्बर/अक्टोबरमा १५ दिनसम्म मनाइन्छ। यसले असत्यमाथि सत्यको विजयलाई प्रतीक गर्दछ र परिवारको पुनर्मिलन, बुजुर्गहरूबाट टीका र आशीर्वाद प्राप्त गर्ने समय हो।",
        "np": "Dashain Nepal ko sabai bhanda thulo ra important festival ho, jun September/October ma 15 din samma manaincha. Yo evil over good ko victory lai symbolize garchha ani family reunion, elder haru bata Tika ra blessings paune time ho."
    },
    "ioe entrance": {
        "en": "IOE (Institute of Engineering) Entrance is the entrance exam for engineering programs at Tribhuvan University. It's highly competitive and covers Physics, Chemistry, Mathematics, and English. Students need strong preparation and typically score 35+ marks out of 100 for admission.",
        "ne": "IOE (Institute of Engineering) Entrance त्रिभुवन विश्वविद्यालयमा इन्जिनियरिङ कार्यक्रमहरूको प्रवेश परीक्षा हो। यो अत्यधिक प्रतिस्पर्धात्मक छ र Physics, Chemistry, Mathematics, र English समावेश गर्दछ। विद्यार्थीहरूलाई बलियो तयारी चाहिन्छ र सामान्यतया १०० मध्ये ३५+ अंक भर्नाको लागि आवश्यक हुन्छ।",
        "np": "IOE (Institute of Engineering) Entrance Tribhuvan University ma engineering programs ko entrance exam ho. Yo highly competitive cha ani Physics, Chemistry, Mathematics, ra English cover garchha. Students lai strong preparation chahincha ani typically 100 madhye 35+ marks admission ko lagi chahincha."
    }
}

def check_faq(query):
    """Check if query matches any FAQ"""
    query_lower = query.lower().strip()
    
    for key, answers in FAQ_DATABASE.items():
        if key in query_lower:
            script = detect_script(query)
            if script == 'devanagari':
                return answers.get('ne', answers['en'])
            elif script == 'nepglish':
                return answers.get('np', answers['en'])
            else:
                return answers['en']
    
    return None

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
    1. Go to your app settings
    2. Click ⚙️ Settings → Secrets
    3. Add: `GEMINI_API_KEY = "your-actual-key"`
    
    **For Local Development:**
    1. Create `.streamlit/secrets.toml`
    2. Add: `GEMINI_API_KEY = "your-key"`
    
    Get a key from: https://aistudio.google.com/app/apikey
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

<CRITICAL_FORMATTING_RULES>
**ALWAYS FORMAT RESPONSES WITH PROPER STRUCTURE:**

1. **Use line breaks** between different points
2. **Use numbered lists** (1), (2), (3) for multiple points
3. **Add blank lines** between sections
4. **Keep each point on NEW LINE** - NEVER write long paragraphs
5. **Maximum 2-3 sentences per point**

**CORRECT FORMAT EXAMPLE (Nepglish):**
Nepal ma students haru ko main struggles yesto chan:

(1) **Quality Education** - Dherai schools ma outdated teaching methods use huncha. Practical skills lai focus kam dincha.

(2) **Career Guidance** - Students lai proper guidance milena. Kun field choose garne bhanera confuse huncha.

(3) **Financial Problem** - Education expensive cha. Dherai lai afford garna garo huncha.

**WRONG FORMAT (Don't do this):**
Nepal ma students haru ko main struggles haru yo huna sakcha: (1) Quality of Education and Teaching Methods: Dherai thau ma traditional teaching methods use huncha, jasma rote learning lai dherai importance dincha. Practical skills development ma focus kam huncha. (2) Lack of Career Guidance: Students lai future career paths ko barema dherai jankari hunna...

**CRITICAL: Always add line breaks and proper spacing. Never write long run-on paragraphs.**
</CRITICAL_FORMATTING_RULES>

<script_detection_rules>
**DEVANAGARI MODE:**
Response format:
- Write 100% in Devanagari script
- Only exception: Technical terms (smartphone, laptop, WiFi, email, app, software, online)
- Use (१), (२), (३) for numbering
- Always add line breaks between points

**NEPGLISH MODE:**
Response format:
- 70% Romanized Nepali + 30% English
- Use (1), (2), (3) for numbering
- Always add line breaks between points

**ENGLISH MODE:**
Response format:
- 100% English
- Always add line breaks between points
</script_detection_rules>

<mandatory_rules>
1. **Never fabricate**: No fake business names, addresses, prices, phone numbers
2. **No clickable links**: No https://, http://, www.
3. **Default to "tapai"** (तपाईं): Don't assume gender
4. **Be concise**: 150-250 words max unless user requests detailed essay
5. **ALWAYS use proper formatting** with line breaks and structure
</mandatory_rules>

**CORE PRINCIPLE: Perfect script matching + Proper formatting + Honest information + Concise responses + Nepal focus**
"""

model = genai.GenerativeModel(
    "gemini-2.5-flash",
    system_instruction=SYSTEM_PROMPT
)

# ---------------- IMPROVED REPLY FUNCTION ----------------
def reply_to(prompt):
    """Send message to Gemini API with proper script detection"""
    
    # Check for special commands
    if prompt.startswith('/summarize') or prompt.startswith('/summary'):
        text_to_summarize = prompt.replace('/summarize', '').replace('/summary', '').strip()
        if not text_to_summarize:
            script = detect_script(prompt)
            if script == 'devanagari':
                return "कृपया summarize गर्नको लागि text प्रदान गर्नुहोस्। उदाहरण: /summarize [your text]"
            else:
                return "Kripaya summarize garna ko lagi text provide garnus. Example: /summarize [your text]"
        prompt = f"Please summarize this text in the same language/script: {text_to_summarize}"
    
    # Check FAQ first (instant response, no API call)
    faq_response = check_faq(prompt)
    if faq_response:
        return f"**📌 Quick Answer:**\n\n{faq_response}"
    
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
        
        # API call with timeout
        response = st.session_state.chat.send_message(
            tagged_prompt,
            request_options={"timeout": 30}
        )
        
        # Validate response before returning
        validated_response = validate_response(response.text)
        
        return validated_response
        
    except Exception as e:
        error_message = str(e).lower()
        
        # Detect script for error message
        error_script = detect_script(prompt)
        
        if "quota" in error_message or "429" in str(e):
            if error_script == 'devanagari':
                return """**⚠️ Request Limit पुग्यो**

कृपया १-२ मिनेट पर्खनुहोस्। Free tier मा limited requests छन्।

**Tips:**
• छोटो प्रश्न सोध्नुहोस्
• केही मिनेट पछि पुनः प्रयास गर्नुहोस्"""
            else:
                return """**⚠️ Request Limit Reached**

Kripaya 1-2 minute wait garnus. Free tier ma limited requests chan.

**Tips:**
• Concise questions sodhnus
• Kei minute pachi try garnus"""
        
        elif "timeout" in error_message:
            if error_script == 'devanagari':
                return "**⏱️ Response Timeout**\n\nAI लाई समय लाग्यो। छोटो message try गर्नुहोस् वा केही समय पछि फेरि सोध्नुहोस्।"
            else:
                return "**⏱️ Response Timeout**\n\nAI lai time lagyo. Shorter message try garnus ya wait garera feri sodhnus."
        
        else:
            if error_script == 'devanagari':
                return f"**❌ Error**\n\nमलाई समस्या भयो। फेरि प्रयास गर्नुहोस्।"
            else:
                return f"**❌ Error**\n\nMalai issue bhayo. Feri try garnus."

# ---------------- STATE ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])

if "rate_limiter" not in st.session_state:
    st.session_state.rate_limiter = RateLimiter(calls_per_minute=5)

if "query_history" not in st.session_state:
    st.session_state.query_history = []

st.markdown(
    """
    <style>
    .stChatInput {
        margin-top: -1.5rem;
    }
    
    /* Improve sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #f8fafc;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 0.5rem 1rem;
        font-size: 0.875rem;
    }
    
    /* Button styling for better look */
    .stButton button {
        border-radius: 8px;
        font-size: 0.875rem;
        padding: 0.5rem 1rem;
    }
    
    /* Primary button special style */
    .stButton button[kind="primary"] {
        background-color: #dc2626;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------- UI ----------------
st.markdown(
    """
    <h1 style="margin-bottom: 0.2rem;">Kancha AI</h1>
    <p style="color: #6b7280; margin-top: 0;">
    Ask me anything in English or Nepali.
    </p>
    """,
    unsafe_allow_html=True
)

# ---------------- SIDEBAR ----------------
with st.sidebar:
    # Header with branding
    st.markdown("""
        <div style="text-align: center; padding: 1rem 0; margin-bottom: 1.5rem;">
            <h2 style="margin: 0; color: #1f2937;">Kancha AI</h2>
            <p style="margin: 0; color: #6b7280; font-size: 0.875rem;">Your Nepali Assistant</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Tab navigation for better organization
    tab1, tab2, tab3 = st.tabs(["📝 Recent", "❓ Help", "⚙️ Settings"])
    
    # TAB 1: Recent Queries
    with tab1:
        history = get_history()
        if history:
            st.markdown("**Click to reuse:**")
            for i, query in enumerate(history):
                # Truncate long queries
                display_query = query[:35] + "..." if len(query) > 35 else query
                if st.button(display_query, key=f"history_{i}", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": query})
                    with st.spinner("Thinking..."):
                        reply = reply_to(query)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                    st.rerun()
        else:
            st.info("No recent queries yet. Start chatting!")
    
    # TAB 2: Help & FAQ
    with tab2:
        st.markdown("##### 💬 Quick Answers")
        st.markdown("Ask me about:")
        
        faq_buttons = [
            ("What is Kancha AI?", "what is kancha ai"),
            ("What can you do?", "what can you do"),
            ("Tell me about SEE", "see exam"),
            ("Tell me about Dashain", "dashain"),
            ("IOE entrance info", "ioe entrance")
        ]
        
        for label, query_key in faq_buttons:
            if st.button(label, key=f"faq_{query_key}", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": label})
                reply = reply_to(label)
                st.session_state.messages.append({"role": "assistant", "content": reply})
                st.rerun()
        
        st.markdown("---")
        st.markdown("##### ⌨️ Commands")
        st.code("/summarize [text]", language=None)
        st.caption("Summarize any text in your language")
        
    # TAB 3: Settings
    with tab3:
        st.markdown("##### 📊 Usage")
        if "rate_limiter" in st.session_state:
            calls_this_minute = len([t for t in st.session_state.rate_limiter.calls 
                                   if datetime.now() - t < timedelta(minutes=1)])
            st.progress(calls_this_minute / 5, text=f"{calls_this_minute}/5 requests")
            st.caption("Resets every minute")
        
        st.markdown("---")
        st.markdown("##### 🌐 Languages")
        st.markdown("""
        - 🇬🇧 English
        - 🇳🇵 नेपाली (Devanagari)
        - 🇳🇵 Nepglish (Romanized)
        """)
        
        st.markdown("---")
        if st.button("🗑️ Clear Chat", use_container_width=True, type="primary"):
            st.session_state.messages = []
            st.session_state.chat = model.start_chat(history=[])
            st.session_state.query_history = []
            st.rerun()
    
    # Footer
    st.markdown("---")
    st.caption("💡 Built for Nepali users | Free tier")

# ---------------- SUGGESTION BUTTONS ----------------
SUGGESTION_POOL = [
    # English
    "What skills are most useful for students today?",
    "How can someone improve focus while studying?",
    "What are common career mistakes students make?",
    
    # Nepglish
    "Bachelor pachi career choose kasari garne?",
    "Nepal ma students haru ko main struggle ke ho?",
    "Time management ma kasari improve garne?",
    
    # Devanagari
    "विद्यार्थीहरूले सबैभन्दा धेरै सामना गर्ने समस्या के हुन्?",
    "आत्मविश्वास कसरी बढाउने?",
    "करियर छनोट गर्दा के कुरामा ध्यान दिनुपर्छ?",
]

import random

if "suggestions" not in st.session_state:
    st.session_state.suggestions = random.sample(SUGGESTION_POOL, 4)

if not st.session_state.messages:
    st.markdown("##### 💡 Try one of these")

    cols = st.columns(2)
    for idx, s in enumerate(st.session_state.suggestions):
        with cols[idx % 2]:
            if st.button(s, key=f"sug_{idx}", use_container_width=True):
                add_to_history(s)  # Add to history
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
    
    # Add to history
    add_to_history(prompt)
    
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