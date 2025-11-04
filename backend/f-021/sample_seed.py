import requests
import random
from datetime import datetime, timedelta

URL = 'http://localhost:5000/alerts'

sources = ['prometheus', 'cloudwatch', 'nagios', 'app-logs']
services = ['auth', 'payments', 'search', 'db', 'cache']
severities = ['info', 'low', 'medium', 'high', 'critical']
categories = ['login', 'latency', 'error', 'cpu', 'memory', 'network']
messages = [
    'High CPU usage detected on node',
    'Authentication failure for user john',
    'DB connection timeout occurred',
    'Payment gateway response slow',
    'Cache hit rate dropped significantly',
    'Network packet loss above threshold',
    'User login failed due to invalid password',
    'Service latency exceeded SLO',
    'Error rate increased in search service',
]

now = datetime.utcnow()

for i in range(120):
    ts = now - timedelta(minutes=random.randint(0, 60*24))
    payload = {
        'timestamp': ts.isoformat() + 'Z',
        'source': random.choice(sources),
        'service': random.choice(services),
        'severity': random.choices(severities, weights=[4,4,3,2,1])[0],
        'category': random.choice(categories),
        'message': random.choice(messages) + f" #{random.randint(1,5)}"
    }
    r = requests.post(URL, json=payload, timeout=5)
    print(i, r.status_code, r.json())

