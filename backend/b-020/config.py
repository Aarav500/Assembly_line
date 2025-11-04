import os

SETTINGS = {
    'CACHE_TRENDS_TTL': int(os.getenv('CACHE_TRENDS_TTL', '600')),
    'CACHE_NEWS_TTL': int(os.getenv('CACHE_NEWS_TTL', '1800')),
    'PORT': int(os.getenv('PORT', '5000')),
    'DEBUG': os.getenv('DEBUG', '0') in ('1', 'true', 'True'),
}

