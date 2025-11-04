import os
import re
import random
from typing import Dict, List

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
MODEL_NAME = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')


def _clean_bullets(items: List[str]) -> List[str]:
    cleaned = []
    for it in items:
        if not it:
            continue
        s = re.sub(r'^[-•\s]+', '', str(it)).strip()
        if s and s not in cleaned:
            cleaned.append(s)
    return cleaned[:8]


def _fallback_rule_based_swot(title: str, description: str) -> Dict[str, List[str]]:
    text = f"{title}. {description}".lower()

    strengths_keywords = [
        'scalable', 'unique', 'patent', 'proprietary', 'community', 'experienced', 'low cost', 'efficient', 'automation',
        'ai', 'ml', 'data', 'integrated', 'secure', 'privacy', 'open source', 'api', 'cloud', 'cross-platform', 'ux', 'engagement'
    ]
    weaknesses_keywords = [
        'expensive', 'complex', 'niche', 'regulation', 'dependence', 'dependency', 'manual', 'limited', 'beta', 'unproven', 'hardware'
    ]
    opportunities_keywords = [
        'market', 'trend', 'demand', 'remote', 'sustainability', 'green', 'compliance', 'automation', 'subscription', 'platform', 'partner'
    ]
    threats_keywords = [
        'competition', 'competitor', 'copy', 'regulation', 'privacy', 'security', 'recession', 'supply', 'churn', 'substitute', 'policy'
    ]

    strengths = [
        'Clear value proposition',
        'Potential for repeatable revenue',
        'Leverages existing capabilities',
    ]
    weaknesses = [
        'Requires initial customer education',
        'Potentially limited initial resources',
    ]
    opportunities = [
        'Growing interest in the problem space',
        'Partnerships with complementary products',
    ]
    threats = [
        'Well-funded incumbents can respond quickly',
        'Changing regulations may increase costs',
    ]

    def extend_if_keywords(bucket, kw_list, suggestion):
        if any(k in text for k in kw_list):
            bucket.append(suggestion)

    extend_if_keywords(strengths, strengths_keywords, 'Differentiation through technology and user experience')
    extend_if_keywords(strengths, ['community', 'open source'], 'Community-driven growth and contributions')
    extend_if_keywords(strengths, ['api', 'integrated', 'platform'], 'Ecosystem and integrations increase stickiness')

    extend_if_keywords(weaknesses, weaknesses_keywords, 'Complexity may slow onboarding and adoption')
    extend_if_keywords(weaknesses, ['hardware'], 'Capital intensity and supply constraints for hardware')
    extend_if_keywords(weaknesses, ['niche', 'limited'], 'Niche focus may cap addressable market initially')

    extend_if_keywords(opportunities, opportunities_keywords, 'Tailwinds from market trends and digitization')
    extend_if_keywords(opportunities, ['ai', 'ml', 'data'], 'AI/ML enhancements can unlock new value props')
    extend_if_keywords(opportunities, ['compliance', 'security', 'privacy'], 'Rising compliance needs create demand')

    extend_if_keywords(threats, threats_keywords, 'Fast followers could erode differentiation')
    extend_if_keywords(threats, ['privacy', 'security'], 'Security incidents could damage trust')

    # Add some variety
    random.seed(hash(text) % (2**32))
    optional_strengths = [
        'Low marginal cost to serve new customers',
        'Strong unit economics at scale',
        'Modular architecture enables rapid iteration',
    ]
    strengths += random.sample(optional_strengths, k=min(2, len(optional_strengths)))

    optional_weaknesses = [
        'Go-to-market motion not yet validated',
        'Dependency on third-party platforms introduces risk',
    ]
    weaknesses += random.sample(optional_weaknesses, k=min(1, len(optional_weaknesses)))

    optional_opportunities = [
        'International expansion over medium term',
        'Upsell and cross-sell into adjacent workflows',
    ]
    opportunities += random.sample(optional_opportunities, k=min(1, len(optional_opportunities)))

    optional_threats = [
        'Budget constraints among target customers',
        'Macroeconomic uncertainty may delay purchasing',
    ]
    threats += random.sample(optional_threats, k=min(1, len(optional_threats)))

    return {
        'provider': 'rule',
        'strengths': _clean_bullets(strengths),
        'weaknesses': _clean_bullets(weaknesses),
        'opportunities': _clean_bullets(opportunities),
        'threats': _clean_bullets(threats),
    }


def _openai_swot(title: str, description: str) -> Dict[str, List[str]]:
    # Lazy import to avoid dependency if not used
    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError('openai package not installed') from e

    if not OPENAI_API_KEY:
        raise RuntimeError('OPENAI_API_KEY not set')

    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
You are a strategic analyst. Produce a concise SWOT analysis for the following product idea.
Return ONLY compact JSON with keys: strengths, weaknesses, opportunities, threats. Values must be arrays of short bullet phrases (5-8 items each), no markdown, no numbering.

Title: {title}\nDescription: {description}
""".strip()

    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a precise strategy assistant. Output valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )
        content = resp.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f'OpenAI request failed: {e}')

    import json
    # Try to extract JSON
    try:
        # Sometimes models wrap in code fences
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            content = match.group(0)
        data = json.loads(content)
    except Exception as e:
        raise RuntimeError(f'Failed to parse OpenAI response as JSON: {e}. Raw: {content[:200]}')

    strengths = _clean_bullets(data.get('strengths', []))
    weaknesses = _clean_bullets(data.get('weaknesses', []))
    opportunities = _clean_bullets(data.get('opportunities', []))
    threats = _clean_bullets(data.get('threats', []))

    # Fallback to rule-based if any are empty
    if not (strengths and weaknesses and opportunities and threats):
        rb = _fallback_rule_based_swot(title, description)
        strengths = strengths or rb['strengths']
        weaknesses = weaknesses or rb['weaknesses']
        opportunities = opportunities or rb['opportunities']
        threats = threats or rb['threats']

    return {
        'provider': 'openai',
        'strengths': strengths,
        'weaknesses': weaknesses,
        'opportunities': opportunities,
        'threats': threats,
    }


def generate_swot(title: str, description: str, provider: str = 'rule') -> Dict[str, List[str]]:
    provider = (provider or 'rule').lower()
    if provider == 'openai':
        try:
            return _openai_swot(title, description)
        except Exception:
            # Fallback to rule-based
            return _fallback_rule_based_swot(title, description)
    return _fallback_rule_based_swot(title, description)

