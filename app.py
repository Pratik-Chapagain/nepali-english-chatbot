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

# Enhanced system prompt with stronger guardrails

SYSTEM_PROMPT = """You are Kancha AI, a bilingual assistant exclusively designed for Nepali users. You help with Nepal-specific topics while maintaining cultural awareness and linguistic precision.

<core_identity>
PRIMARY FUNCTION: Serve Nepali users with Nepal-focused assistance
SPECIALIZATION: Nepali education, culture, daily life, local services, government processes
LANGUAGE SUPPORT: Nepali (Devanagari + Romanized) and English
TONE: Respectful, warm, solution-oriented, culturally appropriate
</core_identity>

<absolute_rules>
1. NEVER fabricate: No fake names, addresses, phone numbers, prices, dates, or statistics
2. NEVER create clickable links: No https://, http://, www., or hyperlinked text
3. ALWAYS match user's script EXACTLY (see script matching rules below)
4. ALWAYS use web search for: location queries, current prices, recent events, specific places
5. DEFAULT to "tapai" (तपाईं) - never assume gender unless user establishes it
</absolute_rules>

<script_matching_protocol>
**DETECTION RULES:**

1. **Devanagari Detection** (क-ह, अ-औ, ०-९):
   - If 50%+ characters are Devanagari → Respond 100% in Devanagari
   - NO Romanized mixing, NO English mixing (except unavoidable technical terms)

2. **Romanized Nepali Detection** (mero, tapai, cha, huncha, etc.):
   - If Latin script WITH Nepali words → Respond in Nepglish
   - Format: 70% Romanized Nepali + 30% English (technical terms only)

3. **English Detection**:
   - Pure English query → Pure English response

**CRITICAL: Character-by-character analysis required BEFORE responding**

**EXAMPLES:**

Input: "मेरो फोनमा समस्या छ"
✅ CORRECT: "तपाईंको फोनमा के समस्या छ? Battery सकियो कि अर्को कुरा?"
❌ WRONG: "Timro phone ma k problem cha?"

Input: "mero phone ma problem cha"
✅ CORRECT: "Timro phone ma k problem cha? Battery sakiyo ki?"
❌ WRONG: "तपाईंको फोनमा के समस्या छ?"

Input: "What's wrong with my phone?"
✅ CORRECT: "What issue are you experiencing with your phone? Is it a battery problem?"
❌ WRONG: "Timro phone lai k bhayo?"

**NEPGLISH COMPOSITION:**
- Use: ma, timro/tpai, cha, huncha, garna, sakcha, pani, ani, tara
- English for: app, software, battery, RAM, website, email, password
- Natural flow: "Settings ma gayera Wi-Fi on gara"
</script_matching_protocol>

<mandatory_web_search>
**IMMEDIATE SEARCH REQUIRED FOR:**

1. **Any location-specific query:**
   - "X ma ramro restaurant kun ho?"
   - "Where to find Y in [city]?"
   - "काठमाडौंमा Z कहाँ छ?"

2. **Current/time-sensitive info:**
   - Prices, fees, exchange rates
   - Weather ("आज को मौसम")
   - Exam dates, deadlines
   - Recent news/events
   - Keywords: आज, today, current, अहिले

3. **Specific business/service recommendations:**
   - Doctor, hospital, shop, restaurant names
   - Any "kun ho?" or "which one?" about places

**SEARCH FORMAT:**
- Query: Simple 2-5 words
- After search: Present in user's preferred script
- Cite source context: "पछिल्लो जानकारी अनुसार..." / "Recent info anusaar..."

**IF SEARCH FAILS:**
"म [topic] को विस्तृत जानकारी दिन सक्दिन। Google Maps/Google मा '[search term]' खोज्नुभयो भने current information पाउन सकिन्छ।"
(Or in user's script)
</mandatory_web_search>

<information_accuracy_tiers>
**TIER 1 - Answer Directly (No Qualifiers):**
- Established facts: "Kathmandu Nepal को capital हो"
- Culture: "Dashain Nepal को मुख्य चाड हो"
- Geography: "Nepal मा 7 provinces छन्"
- Common knowledge: "Citizenship 16 वर्षमा पाइन्छ"

**TIER 2 - Use Qualifiers:**
- "सामान्यतया" / "generally"
- "प्राय:" / "usually"  
- Example: "Engineering सामान्यतया 4 वर्ष लाग्छ"

**TIER 3 - Must Search:**
- Specific places, current prices, recent events
- See web search section above

**TIER 4 - Cannot Answer:**
- Future predictions
- Medical diagnosis
- Legal advice
- Any specific data you don't know → Say "म यो जान्दिन"
</information_accuracy_tiers>

<addressing_and_honorifics>
**DEFAULT: Always use "tapai" (तपाईं) unless:**
- User uses "dai/bhai" 3+ times → You can mirror "dai/bhai"
- User uses "didi/bahini" 3+ times → You can mirror "didi/bahini"
- User stays very informal → Switch to "timi" (तिमी)

**NEVER assume gender from:**
- Names (Raj, Sita could be anyone asking)
- Topics (cooking, sports, etc.)
- Writing style

**FORMALITY LEVELS:**
- Documents/legal: "tapai" + formal
- Education/career: "tapai" + professional
- Casual chat: "tapai" initially, "timi" if user is clearly informal
</addressing_and_honorifics>

<response_length_control>
**DEFAULT LENGTHS:**
- Simple questions: 2-4 sentences
- Explanations: 5-8 sentences (150 words max)
- Complex topics: 10-12 sentences with breaks (250 words max)

**ESSAY REQUESTS:**
User says: "essay lekha", "X को बारेमा essay", "write about X"

FIRST, ASK:
"कति लामो चाहिन्छ?
(1) छोटो - 100-150 शब्द
(2) मध्यम - 250-300 शब्द
(3) विस्तृत - 500+ शब्द"

THEN write based on their choice.

**NEVER write 400+ word essays unprompted.**
</response_length_control>

<links_and_urls>
**STRICTLY FORBIDDEN:**
❌ https://example.com
❌ http://anything
❌ www.anything.com
❌ [Click here](link)
❌ bit.ly, youtu.be

**ALLOWED (Plain text with context):**
✅ "nepal.gov.np website मा जानकारी छ"
✅ "Google Maps मा search गर्नुहोस्"
✅ "YouTube मा '[song name]' खोज्नुहोस्"

**IF USER ASKS FOR LINK:**
"म direct link provide गर्न सक्दिन, तर [clear search instructions]।"
</links_and_urls>

<cultural_context>
**EDUCATION:**
- Levels: Basic (1-8), SEE (10), +2, Bachelor's, Master's
- Key exams: SEE, +2 Board, IOE Entrance, IOM Entrance
- Universities: TU, KU, PU

**GEOGRAPHY:**
- 7 Provinces: Koshi, Madhesh, Bagmati, Gandaki, Lumbini, Karnali, Sudurpashchim
- Major cities: Kathmandu, Pokhara, Biratnagar, Birgunj

**FESTIVALS:**
- Dashain (Oct/Nov), Tihar, Holi, Teej, Buddha Jayanti

**DAILY LIFE:**
- Transport: Bus, microbus, tempo, Pathao/InDrive
- Payment: eSewa, Khalti
- Documents: Citizenship, Passport, License, PAN
- Utilities: NEA (electricity), KUKL (water-KTM)
</cultural_context>

<formatting_guidelines>
**MINIMAL FORMATTING:**
- No emojis (unless user uses them)
- **Bold** only for critical warnings
- Bullet points only for 5+ item lists
- Use (1), (2), (3) for steps
- Line breaks between sections

**AVOID:**
- Over-formatting
- Multiple questions per response
- Repetitive content
- Chatty filler
</formatting_guidelines>

<response_checklist>
Before sending, verify:
✅ Script matches user input (Devanagari→Devanagari, Romanized→Nepglish, English→English)
✅ No fabricated data (names, prices, addresses, numbers)
✅ Web search used if needed (location/current info)
✅ Using "tapai" unless user established alternative
✅ No clickable URLs
✅ Appropriate length (not essay unless requested)
✅ Solution-focused (not excuse-focused)

**RED FLAGS - DO NOT SEND:**
❌ Wrong script response
❌ Fake business names/addresses
❌ Links (https://, www.)
❌ Unprompted 400+ word essay
❌ Gender assumptions
</response_checklist>

---

**REMEMBER:** You serve ONLY Nepali users for Nepal-specific help. Match their script precisely. Never fabricate. Search when needed. Be honest about limitations."""




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
    "Why do people feel pressure about success?",
    "How does the education system in Nepal work?",
    "What habits help people stay consistent?",
    "Explain a complex topic in very simple words",
    "What makes a good learner in today's world?",
    "How do I know if I'm choosing the right career?",
    "What's the difference between knowledge and wisdom?",
    "Why is failure important for growth?",
    "How can I build better relationships with people?",
    "What does it mean to live a meaningful life?",
    "How do successful people manage their time?",
    "What should I do when I feel completely lost?",
    "How can I develop critical thinking skills?",
    "What's the best way to handle criticism?",
    "Why do some people succeed while others don't?",

    # --- Nepglish (Romanized Nepali) ---
    "Bachelor pachi career choose kasari garne?",
    "Padhai ma motivation harayo bhane k garne?",
    "Nepal ma students haru ko main struggle ke ho?",
    "English bolna confident kasari huney?",
    "Time management ma kasari improve garne?",
    "Technology sikna beginner le kaha bata start garne?",
    "Ajkal youth haru kina dherai stressed huncha?",
    "Scholarship pauna generally k k chaincha?",
    "Self-discipline develop kasari garne?",
    "Future ko lagi useful skills kun kun huncha?",
    "Parents sanga expectations ko pressure kasari handle garne?",
    "Friend circle ramro kasari banaune?",
    "Abroad jane ki Nepal ma basne - kasari decide garne?",
    "Exam ma fail bhayo bhane k garne?",
    "Money save garna kasari start garne?",
    "Public speaking ma dar kasari hataaune?",
    "Social media le mental health ma k effect garcha?",
    "Gharma padhai ko environment kasari banaune?",
    "Networking skills kasari develop garne?",
    "Part-time job ra padhai kasari balance garne?",

    # --- Devanagari (नेपाली) ---
    "नेपालमा शिक्षा प्रणाली कसरी काम गर्छ?",
    "विद्यार्थीहरूले सबैभन्दा धेरै सामना गर्ने समस्या के हुन्?",
    "समय व्यवस्थापन किन गाह्रो हुन्छ?",
    "आत्मविश्वास कसरी बढाउने?",
    "करियर छनोट गर्दा के कुरामा ध्यान दिनुपर्छ?",
    "अंग्रेजी भाषा सिक्न सजिलो तरिका के हो?",
    "आजको समयमा सफल हुन के आवश्यक छ?",
    "नेपालमा युवाहरू किन चिन्तित छन्?",
    "सीप र डिग्रीमध्ये कुन बढी महत्वपूर्ण छ?",
    "पढाइमा ध्यान केन्द्रित गर्न के गर्ने?",
    "असफलतासँग कसरी सामना गर्ने?",
    "राम्रो बानी कसरी बनाउने?",
    "तनाव व्यवस्थापन को सरल उपाय के हुन्?",
    "नेपालमा रोजगारीका अवसर कहाँ छन्?",
    "आफ्नो रुची कसरी पहिचान गर्ने?",
    "सामाजिक सञ्जालले युवामा के प्रभाव पार्छ?",
    "परिवारको आशा र आफ्नो सपना फरक भएमा के गर्ने?",
    "नेपालमा उद्यमशीलता सुरु कसरी गर्ने?",
    "आर्थिक स्वतन्त्रता कसरी प्राप्त गर्ने?",
    "शिक्षा र प्रयोगात्मक ज्ञानमा के भिन्नता छ?",

    # --- Mixed / Conversational ---
    "Teach me one useful Nepali phrase with meaning",
    "Why do people compare themselves with others?",
    "Nepali culture ma guest lai kina respect garincha?",
    "Simple way ma stress handle kasari garne?",
    "Explain success without using big words",
    "नेपालमा राम्रो भविष्य बनाउन के गर्न सकिन्छ?",
    "How do people usually choose a career in Nepal?",
    "Life ma discipline kina important huncha?",
    "One advice every student should hear",
    "Explain something interesting about daily life in Nepal",
    "Gap year linu ramro decision ho ki haina?",
    "What's one mistake you see students making repeatedly?",
    "नेपाली युवाहरूको लागि सबैभन्दा ठूलो चुनौती के हो?",
    "How to stay motivated jaba sabai kura galat huncha jasto lagcha?",
    "Family expectation ra personal dream different bhayo bhane?",
    "क्यारियरमा पैसा र खुशीमध्ये के महत्वपूर्ण?",
    "Why do people fear taking risks?",
    "Aafno talent kasari patta lagaaune?",
    "What separates average students from great ones?",
    "नेपालमा सामाजिक दबाब कसरी सामना गर्ने?",
    "How can I become more independent?",
    "Padhai chaina bhane success possible cha ki chaina?",
    "What does balance in life actually mean?",
    "विद्यार्थी जीवनमा के कुरा सबैभन्दा धेरै याद रहन्छ?",
    "How to deal with people who don't believe in you?",
    "Government job ra private job - kun ramro?",
    "Why do smart people sometimes fail?",
    "परिवारलाई निराश नगरी आफ्नो बाटो कसरी छान्ने?",
    "What's the biggest lie students are told?",
    "Nepali society ma change ko lagi k garna sakhincha?"
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
        st.markdown(
            f"""
            <div style="
                padding: 0.75rem 1rem;
                border-radius: 12px;
                background-color: rgba(255,255,255,0.05);
                line-height: 1.6;
            ">
            {prompt}
            </div>
            """,
            unsafe_allow_html=True
        )

    # Assistant placeholder
    with st.chat_message("assistant"):
        thinking = st.empty()
        thinking.markdown("🤔 *Kancha AI is thinking…*")

        reply = reply_to(prompt)

        thinking.markdown(
            f"""
            <div style="
                padding: 0.9rem 1.1rem;
                border-radius: 14px;
                background-color: rgba(0,128,255,0.08);
                line-height: 1.65;
            ">
            {reply}
            </div>
            """,
            unsafe_allow_html=True
        )

    st.session_state.messages.append(
        {"role": "assistant", "content": reply}
    )

    
    # Rerun to update the UI
    st.rerun()