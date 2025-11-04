from typing import Dict, Any
import feedparser
import html
import re
import time

from utils.cache import news_cache
from utils.sentiment import analyze_sentiment
from config import SETTINGS


def _strip_html(text: str) -> str:
    if not text:
        return ''
    # remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # unescape entities
    return html.unescape(text)


def get_news(query: str, lang: str = 'en', country: str = 'US', days: int = 7, max_items: int = 30) -> Dict[str, Any]:
    # Build Google News RSS URL
    # Example: https://news.google.com/rss/search?q=tesla+when:7d&hl=en-US&gl=US&ceid=US:en
    query_param = query.replace(' ', '+')
    url = f"https://news.google.com/rss/search?q={query_param}+when:{days}d&hl={lang}-{country}&gl={country}&ceid={country}:{lang}"

    cache_key = f"news::{query}::{lang}::{country}::{days}::{max_items}"
    cached = news_cache.get(cache_key)
    if cached is not None:
        return cached

    feed = feedparser.parse(url)
    items = []

    for entry in feed.entries[:max_items]:
        title = entry.get('title', '')
        link = entry.get('link', '')
        summary = _strip_html(entry.get('summary', '') or entry.get('description', ''))
        published = None
        if 'published_parsed' in entry and entry.published_parsed:
            published = time.strftime('%Y-%m-%dT%H:%M:%SZ', entry.published_parsed)
        source_title = None
        try:
            source = entry.get('source')
            if isinstance(source, dict):
                source_title = source.get('title')
            elif hasattr(source, 'title'):
                source_title = source.title
        except Exception:
            source_title = None

        sentiment = analyze_sentiment(f"{title}. {summary}")

        items.append({
            'title': title,
            'link': link,
            'summary': summary,
            'published': published,
            'source': source_title,
            'sentiment': sentiment,
        })

    result = {
        'query': query,
        'lang': lang,
        'country': country,
        'days': days,
        'count': len(items),
        'items': items,
        'source_url': url,
    }

    news_cache.set(cache_key, result, ttl=SETTINGS['CACHE_NEWS_TTL'])
    return result

