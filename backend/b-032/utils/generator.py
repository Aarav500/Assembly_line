from textwrap import dedent


def _fallback(text, default):
    t = (text or '').strip()
    return t if t else default


def generate_business_plan(data):
    name = _fallback(data.get('company_name'), 'Your Company')
    tagline = _fallback(data.get('tagline'), 'One-line value proposition')
    problem = _fallback(data.get('problem'), 'Describe the painful customer problem.')
    solution = _fallback(data.get('solution'), 'Explain your product and how it solves the problem.')
    market = _fallback(data.get('target_market'), 'Who are your customers and how big is the market?')
    model = _fallback(data.get('business_model'), 'How do you make money? Pricing, unit economics.')
    gtm = _fallback(data.get('go_to_market'), 'How will you reach and convert customers?')
    competition = _fallback(data.get('competition'), 'Who else solves this? Why you win?')
    advantage = _fallback(data.get('unfair_advantage'), 'Moat: data, network, IP, speed, distribution.')
    team = _fallback(data.get('team'), 'Founders and key roles. Why you?')
    financials = _fallback(data.get('financials'), 'Revenue, growth, margins, key metrics and forecasts.')
    ask = _fallback(data.get('ask'), 'How much are you raising? Use of funds and milestones.')

    exec_summary = f"{name} — {tagline}\nWe solve: {problem[:180].strip()}..." if len(problem) > 180 else f"{name} — {tagline}\nWe solve: {problem}"

    plan = dedent(f"""
    === Executive Summary ===
    {exec_summary}

    === Problem ===
    {problem}

    === Solution ===
    {solution}

    === Market ===
    {market}

    === Business Model ===
    {model}

    === Go-To-Market ===
    {gtm}

    === Competition & Differentiation ===
    {competition}

    === Unfair Advantage / Moat ===
    {advantage}

    === Team ===
    {team}

    === Financials & Metrics ===
    {financials}

    === Funding & Use of Proceeds ===
    {ask}

    === Milestones (Next 12 Months) ===
    - Build: MVP -> Beta -> GA
    - Sell: First 10 lighthouse customers -> 100 -> 500
    - Metrics: Retention > 90%, CAC payback < 6 months
    - Team: Key hires in eng, sales, and success
    """).strip()

    slides = [
        {"title": name, "content": f"{tagline}\n\n{exec_summary}"},
        {"title": "Problem", "content": problem},
        {"title": "Solution", "content": solution},
        {"title": "Market", "content": market},
        {"title": "Business Model", "content": model},
        {"title": "Go-To-Market", "content": gtm},
        {"title": "Competition", "content": competition},
        {"title": "Unfair Advantage", "content": advantage},
        {"title": "Team", "content": team},
        {"title": "Financials", "content": financials},
        {"title": "Ask / Use of Funds", "content": ask},
        {"title": "Contact", "content": f"{name}\n{tagline}"},
    ]

    return plan, slides

