"""
web_search.py - Enhanced web search with Nepal-specific optimization
"""
import requests
import re
import json
from datetime import datetime
import time
from urllib.parse import quote_plus, urlencode
import html

class WebSearcher:
    """Enhanced web search optimized for Nepal-specific queries"""
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
    
    def search(self, query, max_results=3):
        """Search with Nepal-specific optimization"""
        try:
            print(f"\n🔍 Searching: '{query}'")
            
            # Special handling for political positions
            if self._is_political_query(query):
                return self._search_political_info(query, max_results)
            
            # General search
            return self._enhanced_search(query, max_results)
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def _is_political_query(self, query):
        """Check if query is about political positions"""
        political_keywords = [
            'prime minister', 'president', 'pm', 'government',
            'minister', 'cabinet', 'head of state', 'head of government',
            'प्रधानमन्त्री', 'राष्ट्रपति', 'सरकार', 'मन्त्री'
        ]
        
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in political_keywords)
    
    def _search_political_info(self, query, max_results):
        """Specialized search for political information"""
        try:
            # Format query for political search
            query_lower = query.lower()
            
            if 'prime minister' in query_lower or 'pm' in query_lower or 'प्रधानमन्त्री' in query:
                search_queries = [
                    f"Nepal current Prime Minister 2025 2026 latest",
                    f"Who is Prime Minister of Nepal now",
                    f"नयाँ प्रधानमन्त्री नेपाल २०२६"
                ]
            elif 'president' in query_lower or 'राष्ट्रपति' in query:
                search_queries = [
                    f"Nepal President 2025 2026 current",
                    f"Who is President of Nepal now",
                    f"नेपालको राष्ट्रपति २०२६"
                ]
            else:
                search_queries = [f"{query} Nepal latest 2025 2026"]
            
            # Try each search query
            for search_query in search_queries:
                results = self._duckduckgo_search(search_query, max_results, is_political=True)
                if results:
                    print(f"Found political results using: '{search_query}'")
                    return results
            
            # Fallback to news sites
            return self._search_nepal_news(query, max_results)
            
        except Exception as e:
            print(f"Political search error: {e}")
            return []
    
    def _enhanced_search(self, query, max_results):
        """General enhanced search"""
        try:
            # Try DuckDuckGo first
            results = self._duckduckgo_search(query, max_results)
            if results:
                return results
            
            # Try Google Custom Search (if available)
            results = self._try_google_search(query, max_results)
            if results:
                return results
            
            return []
            
        except Exception as e:
            print(f"Enhanced search error: {e}")
            return []
    
    def _duckduckgo_search(self, query, max_results, is_political=False):
        """Improved DuckDuckGo search with better parsing"""
        try:
            # Format query for better results
            enhanced_query = query
            
            if is_political:
                enhanced_query = f"{query} site:.np OR site:.com.np latest news update"
            else:
                current_year = datetime.now().year
                enhanced_query = f"{query} {current_year} Nepal"
            
            print(f"DuckDuckGo query: '{enhanced_query}'")
            
            # Prepare request
            params = {
                'q': enhanced_query,
                'kl': 'np-np',  # Nepal region
                'df': 'y',  # Disable safe search
                't': 'ne'  # Nepal
            }
            
            url = "https://html.duckduckgo.com/html/?" + urlencode(params)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://duckduckgo.com/',
                'DNT': '1',
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                print(f"DuckDuckGo returned status: {response.status_code}")
                return []
            
            return self._parse_duckduckgo_results(response.text, max_results)
            
        except Exception as e:
            print(f"DuckDuckGo search error: {e}")
            return []
    
    def _parse_duckduckgo_results(self, html_content, max_results):
        """Parse DuckDuckGo results with improved extraction"""
        results = []
        
        try:
            # Find all result containers
            result_pattern = r'<div class="result[^"]*">(.*?)</div>\s*</div>'
            result_matches = re.findall(result_pattern, html_content, re.DOTALL)
            
            for match in result_matches[:max_results]:
                # Extract title
                title_match = re.search(r'class="result__title".*?<a[^>]*>(.*?)</a>', match, re.DOTALL)
                if not title_match:
                    continue
                
                title = self._clean_html(title_match.group(1))
                
                # Extract snippet
                snippet_match = re.search(r'class="result__snippet".*?>(.*?)</a>', match, re.DOTALL)
                snippet = self._clean_html(snippet_match.group(1)) if snippet_match else ""
                
                # Extract URL for context
                url_match = re.search(r'class="result__url".*?>(.*?)</a>', match, re.DOTALL)
                url = self._clean_html(url_match.group(1)) if url_match else "Unknown"
                
                # Check for date in snippet
                date_match = re.search(r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})', 
                                      snippet, re.IGNORECASE)
                date = date_match.group(1) if date_match else "Recent"
                
                # Filter out irrelevant results
                if len(snippet) > 20 and not self._is_irrelevant(title, snippet):
                    results.append({
                        'title': title[:120] + "..." if len(title) > 120 else title,
                        'snippet': snippet[:300] + "..." if len(snippet) > 300 else snippet,
                        'source': 'DuckDuckGo',
                        'date': date,
                        'url_hint': url[:50] + "..." if len(url) > 50 else url
                    })
            
            print(f"Parsed {len(results)} results from DuckDuckGo")
            return results
            
        except Exception as e:
            print(f"Parse error: {e}")
            return []
    
    def _is_irrelevant(self, title, snippet):
        """Filter out irrelevant results"""
        irrelevant_patterns = [
            r'wikipedia\.org',
            r'book.*?price',
            r'buy.*?online',
            r'\.pdf$',
            r'advertisement',
            r'sponsored',
            r'यसबारे थप'
        ]
        
        combined = f"{title} {snippet}".lower()
        return any(re.search(pattern, combined, re.IGNORECASE) for pattern in irrelevant_patterns)
    
    def _search_nepal_news(self, query, max_results):
        """Direct search from Nepal news sites"""
        try:
            results = []
            
            # OnlineKhabar search
            onlinekhabar_results = self._search_onlinekhabar(query)
            if onlinekhabar_results:
                results.extend(onlinekhabar_results[:2])
            
            # Ekantipur search
            if len(results) < max_results:
                ekantipur_results = self._search_ekantipur(query)
                if ekantipur_results:
                    results.extend(ekantipur_results[:1])
            
            # Setopati search
            if len(results) < max_results:
                setopati_results = self._search_setopati(query)
                if setopati_results:
                    results.extend(setopati_results[:1])
            
            return results[:max_results]
            
        except Exception as e:
            print(f"News search error: {e}")
            return []
    
    def _search_onlinekhabar(self, query):
        """Search OnlineKhabar"""
        try:
            encoded_query = quote_plus(query)
            url = f"https://www.onlinekhabar.com/search?q={encoded_query}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # Simple parsing for OnlineKhabar
                title_pattern = r'<h2[^>]*><a[^>]*>(.*?)</a></h2>'
                titles = re.findall(title_pattern, response.text, re.DOTALL)
                
                results = []
                for title in titles[:2]:  # Get first 2
                    clean_title = self._clean_html(title)
                    if clean_title and len(clean_title) > 10:
                        results.append({
                            'title': clean_title[:100] + "..." if len(clean_title) > 100 else clean_title,
                            'snippet': f"Latest news from OnlineKhabar about {query[:30]}...",
                            'source': 'OnlineKhabar',
                            'date': 'Recent',
                            'url_hint': 'onlinekhabar.com'
                        })
                
                return results
                
        except Exception as e:
            print(f"OnlineKhabar search error: {e}")
        
        return []
    
    def _search_ekantipur(self, query):
        """Search Ekantipur"""
        try:
            encoded_query = quote_plus(query)
            url = f"https://ekantipur.com/search?q={encoded_query}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # Parse Ekantipur
                article_pattern = r'<article[^>]*>(.*?)</article>'
                articles = re.findall(article_pattern, response.text, re.DOTALL)
                
                results = []
                for article in articles[:1]:  # Get first 1
                    # Extract title
                    title_match = re.search(r'<h2[^>]*>(.*?)</h2>', article, re.DOTALL)
                    if title_match:
                        title = self._clean_html(title_match.group(1))
                        
                        # Extract excerpt
                        excerpt_match = re.search(r'<p[^>]*>(.*?)</p>', article, re.DOTALL)
                        excerpt = self._clean_html(excerpt_match.group(1)) if excerpt_match else ""
                        
                        if title:
                            results.append({
                                'title': title[:100] + "..." if len(title) > 100 else title,
                                'snippet': excerpt[:200] + "..." if excerpt else f"News from Ekantipur about {query[:30]}...",
                                'source': 'Ekantipur',
                                'date': 'Recent',
                                'url_hint': 'ekantipur.com'
                            })
                
                return results
                
        except Exception as e:
            print(f"Ekantipur search error: {e}")
        
        return []
    
    def _search_setopati(self, query):
        """Search Setopati"""
        try:
            encoded_query = quote_plus(query)
            url = f"https://www.setopati.com/search?q={encoded_query}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # Simple parsing
                title_pattern = r'<h3[^>]*><a[^>]*>(.*?)</a></h3>'
                titles = re.findall(title_pattern, response.text, re.DOTALL)
                
                results = []
                for title in titles[:1]:  # Get first 1
                    clean_title = self._clean_html(title)
                    if clean_title and len(clean_title) > 10:
                        results.append({
                            'title': clean_title[:100] + "..." if len(clean_title) > 100 else clean_title,
                            'snippet': f"Latest from Setopati about {query[:30]}...",
                            'source': 'Setopati',
                            'date': 'Recent',
                            'url_hint': 'setopati.com'
                        })
                
                return results
                
        except Exception as e:
            print(f"Setopati search error: {e}")
        
        return []
    
    def _try_google_search(self, query, max_results):
        """Fallback using Google (limited without API key)"""
        try:
            encoded_query = quote_plus(f"{query} Nepal")
            url = f"https://www.google.com/search?q={encoded_query}&gl=np"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # Basic parsing of Google results
                results = []
                
                # Look for result divs
                result_pattern = r'<div class="g">(.*?)</div>\s*</div>\s*</div>'
                result_matches = re.findall(result_pattern, response.text, re.DOTALL)
                
                for match in result_matches[:max_results]:
                    # Extract title
                    title_match = re.search(r'<h3[^>]*>(.*?)</h3>', match, re.DOTALL)
                    if not title_match:
                        continue
                    
                    title = self._clean_html(title_match.group(1))
                    
                    # Extract snippet
                    snippet_match = re.search(r'<div[^>]*class="[^"]*VwiC3b[^"]*"[^>]*>(.*?)</div>', match, re.DOTALL)
                    snippet = self._clean_html(snippet_match.group(1)) if snippet_match else ""
                    
                    if title and snippet:
                        results.append({
                            'title': title[:100] + "..." if len(title) > 100 else title,
                            'snippet': snippet[:250] + "..." if len(snippet) > 250 else snippet,
                            'source': 'Google Search',
                            'date': 'Recent',
                            'url_hint': 'google.com'
                        })
                
                return results
                
        except Exception as e:
            print(f"Google search error: {e}")
        
        return []
    
    def _clean_html(self, text):
        """Clean HTML tags and entities"""
        if not text:
            return ""
        
        try:
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', ' ', text)
            
            # Decode HTML entities
            text = html.unescape(text)
            
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text
            
        except Exception:
            return str(text)

# Global instance
web_searcher = WebSearcher()

def get_search_context(query):
    """Get formatted search context with Nepal focus"""
    try:
        print(f"\n{'='*60}")
        print(f"🔍 SEARCHING: '{query}'")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        # Get search results
        results = web_searcher.search(query, max_results=3)
        
        search_time = time.time() - start_time
        
        if not results:
            print(f"❌ No search results found ({search_time:.2f}s)")
            return None
        
        print(f"✅ Found {len(results)} results in {search_time:.2f}s")
        
        # Format context
        current_date = datetime.now().strftime("%B %d, %Y %H:%M")
        context = f"""🔍 **CURRENT WEB SEARCH RESULTS**

**Search Query:** "{query}"
**Search Time:** {current_date}
**Results Found:** {len(results)}
**Search Duration:** {search_time:.2f}s

"""
        
        for i, result in enumerate(results, 1):
            context += f"""**RESULT #{i}: {result['title']}**
{result['snippet']}

*Source: {result['source']} | Date: {result['date']}*
{'-'*50}

"""
        
        context += """---
**CRITICAL INSTRUCTIONS:**
1. Use ONLY the information from these search results
2. Start with "Based on current web search:" 
3. Reference specific result numbers (#1, #2, #3)
4. If search doesn't answer, say: "Search results don't contain specific information"
5. NEVER guess or use outdated knowledge
"""
        
        return context
        
    except Exception as e:
        print(f"Error getting search context: {e}")
        return None

def needs_web_search(prompt):
    """
    Detect if web search is needed for current information
    """
    prompt_lower = prompt.lower()
    
    # Keywords that need current information
    current_keywords = [
        'current', 'latest', 'recent', 'new', 'now', 'today',
        'prime minister', 'president', 'pm', 'government',
        'minister', 'cabinet', 'election', 'result',
        '2025', '2026', 'this year', 'as of now',
        'breaking news', 'latest update', 'just announced',
        'नेपालको', 'प्रधानमन्त्री', 'राष्ट्रपति', 'सरकार',
        'वर्तमान', 'हालको', 'नयाँ', 'ताजा', 'आज', 'भर्खर'
    ]
    
    # Check for any current keyword
    for keyword in current_keywords:
        if keyword in prompt_lower:
            return True
    
    # Check for time-based questions
    time_phrases = [
        'who is current', 'what is current', 'latest news',
        'recent development', 'today\'s update', 'now serving',
        'current situation', 'present government'
    ]
    
    for phrase in time_phrases:
        if phrase in prompt_lower:
            return True
    
    return False