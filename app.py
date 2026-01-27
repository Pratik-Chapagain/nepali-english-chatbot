"""
Kancha AI - Professional Multilingual Chatbot
Optimized Version with all features integrated
"""

import streamlit as st
import google.generativeai as genai
import os, re, time, json, logging, threading, random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class AppConfig:
    """Centralized application configuration"""
    APP_NAME: str = "Kancha AI"
    APP_ICON: str = "😊"
    VERSION: str = "2.1.0"
    
    # API Configuration
    API_CALLS_PER_MINUTE: int = 5
    API_TIMEOUT: int = 30
    MODEL_NAME: str = "gemini-2.5-flash"  # Updated model
    
    # Chat Configuration
    MIN_QUERY_LENGTH: int = 2
    MAX_HISTORY: int = 5
    FAQ_THRESHOLD: float = 0.65
    MAX_RESPONSE_LENGTH: int = 500
    
    # UI Configuration
    SIDEBAR_WIDTH: int = 320
    MAX_WIDTH: int = 1100

config = AppConfig()

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('kancha_ai.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# RATE LIMITER (IMPROVED)
# ============================================================================

class RateLimiter:
    """Thread-safe rate limiter for API calls"""
    def __init__(self, calls_per_minute=5):
        self.calls_per_minute = calls_per_minute
        self.calls: List[datetime] = []
        logger.info(f"RateLimiter initialized: {calls_per_minute} calls/min")
    
    def wait_if_needed(self) -> None:
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
                # More precise waiting
                target_time = oldest + timedelta(seconds=60)
                sleep_time = (target_time - now).total_seconds()
                
                if sleep_time > 0:
                    time.sleep(sleep_time + 0.5)
                
                # Reset calls after wait
                self.calls = []
        
        # Add current call
        self.calls.append(now)
    
    def get_remaining_calls(self) -> int:
        """Get number of remaining calls in current minute"""
        now = datetime.now()
        self.calls = [t for t in self.calls 
                     if now - t < timedelta(minutes=1)]
        return max(0, self.calls_per_minute - len(self.calls))

# ============================================================================
# IMPROVED LANGUAGE DETECTION
# ============================================================================

class LanguageDetector:
    """Detect script/language of user input with high accuracy"""
    
    # Extended Devanagari Unicode ranges
    DEVANAGARI_RANGES = [
        (0x0900, 0x097F),  # Devanagari
        (0x1CD0, 0x1CFF),  # Vedic Extensions
        (0xA8E0, 0xA8FF),  # Devanagari Extended
    ]
    
    # Common Nepali words in Romanized form (EXTENDED)
    NEPALI_INDICATORS = {
        # Pronouns and particles
        'ma', 'cha', 'chha', 'ho', 'huncha', 'hunchha', 'hunxa', 'hunna',
        'ko', 'lai', 'le', 'ra', 'ni', 'ta', 'po', 
        
        # Pronouns
        'timro', 'mero', 'hamro', 'unko', 'usko', 'tapai', 'timi', 'tapain',
        'maile', 'taile', 'usle', 'unle',
        
        # Question words
        'kata', 'kaha', 'kina', 'kasari', 'kasko', 'kati', 'kun', 'kaha',
        'kasto', 'kati', 'khoi', 'ke',
        
        # Verbs
        'bhayo', 'bhayena', 'gareko', 'garena', 'garne', 'garnu', 'garna',
        'gar', 'garchu', 'garchha', 'garxa', 'hune',
        'hudaicha', 'hudaina', 'rahecha', 'rahena', 'hunu', 'hunuhuncha',
        
        # Common words
        'ramro', 'naramro', 'thulo', 'sano', 'mitho', 'piro', 'garmi',
        'jado', 'pani', 'ani', 'tara', 'kinabhane', 'bhanera', 'bhanne',
        'dai', 'didi', 'bhai', 'bahini', 'aama', 'baba', 'sathi',
        
        # Modal/auxiliary
        'pugcha', 'pugdaina', 'sakcha', 'sakdaina', 'parcha', 'pardaina',
        'parxa', 'pardaina', 'lagcha', 'lagdaina', 'milcha', 'mildaina',
        
        # Time/place
        'aja', 'bholi', 'hijo', 'asti', 'paxi', 'agadi', 'pachadi',
        'mathi', 'tala', 'bhitra', 'bahira',
        
        # Common phrases
        'namaste', 'dhanyabad', 'maf', 'kripaya', 'hajur', 'la', 'hoina',
    }
    
    @staticmethod
    def detect(text: str) -> str:
        """
        Detect script of input text
        
        Returns:
            'devanagari', 'nepglish', or 'english'
        """
        text = text.strip()
        if not text:
            return 'english'
        
        # Count Devanagari characters across all ranges
        devanagari_chars = sum(
            1 for c in text 
            if any(start <= ord(c) <= end for start, end in LanguageDetector.DEVANAGARI_RANGES)
        )
        
        # Count total non-space characters
        total_chars = len(text.replace(' ', ''))
        
        if total_chars == 0:
            return 'english'
        
        devanagari_percentage = (devanagari_chars / total_chars) * 100
        
        # If 40%+ is Devanagari → Pure Devanagari
        if devanagari_percentage >= 40:
            logger.debug(f"Detected Devanagari ({devanagari_percentage:.1f}%)")
            return 'devanagari'
        
        # Check for Romanized Nepali words
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Count matches
        nepali_word_count = sum(1 for word in words if word in LanguageDetector.NEPALI_INDICATORS)
        
        # Adjust detection logic
        if len(words) >= 3:
            nepali_ratio = nepali_word_count / len(words)
            if nepali_ratio >= 0.25:  # 25% Nepali words
                logger.debug(f"Detected Nepglish ({nepali_word_count}/{len(words)} words)")
                return 'nepglish'
        elif nepali_word_count >= 2:
            logger.debug(f"Detected Nepglish ({nepali_word_count} words)")
            return 'nepglish'
        
        # Check for mixed script
        if devanagari_chars > 0 and devanagari_percentage < 40:
            if nepali_word_count >= 1:
                return 'nepglish'
        
        logger.debug("Detected English")
        return 'english'

# ============================================================================
# MESSAGE VALIDATOR
# ============================================================================

class MessageValidator:
    """Validate and sanitize user messages"""
    
    @staticmethod
    def validate(message: str) -> Tuple[bool, Optional[str]]:
        """
        Validate user message
        
        Returns:
            (is_valid, error_message)
        """
        if not message:
            return False, "Message cannot be empty"
        
        message = message.strip()
        
        if len(message) < config.MIN_QUERY_LENGTH:
            return False, f"Message too short (min {config.MIN_QUERY_LENGTH} chars)"
        
        if len(message) > 2000:
            return False, "Message too long (max 2000 chars)"
        
        return True, None
    
    @staticmethod
    def sanitize(message: str) -> str:
        """Remove potentially harmful content"""
        # Remove excessive whitespace
        message = re.sub(r'\s+', ' ', message)
        return message.strip()

# ============================================================================
# RESPONSE PROCESSOR
# ============================================================================

class ResponseProcessor:
    """Process and format AI responses"""
    
    @staticmethod
    def clean(response: str) -> str:
        """Clean and validate AI response"""
        # Remove FAQ metadata
        response = re.sub(r'\[FAQ Match:.*?\]', '', response)
        response = re.sub(r'\[Similarity:.*?\]', '', response)
        response = re.sub(r'\[Match.*?\]', '', response)
        
        # Remove suspicious URLs
        suspicious_patterns = [
            (r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+', 
             '🔍 YouTube ma search gara: '),
            (r'https?://youtu\.be/[\w-]+', 
             '🔍 YouTube video search gara: '),
            (r'https?://[^\s]+', 
             '🔗 [Link removed - Search instead]')
        ]
        
        for pattern, replacement in suspicious_patterns:
            response = re.sub(pattern, replacement, response)
        
        # Clean excessive newlines
        response = re.sub(r'\n{3,}', '\n\n', response)
        
        return response.strip()
    
    @staticmethod
    def format_error(error: Exception, script: str) -> str:
        """Format error message based on language"""
        error_messages = {
            'rate_limit': {
                'devanagari': """**⚠️ Request Limit पुग्यो**

कृपया १-२ मिनेट पर्खनुहोस्। Free tier मा limited requests छन्।

**सुझाव:**
• छोटो प्रश्न सोध्नुहोस्
• केही मिनेट पछि पुनः प्रयास गर्नुहोस्
• एकै समयमा धेरै प्रश्न नसोध्नुहोस्""",
                'nepglish': """**⚠️ Request Limit Reached**

Kripaya 1-2 minute wait garnus. Free tier ma limited requests chan.

**Suggestions:**
• Ask concise questions
• Try again after a few minutes
• Don't send multiple questions at once""",
                'english': """**⚠️ Request Limit Reached**

Please wait 1-2 minutes. Free tier has limited requests.

**Suggestions:**
• Ask concise questions
• Try again after a few minutes
• Don't send multiple questions at once"""
            },
            'timeout': {
                'devanagari': "**⏱️ Response Timeout**\n\nAI लाई समय लाग्यो। छोटो message try गर्नुहोस् वा केही समय पछि फेरि सोध्नुहोस्।",
                'nepglish': "**⏱️ Response Timeout**\n\nAI lai time lagyo. Try a shorter message or ask again later.",
                'english': "**⏱️ Response Timeout**\n\nAI took too long to respond. Try a shorter message or ask again later."
            },
            'generic': {
                'devanagari': f"**❌ त्रुटि भयो**\n\nकृपया फेरि प्रयास गर्नुहोस्।\n\nError: {str(error)[:100]}",
                'nepglish': f"**❌ Error Bhayo**\n\nKripaya feri try garnus.\n\nError: {str(error)[:100]}",
                'english': f"**❌ An Error Occurred**\n\nPlease try again.\n\nError: {str(error)[:100]}"
            }
        }
        
        error_str = str(error).lower()
        
        if 'quota' in error_str or '429' in error_str:
            error_type = 'rate_limit'
        elif 'timeout' in error_str:
            error_type = 'timeout'
        else:
            error_type = 'generic'
        
        return error_messages[error_type].get(script, error_messages[error_type]['english'])

# ============================================================================
# FAQ HANDLER (SIMPLIFIED)
# ============================================================================

class FAQHandler:
    """Handle FAQ matching - simplified version"""
    
    FAQ_DATA = {
        'en': {
            "What is Kancha AI?": "Kancha AI is a multilingual chatbot assistant specifically designed for Nepali users. It supports English, Nepali (Devanagari), and Nepglish (Romanized Nepali).",
            "SEE exam information": "SEE (Secondary Education Examination) is the national level exam in Nepal for Grade 10 students. It's conducted by National Examination Board (NEB).",
            "Dashain festival": "Dashain is the biggest festival in Nepal, celebrated for 15 days in September/October. It symbolizes the victory of good over evil.",
            "IOE entrance guide": "IOE entrance exam is for admission to engineering colleges in Nepal. Preparation requires strong basics in Physics, Chemistry, and Mathematics.",
            "Study tips": "Effective study tips: 1) Create a schedule 2) Take regular breaks 3) Practice problems 4) Review regularly 5) Get enough sleep.",
            "Career guidance": "For career guidance: 1) Assess your interests 2) Research options 3) Talk to professionals 4) Consider job market 5) Plan your education."
        },
        'np': {
            "Kancha AI भनेको के हो?": "Kancha AI भनेको नेपाली प्रयोगकर्ताहरूको लागि विशेष रूपमा तयार गरिएको बहुभाषिक च्याटबट सहायक हो। यसले अङ्ग्रेजी, नेपाली (देवनागरी), र नेप्गलिस (रोमनाइज्ड नेपाली) समर्थन गर्दछ।",
            "SEE परीक्षा": "SEE (माध्यमिक शिक्षा परीक्षा) नेपालमा कक्षा १० का विद्यार्थीहरूको लागि राष्ट्रिय स्तरको परीक्षा हो। यो राष्ट्रिय परीक्षा बोर्ड (NEB) द्वारा आयोजना गरिन्छ।",
            "दशैं पर्व": "दशैं नेपालको सबैभन्दा ठूलो पर्व हो, सेप्टेम्बर/अक्टोबरमा १५ दिनसम्म मनाइन्छ। यसले सत्को माथि असत्को विजयलाई प्रतिनिधित्व गर्दछ।"
        }
    }
    
    @staticmethod
    def get_answer(query: str, language: str = 'en', threshold: float = 0.65) -> Optional[str]:
        """Simple FAQ matching"""
        if language not in FAQHandler.FAQ_DATA:
            language = 'en'
        
        query_lower = query.lower().strip()
        
        # Simple keyword matching
        for question, answer in FAQHandler.FAQ_DATA[language].items():
            question_lower = question.lower()
            
            # Check for direct match or contains
            if (query_lower == question_lower or 
                query_lower in question_lower or 
                question_lower in query_lower):
                return answer
        
        return None

# ============================================================================
# IMPROVED SYSTEM PROMPT
# ============================================================================

SYSTEM_PROMPT = """You are Kancha AI, a bilingual assistant for Nepali users.

<CRITICAL_INSTRUCTION>
**LANGUAGE MATCHING (MANDATORY):**
1. User writes in Devanagari (क, ख, ग...) → Respond 100% in Devanagari
2. User writes in Romanized Nepali (ma, cha, ko...) → Respond in Nepglish
3. User writes in English → Respond in English

**NEVER MIX SCRIPTS IN RESPONSE.**
</CRITICAL_INSTRUCTION>

<FORMATTING_RULES>
**ALWAYS USE THIS FORMAT:**
- Use line breaks between points
- Use numbered lists (1), (2), (3) or (१), (२), (३) based on language
- Add blank lines between sections
- Bold key terms with **text**
- Maximum 2-3 sentences per point

**Example Format (Nepglish):**
Nepal ma students haru ko main struggles:

**(1) Quality Education**
Dherai schools ma outdated teaching methods use huncha. Practical skills lai focus kam cha.

**(2) Career Guidance**
Proper guidance milena. Kun field choose garne confuse huncha.

**(3) Financial Problem**
Education expensive cha. Dherai lai afford garna garo huncha.
</FORMATTING_RULES>

<CONTENT_RULES>
1. **Never fabricate information** - no fake addresses, prices, phone numbers
2. **No clickable links** - never include https://, http://, www.
3. **Use respectful pronouns** - default to "तपाईं" (Devanagari) or "you"
4. **Be concise** - 150-250 words max
5. **Focus on Nepal context** - provide culturally relevant information
6. **Be honest about limitations** - if you don't know, say so
7. **Provide practical, actionable advice**
</CONTENT_RULES>

**KEY: Script matching + Proper formatting + Honest information + Nepal focus**
"""

# ============================================================================
# AI CHAT MANAGER
# ============================================================================

class AIChatManager:
    """Manage AI chat interactions"""
    
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            config.MODEL_NAME,
            system_instruction=SYSTEM_PROMPT
        )
        self.chat = None
        logger.info("AI Chat Manager initialized")
    
    def start_chat(self):
        """Start a new chat session"""
        self.chat = self.model.start_chat(history=[])
        logger.info("New chat session started")
    
    def send_message(self, message: str, script: str) -> str:
        """
        Send message to AI and get response
        
        Args:
            message: User message
            script: Detected script (devanagari/nepglish/english)
            
        Returns:
            AI response text
        """
        if not self.chat:
            self.start_chat()
        
        # Prepare prompt with language instruction
        instructions = {
            'devanagari': "[USER IS WRITING IN DEVANAGARI SCRIPT - YOU MUST RESPOND 100% IN DEVANAGARI]",
            'nepglish': "[USER IS WRITING IN ROMANIZED NEPALI (NEPGLISH) - YOU MUST RESPOND IN NEPGLISH]",
            'english': "[USER IS WRITING IN ENGLISH - YOU MUST RESPOND IN ENGLISH]"
        }
        
        tagged_message = f"{instructions[script]}\n\nUser: {message}"
        
        try:
            response = self.chat.send_message(
                tagged_message,
                request_options={"timeout": config.API_TIMEOUT}
            )
            
            return ResponseProcessor.clean(response.text)
            
        except Exception as e:
            logger.error(f"AI chat error: {e}", exc_info=True)
            raise Exception(f"Failed to get AI response: {str(e)[:100]}")

# ============================================================================
# SESSION STATE MANAGER
# ============================================================================

class SessionStateManager:
    """Manage Streamlit session state"""
    
    @staticmethod
    def initialize():
        """Initialize all session state variables"""
        defaults = {
            "messages": [],
            "rate_limiter": RateLimiter(config.API_CALLS_PER_MINUTE),
            "chat_manager": None,
            "query_history": [],
            "suggestions": [],
            "initialized": False
        }
        
        for key, default_value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
        
        if not st.session_state.initialized:
            logger.info("Session state initialized")
            st.session_state.initialized = True
    
    @staticmethod
    def add_to_history(query: str):
        """Add query to history"""
        if (query not in st.session_state.query_history and 
            len(query.strip()) > config.MIN_QUERY_LENGTH and
            not query.startswith('/')):
            st.session_state.query_history.insert(0, query)
            st.session_state.query_history = st.session_state.query_history[:config.MAX_HISTORY]
    
    @staticmethod
    def clear_chat():
        """Clear chat history"""
        st.session_state.messages = []
        st.session_state.query_history = []
        if st.session_state.chat_manager:
            st.session_state.chat_manager.start_chat()
        logger.info("Chat history cleared")
    
    @staticmethod
    def generate_suggestions():
        """Generate new suggestion prompts"""
        suggestion_pool = [
            "What skills are most useful for students today?",
            "How can I improve my focus while studying?",
            "What are common career mistakes?",
            "How to prepare for SEE exam?",
            "Bachelor pachi career choose kasari garne?",
            "Nepal ma students ko main struggle?",
            "Time management kasari improve garne?",
            "IOE entrance preparation?",
            "विद्यार्थीहरूले सामना गर्ने समस्या?",
            "आत्मविश्वास कसरी बढाउने?",
            "करियर छनोट गर्दा ध्यान दिनुपर्ने?",
            "पढाइमा मन कसरी लाउने?",
        ]
        st.session_state.suggestions = random.sample(suggestion_pool, 6)

# ============================================================================
# MESSAGE PROCESSOR
# ============================================================================

def process_user_message(user_input: str):
    """Process user message and generate response"""
    try:
        # Validate input
        is_valid, error_msg = MessageValidator.validate(user_input)
        if not is_valid:
            st.error(f"❌ {error_msg}")
            return
        
        # Sanitize input
        user_input = MessageValidator.sanitize(user_input)
        
        # Add to history
        SessionStateManager.add_to_history(user_input)
        
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # Check for special commands
        if user_input.startswith('/summarize') or user_input.startswith('/summary'):
            text_to_summarize = user_input.replace('/summarize', '').replace('/summary', '').strip()
            if not text_to_summarize:
                script = LanguageDetector.detect(user_input)
                if script == 'devanagari':
                    return "**📝 Summarize Command**\n\nकृपया summarize गर्नको लागि text प्रदान गर्नुहोस्।"
                else:
                    return "**📝 Summarize Command**\n\nPlease provide text to summarize."
            user_input = f"Please summarize this text in the same language/script: {text_to_summarize}"
        
        # Check FAQ first (instant response, no API call)
        script = LanguageDetector.detect(user_input)
        language_map = {'devanagari': 'np', 'nepglish': 'np', 'english': 'en'}
        language = language_map.get(script, 'en')
        
        faq_answer = FAQHandler.get_answer(user_input, language, config.FAQ_THRESHOLD)
        if faq_answer:
            if script == 'devanagari':
                response = f"**📌 तत्काल उत्तर:**\n\n{faq_answer}"
            else:
                response = f"**📌 Quick Answer:**\n\n{faq_answer}"
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": response
            })
            return
        
        # Apply rate limiting
        st.session_state.rate_limiter.wait_if_needed()
        
        # Get AI response
        response = st.session_state.chat_manager.send_message(user_input, script)
        
        # Add AI response to chat
        st.session_state.messages.append({
            "role": "assistant",
            "content": response
        })
        
        logger.info(f"Message processed successfully in {script}")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        script = LanguageDetector.detect(user_input)
        error_msg = ResponseProcessor.format_error(e, script)
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": error_msg
        })

# ============================================================================
# UI COMPONENTS
# ============================================================================

def inject_custom_css():
    """Inject professional custom CSS"""
    st.markdown(f"""
    <style>
    /* ============= ROOT VARIABLES ============= */
    :root {{
        --primary: #0891b2;
        --primary-dark: #0e7490;
        --accent: #3b82f6;
        --success: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --bg: #ffffff;
        --bg-secondary: #f8fafc;
        --bg-tertiary: #f1f5f9;
        --text: #1e293b;
        --text-secondary: #64748b;
        --border: #e2e8f0;
        --shadow: 0 1px 3px rgba(0,0,0,0.08);
        --shadow-lg: 0 10px 25px rgba(0,0,0,0.1);
    }}
    
    [data-theme="dark"] {{
        --bg: #0f172a;
        --bg-secondary: #1e293b;
        --bg-tertiary: #334155;
        --text: #f1f5f9;
        --text-secondary: #94a3b8;
        --border: #334155;
        --shadow: 0 1px 3px rgba(0,0,0,0.3);
        --shadow-lg: 0 10px 25px rgba(0,0,0,0.4);
    }}
    
    /* ============= GLOBAL STYLES ============= */
    * {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    
    #MainMenu, header, footer {{visibility: hidden;}}
    
    .main .block-container {{
        max-width: 1100px;
        padding: 2rem 2rem 8rem;
    }}
    
    /* ============= HEADER ============= */
    .app-header {{
        text-align: center;
        padding: 2rem 0 3rem;
        animation: fadeInDown 0.5s ease-out;
    }}
    
    .app-header h1 {{
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }}
    
    .app-subtitle {{
        color: var(--text-secondary);
        font-size: 1.125rem;
        font-weight: 500;
        margin-bottom: 1.5rem;
    }}
    
    .lang-badges {{
        display: flex;
        gap: 0.75rem;
        justify-content: center;
        flex-wrap: wrap;
    }}
    
    .lang-badge {{
        background: var(--bg-secondary);
        border: 2px solid var(--border);
        padding: 0.5rem 1.25rem;
        border-radius: 50px;
        font-size: 0.875rem;
        color: var(--text-secondary);
        font-weight: 600;
        transition: all 0.3s;
    }}
    
    .lang-badge:hover {{
        border-color: var(--primary);
        color: var(--primary);
        transform: translateY(-2px);
        box-shadow: var(--shadow-lg);
    }}
    
    /* ============= CHAT MESSAGES ============= */
    .stChatMessage {{
        padding: 1.5rem;
        border-radius: 16px;
        margin-bottom: 1.25rem;
        box-shadow: var(--shadow);
        animation: fadeInUp 0.3s ease-out;
    }}
    
    [data-testid="stChatMessageUser"] {{
        background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
        color: white;
    }}
    
    [data-testid="stChatMessageUser"] p {{
        color: white !important;
    }}
    
    [data-testid="stChatMessageAssistant"] {{
        background: var(--bg-secondary);
        border-left: 4px solid var(--primary);
    }}
    
    .stChatMessage p {{
        color: var(--text);
        line-height: 1.7;
        margin-bottom: 0.5rem;
    }}
    
    /* ============= CHAT INPUT ============= */
    .stChatInput {{
        position: fixed;
        bottom: 0;
        left: 21rem;
        right: 0;
        background: var(--bg);
        padding: 1.5rem 2rem;
        border-top: 1px solid var(--border);
        box-shadow: 0 -4px 20px rgba(0,0,0,0.08);
        z-index: 999;
        backdrop-filter: blur(10px);
    }}
    
    .stChatInput textarea {{
        border-radius: 50px !important;
        border: 2px solid var(--border) !important;
        padding: 1rem 1.5rem !important;
        background: var(--bg-secondary) !important;
        color: var(--text) !important;
        font-size: 0.95rem !important;
        transition: all 0.2s !important;
    }}
    
    .stChatInput textarea:focus {{
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px rgba(8, 145, 178, 0.1) !important;
    }}
    
    .stChatInput textarea::placeholder {{
        color: var(--text-secondary) !important;
    }}
    
    /* ============= SIDEBAR ============= */
    [data-testid="stSidebar"] {{
        background: var(--bg-secondary);
        border-right: 1px solid var(--border);
        width: 21rem;
    }}
    
    [data-testid="stSidebar"] .sidebar-content {{
        padding: 1.5rem;
    }}
    
    [data-testid="stSidebar"] h2 {{
        color: var(--primary) !important;
        font-weight: 800 !important;
        font-size: 1.5rem !important;
        margin-bottom: 0.5rem !important;
    }}
    
    /* Sidebar buttons */
    [data-testid="stSidebar"] .stButton button {{
        width: 100%;
        border-radius: 12px;
        padding: 0.875rem 1rem;
        margin-bottom: 0.5rem;
        border: 2px solid var(--border);
        background: var(--bg);
        color: var(--text);
        text-align: left;
        font-weight: 500;
        transition: all 0.2s;
    }}
    
    [data-testid="stSidebar"] .stButton button:hover {{
        border-color: var(--primary);
        transform: translateX(4px);
        box-shadow: var(--shadow);
    }}
    
    /* Clear button */
    [data-testid="stSidebar"] .stButton button[kind="primary"] {{
        background: var(--danger);
        color: white;
        border: none;
        font-weight: 600;
    }}
    
    [data-testid="stSidebar"] .stButton button[kind="primary"]:hover {{
        background: #dc2626;
        transform: scale(1.02);
    }}
    
    /* ============= TABS ============= */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0.25rem;
        background: var(--bg-tertiary);
        border-radius: 12px;
        padding: 0.25rem;
    }}
    
    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px;
        padding: 0.75rem 1.25rem;
        color: var(--text-secondary);
        font-weight: 600;
        transition: all 0.2s;
    }}
    
    .stTabs [aria-selected="true"] {{
        background: var(--primary);
        color: white;
    }}
    
    /* ============= SUGGESTION CARDS ============= */
    .suggestion-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 1rem;
        margin: 2rem 0;
    }}
    
    .main .stButton button {{
        background: var(--bg-secondary);
        border: 2px solid var(--border);
        border-radius: 16px;
        padding: 1.5rem;
        color: var(--text);
        text-align: left;
        min-height: 100px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        font-weight: 500;
        line-height: 1.5;
    }}
    
    .main .stButton button:hover {{
        border-color: var(--primary);
        transform: translateY(-4px);
        box-shadow: var(--shadow-lg);
        background: var(--primary);
        color: white;
    }}
    
    /* Refresh button */
    .main .stButton button[kind="secondary"] {{
        min-height: auto;
        color: var(--primary);
        font-weight: 600;
        border-color: var(--primary);
    }}
    
    .main .stButton button[kind="secondary"]:hover {{
        background: var(--primary);
        color: white;
    }}
    
    /* ============= ANIMATIONS ============= */
    @keyframes fadeInDown {{
        from {{ opacity: 0; transform: translateY(-20px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    @keyframes fadeInUp {{
        from {{ opacity: 0; transform: translateY(20px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    /* ============= RESPONSIVE ============= */
    @media (max-width: 768px) {{
        .main .block-container {{
            padding: 1rem 1rem 6rem;
        }}
        
        .stChatInput {{
            left: 0;
            padding: 1rem;
        }}
        
        .app-header h1 {{
            font-size: 2.25rem;
        }}
        
        .suggestion-grid {{
            grid-template-columns: 1fr;
        }}
    }}
    </style>
    """, unsafe_allow_html=True)

def render_header():
    """Render application header"""
    st.markdown("""
        <div class="app-header">
            <h1>{icon} {name}</h1>
            <p class="app-subtitle">Your Intelligent Nepali Assistant</p>
            <div class="lang-badges">
                <div class="lang-badge">🇬🇧 English</div>
                <div class="lang-badge">🇳🇵 नेपाली</div>
                <div class="lang-badge">🌐 Nepglish</div>
            </div>
        </div>
    """.format(icon=config.APP_ICON, name=config.APP_NAME), unsafe_allow_html=True)

def render_sidebar():
    """Render sidebar with navigation and controls"""
    with st.sidebar:
        st.markdown("""
            <div style="text-align: center; padding: 1rem 0 1.5rem;">
                <h2>{icon} {name}</h2>
                <p style="color: var(--text-secondary); font-size: 0.9rem; margin: 0.5rem 0 0;">
                    v{version} - Professional Assistant
                </p>
            </div>
        """.format(icon=config.APP_ICON, name=config.APP_NAME, version=config.VERSION), 
        unsafe_allow_html=True)
        
        # Tabs for different sections
        tab1, tab2, tab3 = st.tabs(["📝 Recent", "❓ FAQ", "ℹ️ Info"])
        
        with tab1:
            render_history_tab()
        
        with tab2:
            render_faq_tab()
        
        with tab3:
            render_info_tab()
        
        # Clear chat button
        st.divider()
        if st.button("🗑️ Clear All Chats", use_container_width=True, type="primary"):
            SessionStateManager.clear_chat()
            st.success("✅ Chat cleared!")
            time.sleep(0.5)
            st.rerun()
        
        st.caption("Made with ❤️ for Nepali users")

def render_history_tab():
    """Render recent queries tab"""
    history = st.session_state.query_history
    if history:
        st.markdown("**Recent Questions**")
        for i, query in enumerate(history):
            display_query = query[:45] + "..." if len(query) > 45 else query
            if st.button(display_query, key=f"history_{i}", use_container_width=True):
                process_user_message(query)
                st.rerun()
    else:
        st.info("📭 No recent queries")

def render_faq_tab():
    """Render quick FAQ buttons"""
    st.markdown("**Quick Questions**")
    faqs = [
        "What is Kancha AI?",
        "SEE exam information",
        "Dashain festival",
        "IOE entrance guide",
        "Study tips",
        "Career guidance"
    ]
    for label in faqs:
        if st.button(label, key=f"faq_{label}", use_container_width=True):
            process_user_message(label)
            st.rerun()

def render_info_tab():
    """Render info and stats tab"""
    st.markdown("**📊 Usage Stats**")
    
    # Show rate limit progress
    remaining = st.session_state.rate_limiter.get_remaining_calls()
    progress = remaining / config.API_CALLS_PER_MINUTE
    st.progress(progress, text=f"{remaining}/{config.API_CALLS_PER_MINUTE} requests left")
    st.caption("⏱️ Resets every minute")
    
    st.divider()
    
    # Message count
    msg_count = len([m for m in st.session_state.messages if m["role"] == "user"])
    st.metric("Messages Sent", msg_count)
    
    st.divider()
    
    st.markdown("**🌍 Supported Languages**")
    st.markdown("• English 🇬🇧\n• नेपाली 🇳🇵\n• Nepglish 🌐")
    
    st.divider()
    
    st.markdown("**✨ Features**")
    st.markdown("""
    • Multi-language support
    • Smart rate limiting
    • Instant FAQ answers
    • Nepal-specific knowledge
    • Professional formatting
    """)

def render_suggestions():
    """Render suggestion cards when chat is empty"""
    if not st.session_state.suggestions:
        SessionStateManager.generate_suggestions()
    
    if not st.session_state.messages:
        st.markdown("""
            <div style="text-align: center; margin: 2.5rem 0 2rem;">
                <h2 style="font-size: 1.875rem; font-weight: 700; color: var(--text);">
                    💡 Try asking...
                </h2>
                <p style="color: var(--text-secondary); margin-top: 0.5rem;">
                    Popular questions to get started
                </p>
            </div>
        """, unsafe_allow_html=True)
        
        # Display in 2 columns
        cols = st.columns(2, gap="medium")
        for idx, suggestion in enumerate(st.session_state.suggestions):
            with cols[idx % 2]:
                if st.button(suggestion, key=f"sug_{idx}", use_container_width=True):
                    process_user_message(suggestion)
                    st.rerun()
        
        # Refresh button
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Show different suggestions", 
                        use_container_width=True, 
                        type="secondary"):
                SessionStateManager.generate_suggestions()
                st.rerun()

def render_chat_messages():
    """Render all chat messages"""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application entry point"""
    
    # Page configuration
    st.set_page_config(
        page_title=config.APP_NAME,
        page_icon=config.APP_ICON,
        layout="centered",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    SessionStateManager.initialize()
    
    # Inject custom CSS
    inject_custom_css()
    
    # Load API key
    load_dotenv()
    api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        st.error("""
        ## 🔑 API Key Required
        
        **For Streamlit Cloud:**
        1. Go to app settings → Secrets
        2. Add: `GEMINI_API_KEY = "your-key-here"`
        
        **For Local Development:**
        1. Create `.env` file
        2. Add: `GEMINI_API_KEY=your-key-here`
        
        Get your key from: https://aistudio.google.com/app/apikey
        """)
        st.stop()
    
    # Initialize chat manager
    if not st.session_state.chat_manager:
        st.session_state.chat_manager = AIChatManager(api_key)
        st.session_state.chat_manager.start_chat()
    
    # Render UI components
    render_header()
    render_sidebar()
    
    # Show suggestions or chat messages
    if st.session_state.messages:
        st.markdown("---")
        render_chat_messages()
    else:
        render_suggestions()
    
    # Chat input
    st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)
    
    if prompt := st.chat_input("Type your question... (English, नेपाली, or Nepglish)"):
        process_user_message(prompt)
        st.rerun()

# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    main()