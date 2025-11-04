from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from threading import Lock

_analyzer = None
_lock = Lock()


def _get_analyzer() -> SentimentIntensityAnalyzer:
    global _analyzer
    if _analyzer is None:
        with _lock:
            if _analyzer is None:
                _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def analyze_sentiment(text: str):
    if not text:
        return {'neg': 0.0, 'neu': 0.0, 'pos': 0.0, 'compound': 0.0}
    analyzer = _get_analyzer()
    scores = analyzer.polarity_scores(text)
    return {
        'neg': float(scores.get('neg', 0.0)),
        'neu': float(scores.get('neu', 0.0)),
        'pos': float(scores.get('pos', 0.0)),
        'compound': float(scores.get('compound', 0.0))
    }

