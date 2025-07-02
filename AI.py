import asyncio
import sqlite3
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from pathlib import Path
import os
import time
import random
import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('ai_news')

# Load environment variables (optional)
load_dotenv(dotenv_path=Path(".env"))

# Simple SQLite Database
class SimpleNewsDB:
    def __init__(self, db_path="ai_news.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize simple database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    content TEXT,
                    source TEXT,
                    scraped_date TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            conn.close()
            logger.info("✅ Database ready")
            
        except Exception as e:
            logger.error(f"❌ Database error: {e}")
    
    def save_news(self, title, url, content, source):
        """Save one news article"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO news (title, url, content, source, scraped_date)
                VALUES (?, ?, ?, ?, ?)
            """, (title, url, content, source, datetime.datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            logger.info(f"💾 Saved: {title[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"❌ Save error: {e}")
            return False

# Initialize database
db = SimpleNewsDB()

# Helper function
async def human_delay(min_ms=1000, max_ms=3000):
    """Human-like delay"""
    delay = random.randint(min_ms, max_ms) / 1000
    await asyncio.sleep(delay)

# Main search function
async def search_trending_ai_news():
    """Search for the most UP-TO-DATE TRENDING AI news and store it"""
    logger.info("🚀 Starting search for TRENDING AI news...")
    
    try:
        async with async_playwright() as p:
            # Launch browser with better stealth settings
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--no-sandbox',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()
            
            # Try multiple trending AI news sources
            trending_sources = [
                {
                    "name": "Google News - AI Trending",
                    "url": "https://news.google.com/search?q=AI%20artificial%20intelligence%20latest%20breaking&hl=en-US&gl=US&ceid=US%3Aen",
                    "strategy": "google_news"
                },
                {
                    "name": "TechCrunch AI - Latest",
                    "url": "https://techcrunch.com/category/artificial-intelligence/",
                    "strategy": "techcrunch"
                },
                {
                    "name": "Google Search - Today's AI News",  
                    "url": "https://www.google.com/search?q=\"AI+news\"+OR+\"artificial+intelligence\"+today+breaking+latest&tbm=nws&tbs=qdr:d",
                    "strategy": "google_search"
                }
            ]
            
            best_article = None
            
            for source in trending_sources:
                logger.info(f"🔍 Trying {source['name']}...")
                
                try:
                    await page.goto(source['url'], wait_until="networkidle", timeout=30000)
                    await human_delay(2000, 4000)
                    
                    # Handle cookie consent
                    try:
                        consent_selectors = [
                            'button:has-text("Accept")',
                            'button:has-text("I agree")', 
                            'button:has-text("Accept all")',
                            '[aria-label*="accept"]',
                            '.accept-button'
                        ]
                        for selector in consent_selectors:
                            button = await page.query_selector(selector)
                            if button:
                                await button.click()
                                await human_delay(1000, 2000)
                                break
                    except:
                        pass
                    
                    # Extract trending articles based on source strategy
                    if source['strategy'] == 'google_news':
                        article = await extract_from_google_news(page)
                    elif source['strategy'] == 'techcrunch':
                        article = await extract_from_techcrunch(page)
                    else:  # google_search
                        article = await extract_from_google_search(page)
                    
                    if article:
                        article['source_type'] = source['name']
                        article['trending_score'] = calculate_trending_score(article)
                        
                        if not best_article or article['trending_score'] > best_article['trending_score']:
                            best_article = article
                            logger.info(f"🏆 New best article found: {article['title'][:50]}... (Score: {article['trending_score']})")
                    
                    await human_delay(3000, 5000)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to extract from {source['name']}: {e}")
                    continue
            
            if not best_article:
                logger.error("❌ No trending AI news found from any source")
                await browser.close()
                return
            
            # Get full content of the best trending article
            logger.info(f"📖 Getting full content for trending article...")
            best_article = await get_full_article_content(page, best_article)
            
            # Save to database
            success = db.save_news(
                title=best_article['title'],
                url=best_article['url'],
                content=best_article.get('content', ''),
                source=best_article.get('source', 'Unknown')
            )
            
            if success:
                print("\n" + "="*70)
                print("🔥 TRENDING AI NEWS FOUND AND SAVED!")
                print("="*70)
                print(f"📰 Title: {best_article['title']}")
                print(f"🌐 Source: {best_article.get('source', 'Unknown')}")
                print(f"📊 Trending Score: {best_article['trending_score']}")
                print(f"🔗 URL: {best_article['url']}")
                print(f"📝 Content: {len(best_article.get('content', ''))} characters")
                print(f"💾 Saved to: {db.db_path}")
                print(f"🚀 Found via: {best_article['source_type']}")
                print("="*70)
            else:
                print("❌ Failed to save article")
            
            await human_delay(2000, 3000)
            await browser.close()
            
    except Exception as e:
        logger.error(f"❌ Search failed: {e}")
        print("❌ Search failed. Please check your internet connection and try again.")

async def extract_from_google_news(page):
    """Extract trending article from Google News"""
    try:
        article = await page.evaluate("""
            () => {
                // Look for the first news article in Google News
                const articles = document.querySelectorAll('article, [data-n-tid]');
                
                for (let article of articles) {
                    const titleElement = article.querySelector('h3, h4, [role="heading"]');
                    const linkElement = article.querySelector('a[href*="http"]');
                    
                    if (titleElement && linkElement) {
                        const title = titleElement.innerText || titleElement.textContent || '';
                        const url = linkElement.href;
                        
                        if (title.length > 10 && url.includes('http')) {
                            return {
                                title: title.trim(),
                                url: url,
                                source: 'Google News'
                            };
                        }
                    }
                }
                return null;
            }
        """)
        return article
    except Exception as e:
        logger.warning(f"Error extracting from Google News: {e}")
        return None

async def extract_from_techcrunch(page):
    """Extract latest article from TechCrunch AI"""
    try:
        article = await page.evaluate("""
            () => {
                // Look for TechCrunch articles
                const articles = document.querySelectorAll('article, .post-block, .wp-block-tc23-post-picker');
                
                for (let article of articles) {
                    const titleElement = article.querySelector('h2 a, h3 a, .post-block__title a');
                    
                    if (titleElement) {
                        const title = titleElement.innerText || titleElement.textContent || '';
                        const url = titleElement.href;
                        
                        if (title.length > 10 && url) {
                            return {
                                title: title.trim(),
                                url: url.startsWith('http') ? url : 'https://techcrunch.com' + url,
                                source: 'TechCrunch'
                            };
                        }
                    }
                }
                return null;
            }
        """)
        return article
    except Exception as e:
        logger.warning(f"Error extracting from TechCrunch: {e}")
        return None

async def extract_from_google_search(page):
    """Extract trending article from Google Search News results"""
    try:
        article = await page.evaluate("""
            () => {
                // Look for news results in Google Search
                const links = Array.from(document.querySelectorAll('a[href]'));
                
                for (let link of links) {
                    const href = link.href;
                    const text = link.innerText || link.textContent || '';
                    
                    // Check if it's a valid news link with AI-related content
                    if (href && 
                        href.includes('http') && 
                        !href.includes('google.com') &&
                        !href.includes('youtube.com') &&
                        text.length > 15 &&
                        text.length < 300) {
                        
                        const lowerText = text.toLowerCase();
                        if (lowerText.includes('ai') || 
                            lowerText.includes('artificial intelligence') ||
                            lowerText.includes('machine learning') ||
                            lowerText.includes('chatgpt') ||
                            lowerText.includes('openai')) {
                            
                            return {
                                title: text.trim(),
                                url: href,
                                source: 'Google Search'
                            };
                        }
                    }
                }
                return null;
            }
        """)
        return article
    except Exception as e:
        logger.warning(f"Error extracting from Google Search: {e}")
        return None

def calculate_trending_score(article):
    """Calculate how trending/recent an article is"""
    score = 0
    title = article.get('title', '').lower()
    
    # High trending keywords
    trending_keywords = [
        'breaking', 'just in', 'latest', 'new', 'announces', 'launches',
        'today', 'this week', 'now', 'update', 'development',
        'breakthrough', 'major', 'revolutionary', 'game-changing'
    ]
    
    # AI company mentions (more relevant/trending)
    ai_companies = [
        'openai', 'google', 'microsoft', 'meta', 'apple', 'nvidia',
        'anthropic', 'deepmind', 'hugging face', 'stability ai'
    ]
    
    # Hot AI topics
    hot_topics = [
        'gpt', 'chatgpt', 'claude', 'gemini', 'llama', 'copilot',
        'agi', 'autonomous', 'robotics', 'ai safety', 'regulation'
    ]
    
    # Score based on trending keywords
    for keyword in trending_keywords:
        if keyword in title:
            score += 20
    
    # Score based on AI companies
    for company in ai_companies:
        if company in title:
            score += 15
    
    # Score based on hot topics
    for topic in hot_topics:
        if topic in title:
            score += 10
    
    # Bonus for source reliability
    source = article.get('source', '').lower()
    if 'techcrunch' in source:
        score += 10
    elif 'google news' in source:
        score += 15
    
    return score

async def get_full_article_content(page, article):
    """Get full content of the trending article"""
    logger.info(f"📖 Getting full content for: {article['title'][:50]}...")
    
    try:
        await page.goto(article['url'], wait_until="networkidle", timeout=30000)
        await human_delay(2000, 4000)
        
        # Extract full article content with better selectors
        content = await page.evaluate("""
            () => {
                // Try comprehensive selectors for article content
                const selectors = [
                    'article .content',
                    'article .post-content',
                    '.article-content',
                    '.post-body',
                    '.entry-content', 
                    'main article',
                    '.story-body',
                    '[data-module="ArticleBody"]',
                    '.article-wrap',
                    '.post-content-body'
                ];
                
                for (const selector of selectors) {
                    const element = document.querySelector(selector);
                    if (element) {
                        const text = element.innerText || element.textContent || '';
                        if (text.length > 200) {
                            return text.trim();
                        }
                    }
                }
                
                // Fallback: try to get main content area
                const main = document.querySelector('main');
                if (main) {
                    const text = main.innerText || main.textContent || '';
                    if (text.length > 200) {
                        return text.trim();
                    }
                }
                
                // Last resort: body content (filtered)
                const bodyText = document.body.innerText || document.body.textContent || '';
                return bodyText.length > 100 ? bodyText.trim() : 'Content extraction limited';
            }
        """)
        
        # Get source domain
        source = await page.evaluate("() => window.location.hostname")
        
        # Limit content length for storage
        if len(content) > 3000:
            content = content[:3000] + "..."
        
        article['content'] = content
        article['source'] = source
        article['content_extracted'] = True
        
        logger.info(f"✅ Successfully extracted content ({len(content)} chars)")
        
    except Exception as e:
        logger.error(f"❌ Error getting full content: {e}")
        article['content'] = f"Trending AI article from {article.get('source', 'unknown source')}. Full content extraction failed."
        article['content_extracted'] = False
    
    return article

# Simple function to view saved news
def view_saved_news():
    """View the saved news from database"""
    try:
        conn = sqlite3.connect("ai_news.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT title, url, source, scraped_date, content 
            FROM news 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        articles = cursor.fetchall()
        conn.close()
        
        if articles:
            print(f"\n📚 SAVED NEWS ({len(articles)} articles):")
            print("="*60)
            
            for i, (title, url, source, date, content) in enumerate(articles, 1):
                print(f"\n{i}. 📰 {title}")
                print(f"   🌐 Source: {source}")
                print(f"   📅 Date: {date[:10]}")
                print(f"   🔗 URL: {url}")
                
                # Show content preview
                preview = content[:150] + "..." if len(content) > 150 else content
                print(f"   📝 Preview: {preview}")
        else:
            print("📭 No saved articles found")
            
    except Exception as e:
        logger.error(f"❌ Error viewing news: {e}")

# Main execution
if __name__ == "__main__":
    print("🤖 Simple AI News Finder")
    print("="*30)
    print("🔥 Search for TRENDING up-to-date AI news")
    print("📊 Smart trending score algorithm")
    print("🚫 No login required!")
    print("="*30)
    
    try:
        # Check command line arguments
        if len(os.sys.argv) > 1:
            if os.sys.argv[1] == "--view":
                view_saved_news()
            else:
                print("Usage: python script.py [--view]")
        else:
            # Default: search for trending AI news
            asyncio.run(search_trending_ai_news())
            
    except KeyboardInterrupt:
        logger.info("⚠️ Process stopped by user")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        
    print("\n✅ Done!")