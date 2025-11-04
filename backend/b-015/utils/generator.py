import re
import hashlib
from datetime import datetime

KNOWN_PAGES = [
    ('dashboard', ['dashboard', 'analytics', 'metric', 'kpi', 'report', 'insight']),
    ('login', ['login', 'sign in', 'signin', 'authenticate']),
    ('signup', ['signup', 'register', 'sign up', 'onboard', 'onboarding']),
    ('profile', ['profile', 'user profile', 'account']),
    ('settings', ['settings', 'preferences', 'configuration', 'config']),
    ('about', ['about', 'mission', 'team']),
    ('contact', ['contact', 'support', 'help', 'feedback']),
    ('pricing', ['pricing', 'plans', 'plan', 'tiers']),
    ('blog', ['blog', 'articles', 'news', 'posts']),
    ('search', ['search', 'discover', 'find']),
    ('cart', ['cart', 'basket', 'bag']),
    ('checkout', ['checkout', 'payment', 'pay', 'billing']),
    ('admin', ['admin', 'backoffice', 'moderation']),
    ('map', ['map', 'location', 'geography', 'geo', 'geolocation']),
    ('chat', ['chat', 'message', 'messaging', 'dm'])
]


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text).strip('-')
    return text or 'page'


def title_from_idea(idea: str) -> str:
    line = idea.strip().splitlines()[0]
    # Limit length
    if len(line) > 60:
        line = line[:57] + '...'
    # Title case, but keep acronyms
    def tc(w):
        return w if w.isupper() else w.capitalize()
    return ' '.join(tc(w) for w in re.split(r'(\s+)', line))


def extract_keywords(idea: str):
    s = idea.lower()
    keys = set()
    for base, alts in KNOWN_PAGES:
        for a in alts:
            if a in s:
                keys.add(base)
                break
    # Additional signals
    if any(k in s for k in ['landing', 'homepage', 'home']):
        keys.add('home')
    return keys


def choose_pages(idea: str):
    keys = extract_keywords(idea)
    pages = []

    # Home is default
    if 'home' in keys or True:
        pages.append({'name': 'Home', 'type': 'home'})

    mapping = {
        'dashboard': {'name': 'Dashboard', 'type': 'dashboard'},
        'login': {'name': 'Login', 'type': 'login'},
        'signup': {'name': 'Sign Up', 'type': 'signup'},
        'profile': {'name': 'Profile', 'type': 'profile'},
        'settings': {'name': 'Settings', 'type': 'settings'},
        'about': {'name': 'About', 'type': 'about'},
        'contact': {'name': 'Contact', 'type': 'contact'},
        'pricing': {'name': 'Pricing', 'type': 'pricing'},
        'blog': {'name': 'Blog', 'type': 'blog'},
        'search': {'name': 'Search', 'type': 'search'},
        'cart': {'name': 'Cart', 'type': 'cart'},
        'checkout': {'name': 'Checkout', 'type': 'checkout'},
        'admin': {'name': 'Admin', 'type': 'admin'},
        'map': {'name': 'Map', 'type': 'map'},
        'chat': {'name': 'Chat', 'type': 'chat'}
    }

    # Add matched pages in a sensible order
    order = ['dashboard','login','signup','profile','settings','pricing','blog','search','cart','checkout','about','contact','admin','map','chat']
    for key in order:
        if key in keys:
            pages.append(mapping[key])

    # If login without signup or vice versa, add the pair
    types = [p['type'] for p in pages]
    if 'login' in types and 'signup' not in types:
        pages.append(mapping['signup'])
    if 'signup' in types and 'login' not in types:
        pages.append(mapping['login'])

    # If cart without checkout or vice versa
    types = [p['type'] for p in pages]
    if 'cart' in types and 'checkout' not in types:
        pages.append(mapping['checkout'])

    # Deduplicate preserving order
    seen = set()
    unique_pages = []
    for p in pages:
        if p['type'] in seen:
            continue
        seen.add(p['type'])
        unique_pages.append(p)

    return unique_pages


def components_for_page(page_type: str, idea: str):
    # Common components per page type
    s = idea.lower()
    comps = []
    if page_type == 'home':
        comps = [
            {'type': 'hero', 'props': {}},
            {'type': 'feature-grid', 'props': {'count': 3}},
            {'type': 'cta', 'props': {'label': 'Get Started'}},
        ]
        if any(k in s for k in ['testimonial', 'review', 'social proof']):
            comps.append({'type': 'testimonials', 'props': {}})
    elif page_type == 'dashboard':
        comps = [
            {'type': 'stats', 'props': {'count': 4}},
            {'type': 'chart', 'props': {'title': 'Performance'}},
            {'type': 'table', 'props': {'rows': 5, 'cols': 5}},
        ]
    elif page_type == 'login':
        comps = [{'type': 'form-login', 'props': {}}]
    elif page_type == 'signup':
        comps = [{'type': 'form-signup', 'props': {}}]
    elif page_type == 'profile':
        comps = [
            {'type': 'profile-summary', 'props': {}},
            {'type': 'settings-form', 'props': {}}
        ]
    elif page_type == 'settings':
        comps = [{'type': 'settings-form', 'props': {}}]
    elif page_type == 'about':
        comps = [{'type': 'about', 'props': {}}]
    elif page_type == 'contact':
        comps = [
            {'type': 'form-contact', 'props': {}},
            {'type': 'info-blocks', 'props': {'count': 3}}
        ]
    elif page_type == 'pricing':
        comps = [{'type': 'pricing-plans', 'props': {'count': 3}}]
    elif page_type == 'blog':
        comps = [{'type': 'blog-list', 'props': {'count': 5}}]
    elif page_type == 'search':
        comps = [
            {'type': 'search-bar', 'props': {}},
            {'type': 'list', 'props': {'count': 8}}
        ]
    elif page_type == 'cart':
        comps = [
            {'type': 'cart-table', 'props': {'rows': 3}},
            {'type': 'cta', 'props': {'label': 'Proceed to Checkout'}}
        ]
    elif page_type == 'checkout':
        comps = [{'type': 'checkout-form', 'props': {}}]
    elif page_type == 'admin':
        comps = [
            {'type': 'admin-header', 'props': {}},
            {'type': 'table', 'props': {'rows': 8, 'cols': 6}}
        ]
    elif page_type == 'map':
        comps = [{'type': 'map', 'props': {}}]
    elif page_type == 'chat':
        comps = [{'type': 'chat', 'props': {}}]
    else:
        comps = [{'type': 'placeholder', 'props': {'label': page_type}}]
    return comps


def generate_structure(idea: str, theme: str = 'gray', fidelity: str = 'low', primary_color: str = '#4F46E5', seed: str | None = None):
    pages = choose_pages(idea)
    title = title_from_idea(idea)
    built_pages = []
    for p in pages:
        name = p['name']
        typ = p['type']
        slug = slugify(name)
        comps = components_for_page(typ, idea)
        built_pages.append({
            'name': name,
            'type': typ,
            'slug': slug,
            'components': comps
        })

    # Add navigation items
    nav = [{'label': p['name'], 'slug': p['slug']} for p in built_pages]

    # A deterministic accent color if not provided
    if not primary_color:
        h = hashlib.sha1(idea.encode('utf-8')).hexdigest()[:6]
        primary_color = f"#{h}"

    return {
        'seed': seed or hashlib.md5((idea + str(datetime.utcnow())).encode('utf-8')).hexdigest()[:10],
        'title': title,
        'idea': idea,
        'theme': theme,
        'fidelity': fidelity,
        'primary_color': primary_color,
        'pages': built_pages,
        'nav': nav
    }

