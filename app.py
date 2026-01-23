import streamlit as st
import google.generativeai as genai
from faq_search import FAQSearcher
import os, re, time, json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import random

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
    # Remove punctuation and extra spaces
    text = text.strip()
    if not text:
        return 'english'
    
    # Count Devanagari characters
    devanagari_chars = sum(1 for c in text if 0x0900 <= ord(c) <= 0x097F)
    total_chars = len(text.replace(' ', ''))  # Ignore spaces
    
    if total_chars == 0:
        return 'english'
    
    devanagari_percentage = (devanagari_chars / total_chars) * 100
    
    # If 30%+ is Devanagari → Pure Devanagari mode
    if devanagari_percentage >= 30:
        return 'devanagari'
    
    # Check for Romanized Nepali words with better detection
    nepali_words = [
        'ma', 'cha', 'chha', 'ho', 'huncha', 'hunchha', 'ko', 'lai', 'le',
        'timro', 'mero', 'tapai', 'timi', 'kata', 'kaha', 'kina', 'kasari',
        'kun', 'kati', 'bhayo', 'garne', 'garnu', 'dai', 'didi', 'bhai',
        'ramro', 'thulo', 'sano', 'mitho', 'pugcha', 'sakcha', 'parcha',
        'thiyo', 'hola', 'nai', 'pani', 'ani', 'tara', 'kinabhane',
        'gareko', 'hunxa', 'hunna', 'rahecha', 'hudaicha', 'hudaina',
        'hune', 'cha', 'chhaina', 'garnus', 'hos', 'rahanu', 'lagcha'
    ]
    
    # Convert to lowercase and clean
    words = re.findall(r'\b\w+\b', text.lower())
    nepali_word_count = sum(1 for word in words if word in nepali_words)
    
    # If 2+ Nepali words found → Nepglish
    if nepali_word_count >= 2:
        return 'nepglish'
    
    # Otherwise → English
    return 'english'

# ---------------- RESPONSE VALIDATOR ----------------
def validate_response(response):
    """
    Prevent hallucinated URLs and problematic content from being sent
    """
    # Remove any FAQ metadata if present
    response = re.sub(r'\[FAQ Match:.*?\]', '', response)
    response = re.sub(r'\[Similarity:.*?\]', '', response)
    response = re.sub(r'\[Match.*?\]', '', response)
    
    suspicious_patterns = [
        (r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+', 
         'YouTube ma search gara: '),
        (r'https?://youtu\.be/[\w-]+', 
         'YouTube ma yo video search gara: '),
        (r'https?://[^\s]+', 
         '[External link removed - Use search instead]')
    ]
    
    for pattern, replacement in suspicious_patterns:
        response = re.sub(pattern, replacement, response)
    
    # Clean up extra whitespace
    response = re.sub(r'\n\s*\n\s*\n', '\n\n', response)  # Replace 3+ newlines with 2
    response = response.strip()
    
    return response

# ---------------- QUERY HISTORY MANAGER ----------------
def add_to_history(query):
    """Add query to recent history (max 5)"""
    if "query_history" not in st.session_state:
        st.session_state.query_history = []
    
    # Don't add duplicates or commands
    if (query not in st.session_state.query_history and 
        not query.startswith('/') and
        len(query.strip()) > 3):
        st.session_state.query_history.insert(0, query)
        # Keep only last 5
        st.session_state.query_history = st.session_state.query_history[:5]

def get_history():
    """Get query history"""
    return st.session_state.get("query_history", [])

# ---------------- FAQ HANDLER ----------------
@st.cache_resource
def load_faq_searcher():
    """Load FAQ searcher once and cache it"""
    return FAQSearcher()

faq_searcher = load_faq_searcher()

def check_faq(user_input: str) -> str:
    """
    Check FAQ using semantic search
    
    Args:
        user_input: User's message
    
    Returns:
        Clean FAQ answer or None
    """
    try:
        # Detect language for FAQ lookup
        script = detect_script(user_input)
        language_map = {
            'devanagari': 'ne',
            'nepglish': 'np',
            'english': 'en'
        }
        language = language_map.get(script, 'en')
        
        # Use semantic search
        answer = faq_searcher.get_answer(user_input, language=language, threshold=0.65)
        
        if answer:
            # Clean the response thoroughly
            cleaned_answer = re.sub(r'\[.*?\]', '', answer).strip()
            
            # Add appropriate header based on language
            if language == 'ne':
                return f"**📌 तत्काल उत्तर:**\n\n{cleaned_answer}"
            else:
                return f"**📌 Quick Answer:**\n\n{cleaned_answer}"
    
    except Exception as e:
        # If FAQ search fails, continue to AI
        print(f"FAQ search error: {e}")
    
    return None

# ---------------- CONFIG ----------------
load_dotenv()

st.set_page_config(
    page_title="Kancha AI - Nepali Assistant",
    page_icon="🇳🇵",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ---------------- API SETUP ----------------
API_KEY = st.secrets.get("GEMINI_API_KEY")

if not API_KEY:
    load_dotenv()
    API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    st.error("""
    ## 🔑 API Key Required
    
    **For Streamlit Cloud:**
    1. Go to app settings → Secrets
    2. Add: `GEMINI_API_KEY = "your-key-here"`
    
    **For Local Development:**
    1. Create `.streamlit/secrets.toml`
    2. Add: `GEMINI_API_KEY = "your-key-here"`
    
    Get your API key from: https://aistudio.google.com/app/apikey
    """)
    st.stop()

genai.configure(api_key=API_KEY)

# ---------------- IMPROVED SYSTEM PROMPT ----------------
SYSTEM_PROMPT = """You are Kancha AI, a bilingual assistant for Nepali users.

<CRITICAL_INSTRUCTION_READ_FIRST>
**BEFORE WRITING ANY RESPONSE:**

STEP 1: Analyze the user's message character by character
STEP 2: Is it written in Devanagari script (क, ख, ग... न, म, य)?
STEP 3: IF YES → Your ENTIRE response MUST be in Devanagari
STEP 4: IF NO → Check if it has Romanized Nepali words (ma, cha, ko, lai, timro, garnu)
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
6. **Use bold** for key terms and headings

**CORRECT FORMAT EXAMPLE (Nepglish):**
Nepal ma students haru ko main struggles yesto chan:

**(1) Quality Education**
Dherai schools ma outdated teaching methods use huncha. Practical skills lai focus kam dincha.

**(2) Career Guidance**
Students lai proper guidance milena. Kun field choose garne bhanera confuse huncha.

**(3) Financial Problem**
Education expensive cha. Dherai lai afford garna garo huncha.

**WRONG FORMAT (Never do this):**
Nepal ma students haru ko main struggles haru yo huna sakcha: (1) Quality of Education and Teaching Methods: Dherai thau ma traditional teaching methods use huncha, jasma rote learning lai dherai importance dincha. Practical skills development ma focus kam huncha. (2) Lack of Career Guidance: Students lai future career paths ko barema dherai jankari hunna...
</CRITICAL_FORMATTING_RULES>

<LANGUAGE_GUIDELINES>
**DEVANAGARI MODE:**
- Write 100% in Devanagari script
- Only exception: Technical terms (smartphone, laptop, WiFi, email, app, software, online)
- Use (१), (२), (३) for numbering
- Always add line breaks between points

**NEPGLISH MODE:**
- 70% Romanized Nepali + 30% English
- Use (1), (2), (3) for numbering
- Always add line breaks between points

**ENGLISH MODE:**
- 100% English
- Use (1), (2), (3) for numbering
- Always add line breaks between points
</LANGUAGE_GUIDELINES>

<MANDATORY_RULES>
1. **Never fabricate information**: No fake business names, addresses, prices, phone numbers
2. **No clickable links**: Never include https://, http://, www.
3. **Use respectful pronouns**: Default to "tapai" (तपाईं) or "you"
4. **Be concise**: 150-250 words max unless user requests detailed essay
5. **Focus on Nepal context**: Provide culturally relevant information
6. **Be helpful and supportive**: Offer practical, actionable advice
7. **Acknowledge limitations**: If you don't know something, say so honestly
</MANDATORY_RULES>

**CORE PRINCIPLE: Perfect script matching + Proper formatting + Honest information + Concise responses + Nepal focus**
"""

# Initialize the model
model = genai.GenerativeModel(
    "gemini-2.5-flash",
    system_instruction=SYSTEM_PROMPT
)

# ---------------- IMPROVED REPLY FUNCTION ----------------
def reply_to(prompt):
    """Send message to Gemini API with proper script detection"""
    
    # Check for empty or very short prompts
    if not prompt or len(prompt.strip()) < 2:
        script = detect_script("test")
        if script == 'devanagari':
            return "कृपया प्रश्न लेख्नुहोस्।"
        else:
            return "Please write your question."
    
    # Check for special commands
    if prompt.startswith('/summarize') or prompt.startswith('/summary'):
        text_to_summarize = prompt.replace('/summarize', '').replace('/summary', '').strip()
        if not text_to_summarize:
            script = detect_script(prompt)
            if script == 'devanagari':
                return "**📝 Summarize Command**\n\nकृपया summarize गर्नको लागि text प्रदान गर्नुहोस्।\n\n**उदाहरण:** /summarize [your text here]"
            else:
                return "**📝 Summarize Command**\n\nKripaya summarize garna ko lagi text provide garnus.\n\n**Example:** /summarize [your text here]"
        prompt = f"Please summarize this text in the same language/script: {text_to_summarize}"
    
    # Check FAQ first (instant response, no API call)
    faq_response = check_faq(prompt)
    if faq_response:
        return faq_response
    
    # Apply rate limiting
    if "rate_limiter" in st.session_state:
        st.session_state.rate_limiter.wait_if_needed()
    
    try:
        # Detect script for proper tagging
        script = detect_script(prompt)
        
        # Add appropriate instruction based on detected script
        if script == 'devanagari':
            tagged_prompt = f"[USER IS WRITING IN DEVANAGARI SCRIPT - YOU MUST RESPOND 100% IN DEVANAGARI]\n\nUser: {prompt}"
        elif script == 'nepglish':
            tagged_prompt = f"[USER IS WRITING IN ROMANIZED NEPALI (NEPGLISH) - YOU MUST RESPOND IN NEPGLISH]\n\nUser: {prompt}"
        else:
            tagged_prompt = f"[USER IS WRITING IN ENGLISH - YOU MUST RESPOND IN ENGLISH]\n\nUser: {prompt}"
        
        # Make API call
        response = st.session_state.chat.send_message(
            tagged_prompt,
            request_options={"timeout": 30}
        )
        
        # Validate and clean response
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

**सुझाव:**
• छोटो प्रश्न सोध्नुहोस्
• केही मिनेट पछि पुनः प्रयास गर्नुहोस्
• एकै समयमा धेरै प्रश्न नसोध्नुहोस्"""
            else:
                return """**⚠️ Request Limit Reached**

Kripaya 1-2 minute wait garnus. Free tier ma limited requests chan.

**Suggestions:**
• Ask concise questions
• Try again after a few minutes
• Don't send multiple questions at once"""
        
        elif "timeout" in error_message:
            if error_script == 'devanagari':
                return "**⏱️ Response Timeout**\n\nAI लाई समय लाग्यो। छोटो message try गर्नुहोस् वा केही समय पछि फेरि सोध्नुहोस्।"
            else:
                return "**⏱️ Response Timeout**\n\nAI lai time lagyo. Try a shorter message or ask again later."
        
        else:
            if error_script == 'devanagari':
                return f"**❌ त्रुटि भयो**\n\nकृपया फेरि प्रयास गर्नुहोस्।\n\nError details: {str(e)[:100]}..."
            else:
                return f"**❌ Error Occurred**\n\nPlease try again.\n\nError details: {str(e)[:100]}..."

# ---------------- STATE MANAGEMENT ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])

if "rate_limiter" not in st.session_state:
    st.session_state.rate_limiter = RateLimiter(calls_per_minute=5)

if "query_history" not in st.session_state:
    st.session_state.query_history = []

if "suggestions" not in st.session_state:
    st.session_state.suggestions = []

# ---------------- POLISHED & PROFESSIONAL CSS ----------------
st.markdown("""
    <style>
    /* Modern Color System */
    :root {
        --primary: #0891b2;
        --primary-hover: #0e7490;
        --accent: #3b82f6;
        --success: #10b981;
        --danger: #ef4444;
        --bg: #ffffff;
        --bg-secondary: #f8fafc;
        --bg-tertiary: #f1f5f9;
        --text: #0f172a;
        --text-secondary: #64748b;
        --text-muted: #94a3af;
        --border: #e2e8f0;
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1);
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-full: 9999px;
    }
    
    /* Global Reset */
    #MainMenu, header, footer {visibility: hidden;}
    
    * {
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    
    /* Main Layout */
    .main .block-container {
        max-width: 1100px;
        padding: 2rem 2.5rem 9rem;
    }
    
    /* ========== HEADER ========== */
    .app-header {
        text-align: center;
        padding: 2rem 0 3.5rem;
        animation: fadeInDown 0.6s ease-out;
    }
    
    @keyframes fadeInDown {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .app-header h1 {
        font-size: 3rem;
        font-weight: 800;
        color: var(--primary);
        margin-bottom: 0.75rem;
        letter-spacing: -0.02em;
        line-height: 1.2;
    }
    
    .app-header .subtitle {
        color: var(--text-secondary);
        font-size: 1.125rem;
        margin-bottom: 1.75rem;
        font-weight: 500;
    }
    
    /* Language Badges */
    .lang-badges {
        display: flex;
        gap: 0.75rem;
        justify-content: center;
        flex-wrap: wrap;
    }
    
    .lang-badge {
        background: var(--bg);
        border: 2px solid var(--border);
        padding: 0.5rem 1.25rem;
        border-radius: var(--radius-full);
        font-size: 0.9rem;
        color: var(--text-secondary);
        font-weight: 600;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: var(--shadow-sm);
    }
    
    .lang-badge:hover {
        border-color: var(--primary);
        color: var(--primary);
        background: #ecfeff;
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }
    
    /* ========== CHAT MESSAGES ========== */
    .stChatMessage {
        padding: 1.5rem;
        border-radius: var(--radius-lg);
        margin-bottom: 1.5rem;
        box-shadow: var(--shadow);
        animation: slideUp 0.3s ease-out;
        width: 100%;
    }
    
    @keyframes slideUp {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    [data-testid="stChatMessageUser"] {
        background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
        border-left: 4px solid var(--accent);
        color: var(--text);
    }
    
    [data-testid="stChatMessageAssistant"] {
        background: var(--bg-secondary);
        border-left: 4px solid var(--primary);
        color: var(--text);
    }
    
    .stChatMessage p {
        color: var(--text);
        line-height: 1.7;
        margin: 0;
    }
    
    /* ========== CHAT INPUT ========== */
    .stChatInput {
        position: fixed;
        bottom: 0;
        left: 21rem;
        right: 0;
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        padding: 1.5rem 2.5rem;
        border-top: 1px solid var(--border);
        box-shadow: 0 -10px 25px -5px rgba(0, 0, 0, 0.1);
        z-index: 999;
    }
    
    .stChatInput input {
        border-radius: var(--radius-full);
        border: 2px solid var(--border);
        padding: 1rem 1.75rem;
        font-size: 1rem;
        transition: all 0.2s ease;
        box-shadow: var(--shadow-sm);
        background: var(--bg);
    }
    
    .stChatInput input:focus {
        border-color: var(--primary);
        box-shadow: 0 0 0 4px rgba(8, 145, 178, 0.1);
        outline: none;
    }
    
    .stChatInput input::placeholder {
        color: var(--text-muted);
    }
    
    /* ========== SIDEBAR ========== */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f0f9ff 0%, var(--bg-secondary) 100%);
        border-right: 1px solid var(--border);
        position: fixed;
        left: 0;
        top: 0;
        bottom: 0;
        width: 21rem;
        overflow-y: auto;
        z-index: 1000;
    }
    
    [data-testid="stSidebar"] > div:first-child {
        padding: 1rem 1rem 1.5rem;
    }
    
    /* Sidebar Branding */
    [data-testid="stSidebar"] h2 {
        color: var(--primary) !important;
        font-weight: 800 !important;
        font-size: 1.5rem !important;
    }
    
    /* Sidebar Buttons */
    [data-testid="stSidebar"] .stButton button {
        width: 100%;
        border-radius: var(--radius-sm);
        padding: 0.875rem 1rem;
        margin-bottom: 0.5rem;
        border: 1.5px solid var(--border);
        background: var(--bg);
        text-align: left;
        font-weight: 500;
        font-size: 0.9rem;
        color: var(--text);
        transition: all 0.15s ease;
        box-shadow: var(--shadow-sm);
    }
    
    [data-testid="stSidebar"] .stButton button:hover {
        border-color: var(--primary);
        background: #f0f9ff;
        transform: translateX(4px);
        box-shadow: var(--shadow);
    }
    
    [data-testid="stSidebar"] .stButton button:active {
        transform: translateX(4px) scale(0.98);
    }
    
    /* Clear Chat Button */
    [data-testid="stSidebar"] .stButton button[kind="primary"] {
        background: linear-gradient(135deg, var(--danger) 0%, #dc2626 100%);
        color: white;
        border: none;
        font-weight: 600;
        box-shadow: var(--shadow);
    }
    
    [data-testid="stSidebar"] .stButton button[kind="primary"]:hover {
        background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }
    
    /* Info Boxes */
    [data-testid="stSidebar"] .stAlert {
        border-radius: var(--radius-sm);
        border-left: 4px solid var(--primary);
        background: #f0f9ff;
        padding: 1rem;
        font-size: 0.9rem;
        box-shadow: var(--shadow-sm);
    }
    
    /* Progress Bar */
    [data-testid="stSidebar"] .stProgress > div > div > div > div {
        background: linear-gradient(90deg, var(--primary) 0%, #06b6d4 100%);
        border-radius: var(--radius-sm);
    }
    
    /* Captions */
    [data-testid="stSidebar"] .stCaption {
        color: var(--text-secondary);
        font-size: 0.85rem;
        line-height: 1.5;
    }
    
    /* Dividers */
    [data-testid="stSidebar"] hr {
        margin: 1rem 0;
        border: none;
        border-top: 1px solid var(--border);
    }
    
    /* Markdown in Sidebar */
    [data-testid="stSidebar"] ul {
        padding-left: 1rem;
        line-height: 1.8;
    }
    
    [data-testid="stSidebar"] li {
        margin-bottom: 0.375rem;
        color: var(--text);
    }
    
    /* ========== TABS ========== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.25rem;
        background: var(--bg-tertiary);
        border-radius: var(--radius-sm);
        padding: 0.25rem;
        border: none;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 0.625rem 1rem;
        border: none;
        background: transparent;
        color: var(--text-secondary);
        font-weight: 600;
        font-size: 0.9rem;
        transition: all 0.15s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255, 255, 255, 0.5);
        color: var(--text);
    }
    
    .stTabs [aria-selected="true"] {
        background: var(--primary);
        color: white;
        box-shadow: var(--shadow-sm);
    }
    
    /* ========== SCROLLBAR ========== */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--bg-secondary);
        border-radius: var(--radius-sm);
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--border);
        border-radius: var(--radius-sm);
        transition: background 0.2s ease;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-muted);
    }
    
    /* ========== RESPONSIVE ========== */
    @media (max-width: 768px) {
        .main .block-container {
            padding: 1rem 1rem 7rem;
        }
        
        .app-header h1 {
            font-size: 2.25rem;
        }
        
        .app-header .subtitle {
            font-size: 1rem;
        }
        
        .stChatInput {
            left: 0;
            padding: 1rem 1rem 1.25rem;
        }
        
        [data-testid="stSidebar"] {
            width: 16rem;
        }
        
        .lang-badge {
            padding: 0.4rem 1rem;
            font-size: 0.85rem;
        }
    }
    </style>
""", unsafe_allow_html=True)

# ---------------- POLISHED HEADER ----------------
st.markdown("""
    <div class="app-header">
        <h1>😊 Kancha AI</h1>
        <p class="subtitle">Your intelligent Nepali assistant</p>
        <div class="lang-badges">
            <div class="lang-badge">English</div>
            <div class="lang-badge">नेपाली</div>
            <div class="lang-badge">🌐 Nepglish</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# ---------------- IMPROVED SIDEBAR ----------------
with st.sidebar:
    # Branding with better styling
    st.markdown("""
        <div style="text-align: center; padding: 0.75rem 0 1.5rem;">
            <h2 style="margin: 0; color: #0891b2; font-weight: 800;">😊 Kancha AI</h2>
            <p style="margin: 0.5rem 0 0; color: #64748b; font-size: 0.9rem; font-weight: 500;">
                Smart Assistant for Nepali Users
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📝 Recent", "❓ FAQ", "ℹ️ Info"])
    
    # ========== RECENT QUERIES ==========
    with tab1:
        history = get_history()
        
        if history:
            st.markdown("**💭 Your Recent Questions**")
            st.caption("Click to ask again")
            st.markdown("")
            
            for i, query in enumerate(history):
                display_query = query[:40] + "..." if len(query) > 40 else query
                if st.button(display_query, key=f"history_{i}", use_container_width=True):
                    add_to_history(query)
                    st.session_state.messages.append({"role": "user", "content": query})
                    with st.spinner("🤔 Thinking..."):
                        reply = reply_to(query)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                    st.rerun()
        else:
            st.info("📭 No recent queries\n\nYour chat history will appear here")
    
    # ========== FAQ ==========
    with tab2:
        st.markdown("**🎯 Quick Access**")
        st.caption("Popular questions")
        st.markdown("")
        
        faqs = [
            ("What is Kancha AI?", "about"),
            ("SEE exam information", "see"),
            ("Dashain festival explained", "dashain"),
            ("IOE entrance guide", "ioe"),
            ("Study tips & techniques", "study"),
            ("Career guidance", "career"),
            ("How can you help me?", "help")
        ]
        
        for label, key in faqs:
            if st.button(label, key=f"faq_{key}", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": label})
                with st.spinner("🤔 Thinking..."):
                    reply = reply_to(label)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                st.rerun()
    
    # ========== INFO ==========
    with tab3:
        # Usage Status
        st.markdown("**📊 Usage**")
        if "rate_limiter" in st.session_state:
            calls = len([t for t in st.session_state.rate_limiter.calls 
                        if datetime.now() - t < timedelta(minutes=1)])
            st.progress(min(1.0, calls / 5), text=f"**{calls}/5** requests")
            st.caption("⏱️ Resets every minute")
        
        st.divider()
        
        # Languages
        st.markdown("**🌐 Supported Languages**")
        st.markdown("• English — Full support\n• नेपाली — Native Devanagari\n• Nepglish — Roman-Nepali mix")
        
        st.divider()
        
        # Features
        st.markdown("**✨ Key Features**")
        st.markdown("• Instant answers\n• Nepal-specific info\n• Education & career help\n• Cultural explanations")
    
    # CLEAR CHAT - Always at bottom
    st.divider()
    if st.button("🗑️ Clear All Chats", use_container_width=True, type="primary"):
        st.session_state.messages = []
        st.session_state.chat = model.start_chat(history=[])
        st.session_state.query_history = []
        st.success("✅ Chat cleared!")
        time.sleep(0.5)
        st.rerun()
    
    # Footer
    st.markdown("")
    st.caption("Made with ❤️ for Nepali users\nPowered by Gemini AI")

# ---------------- SUGGESTION BUTTONS ----------------
SUGGESTION_POOL = [
    # English
    "What skills are most useful for students today?",
    "How can I improve my focus while studying?",
    "What are common career mistakes students make?",
    "How to prepare for SEE exam effectively?",
    
    # Nepglish
    "Bachelor pachi career choose kasari garne?",
    "Nepal ma students haru ko main struggle ke ho?",
    "Time management ma kasari improve garne?",
    "IOE entrance ko lagi kasari prepare garne?",
    
    # Devanagari
    "विद्यार्थीहरूले सबैभन्दा धेरै सामना गर्ने समस्या के हुन्?",
    "आत्मविश्वास कसरी बढाउने?",
    "करियर छनोट गर्दा के कुरामा ध्यान दिनुपर्छ?",
    "पढाइमा मन लाग्ने गरी कसरी अध्ययन गर्ने?",
]

# Initialize suggestions if empty
if not st.session_state.suggestions:
    st.session_state.suggestions = random.sample(SUGGESTION_POOL, 6)

# Show suggestions only if no messages yet
if not st.session_state.messages:
    st.markdown("### 💡 Try asking...")
    
    cols = st.columns(2)
    for idx, suggestion in enumerate(st.session_state.suggestions):
        with cols[idx % 2]:
            if st.button(suggestion, key=f"sug_{idx}", use_container_width=True):
                add_to_history(suggestion)
                st.session_state.messages.append(
                    {"role": "user", "content": suggestion}
                )
                with st.spinner("Kancha AI is thinking..."):
                    reply = reply_to(suggestion)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": reply}
                    )
                st.rerun()
    
    # Refresh suggestions button
    if st.button("🔄 Show different suggestions", use_container_width=True):
        st.session_state.suggestions = random.sample(SUGGESTION_POOL, 6)
        st.rerun()

# ---------------- CHAT HISTORY DISPLAY ----------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ---------------- CHAT INPUT ----------------
# Add some space at the bottom for the fixed chat input
st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)

if prompt := st.chat_input("Type your question here...", key="chat_input"):
    # Add to history
    add_to_history(prompt)
    
    # Save user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message immediately
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate assistant response
    with st.chat_message("assistant"):
        with st.spinner("🤔 Thinking..."):
            reply = reply_to(prompt)
            st.markdown(reply)
    
    # Save assistant response
    st.session_state.messages.append({"role": "assistant", "content": reply})
    
    # Rerun to update UI
    st.rerun()