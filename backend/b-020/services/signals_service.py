from typing import List, Dict, Any
import statistics

from services.trends_service import get_trends
from services.news_service import get_news


def _compute_trend_momentum(timeseries: List[Dict[str, float]]) -> float:
    if not timeseries or len(timeseries) < 6:
        return 0.0
    values = [p['value'] for p in timeseries if p is not None and 'value' in p]
    if len(values) < 6:
        return 0.0
    n = max(3, len(values) // 10)
    recent = values[-n:]
    prev = values[-2*n:-n]
    if not prev or statistics.mean(prev) == 0:
        return 0.0
    momentum = (statistics.mean(recent) - statistics.mean(prev)) / (statistics.mean(prev) + 1e-9) * 100.0
    # Clamp extreme values to reduce sensitivity
    if momentum > 200:
        momentum = 200.0
    if momentum < -200:
        momentum = -200.0
    return float(momentum)


def _aggregate_sentiment(news_items: List[Dict[str, Any]]) -> float:
    if not news_items:
        return 0.0
    compounds = [it['sentiment']['compound'] for it in news_items if it and 'sentiment' in it and 'compound' in it['sentiment']]
    if not compounds:
        return 0.0
    return float(statistics.mean(compounds))


def _signal_from_metrics(trend_momentum_pct: float, sentiment_compound: float) -> Dict[str, Any]:
    # Simple rules-based signal
    # Thresholds
    trend_pos = 5.0
    trend_neg = -5.0
    sent_pos = 0.05
    sent_neg = -0.05

    if trend_momentum_pct >= trend_pos and sentiment_compound >= sent_pos:
        label = 'bullish'
        score = 1
    elif trend_momentum_pct <= trend_neg and sentiment_compound <= sent_neg:
        label = 'bearish'
        score = -1
    else:
        label = 'neutral'
        score = 0

    return {
        'label': label,
        'score': score,
        'thresholds': {
            'trend_pos_pct': trend_pos,
            'trend_neg_pct': trend_neg,
            'sent_pos': sent_pos,
            'sent_neg': sent_neg,
        }
    }


def generate_signals(keywords: List[str], geo: str = 'US', timeframe: str = 'now 7-d', news_lang: str = 'en', news_country: str = 'US', news_days: int = 7) -> Dict[str, Any]:
    trends = get_trends(keywords=keywords, geo=geo, timeframe=timeframe)
    response: Dict[str, Any] = {
        'meta': {
            'geo': geo,
            'timeframe': timeframe,
            'news_lang': news_lang,
            'news_country': news_country,
            'news_days': news_days,
        },
        'signals': {}
    }

    for kw in keywords:
        # Fetch news per keyword
        news = get_news(query=kw, lang=news_lang, country=news_country, days=news_days, max_items=30)
        news_sentiment = _aggregate_sentiment(news.get('items', []))

        ts = trends['data'].get(kw, {}).get('interest_over_time', [])
        trend_momentum_pct = _compute_trend_momentum(ts)

        sig = _signal_from_metrics(trend_momentum_pct, news_sentiment)

        response['signals'][kw] = {
            'trend_momentum_pct': trend_momentum_pct,
            'news_sentiment_compound': news_sentiment,
            'signal': sig,
            'counts': {
                'trend_points': len(ts),
                'news_items': news.get('count', 0)
            }
        }

    return response

