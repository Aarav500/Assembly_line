import hashlib
import random
import textwrap
from typing import List, Dict, Optional

_CANONICAL = {
    "child": {"child", "kid", "toddler", "children"},
    "pm": {"pm", "product_manager", "product manager", "product"},
    "ceo": {"ceo", "executive", "leader", "founder"},
}

_ALLOWED_TONES = {"positive", "neutral", "critical", "negative"}
_ALLOWED_STYLES = {"brief", "detailed"}


def normalize_persona_names(personas: List[str]) -> List[str]:
    normed = []
    for p in personas:
        lp = p.strip().lower()
        matched = None
        for canon, aliases in _CANONICAL.items():
            if lp == canon or lp in aliases:
                matched = canon
                break
        if not matched:
            raise ValueError(f"Unknown persona: {p}")
        if matched not in normed:
            normed.append(matched)
    return normed


def _seed_rng(seed_str: str) -> random.Random:
    h = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    # Use a portion of the hash to create a seed int
    return random.Random(int(h[:16], 16))


def _choose(rng: random.Random, options: List[str]) -> str:
    return rng.choice(options)


def _tone_to_scalar(tone: str) -> float:
    t = tone.lower()
    if t in {"critical", "negative"}:
        return -0.6
    if t in {"positive"}:
        return 0.7
    return 0.0  # neutral


def _apply_style(text: str, style: str, max_lines: Optional[int]) -> str:
    lines = [ln.rstrip() for ln in text.strip().splitlines() if ln.strip()]
    if style == "brief":
        lines = lines[: min(4, len(lines))]
    if max_lines is not None:
        lines = lines[: max(1, max_lines)]
    return "\n".join(lines)


def _child_reaction(message: str, tone_scalar: float, rng: random.Random, style: str, max_lines: Optional[int]) -> str:
    openers_pos = ["Wow!", "Yay!", "Cool!", "Awesome!", "Ooooh!"]
    openers_neu = ["Hmm.", "Okay.", "Oh.", "Alright."]
    openers_neg = ["Uh-oh.", "Hmmmm...", "I dunno.", "Eww."]

    emoji_pos = ["😄", "🤩", "🎉", "✨", "🧸"]
    emoji_neu = ["🤔", "🙃", "🧐"]
    emoji_neg = ["😬", "😕", "🙈", "😟"]

    if tone_scalar > 0.2:
        opener = _choose(rng, openers_pos) + " " + _choose(rng, emoji_pos)
    elif tone_scalar < -0.2:
        opener = _choose(rng, openers_neg) + " " + _choose(rng, emoji_neg)
    else:
        opener = _choose(rng, openers_neu) + " " + _choose(rng, emoji_neu)

    asks = [
        "Can I try it?",
        "Will it be fun?",
        "Does it have colors?",
        "Can it make sounds?",
        "What if it breaks?",
        "Can we make it bigger?",
        "Can it have stickers?",
        "Can I show my friends?",
    ]

    likes = [
        "I like it because it sounds fun!",
        "It looks shiny in my head!",
        "It sounds fast!",
        "I think my friends would say 'woah'!",
        "It makes me smile!",
    ]

    worries = [
        "But what if it's hard?",
        "What if it's too loud?",
        "Will I get bored?",
        "Do I have to share?",
        "Is it sticky?",
    ]

    parts = [
        opener,
        f"So, you said: '{message}'.",
    ]

    if tone_scalar >= 0.2:
        parts.append(_choose(rng, likes))
    elif tone_scalar <= -0.2:
        parts.append(_choose(rng, worries))
    else:
        parts.append(_choose(rng, ["I think it's kinda neat.", "Maybe it's okay.", "I wonder how it works."]))

    parts.append(_choose(rng, asks))

    text = "\n".join(parts)
    return _apply_style(text, style, max_lines)


def _pm_reaction(message: str, tone_scalar: float, rng: random.Random, style: str, max_lines: Optional[int]) -> str:
    sentiment = "Supportive" if tone_scalar > 0.2 else ("Concerned" if tone_scalar < -0.2 else "Neutral")

    summary = f"Summary: {message.strip()}"
    user_story_prefaces = [
        "As a user, I want",
        "As a customer, I want",
        "As a power user, I want",
        "As an admin, I want",
    ]
    user_story = f"User story: {_choose(rng, user_story_prefaces)} {message.strip()} so that I achieve a clear benefit."

    risks = [
        "Scope creep and unclear MVP",
        "Technical complexity vs. timeline",
        "Ambiguous success metrics",
        "Dependencies on external systems",
        "Onboarding friction",
        "Privacy or compliance constraints",
    ]
    metrics = [
        "Activation rate",
        "Adoption (WAU/MAU)",
        "Retention (D30)",
        "Task success rate",
        "NPS/CSAT",
        "Conversion to paid",
    ]
    experiments = [
        "Landing page smoke test",
        "Fake door in navigation",
        "Concierge MVP with manual ops",
        "Usability test with 5 users",
        "A/B test of core value prop",
    ]

    leaning = "green" if tone_scalar > 0.2 else ("red" if tone_scalar < -0.2 else "yellow")

    lines = [
        f"PM read ({sentiment}):",  # tone-aware
        summary,
        user_story,
        "—",
        "Risks:",
        f"- {_choose(rng, risks)}",
        f"- {_choose(rng, risks)}",
        f"- {_choose(rng, risks)}",
        "Success metrics:",
        f"- {_choose(rng, metrics)}",
        f"- {_choose(rng, metrics)}",
        f"- {_choose(rng, metrics)}",
        "Suggested experiments:",
        f"- {_choose(rng, experiments)}",
        f"- {_choose(rng, experiments)}",
        f"- {_choose(rng, experiments)}",
        "Decision signal:",
        f"- Current signal: {leaning.upper()} (subject to validation)",
        "Next steps:",
        "- Define crisp MVP and acceptance criteria",
        "- Set baseline metrics and guardrails",
        "- Run smallest-viable test and review",
    ]

    text = "\n".join(lines)
    return _apply_style(text, style, max_lines)


def _ceo_reaction(message: str, tone_scalar: float, rng: random.Random, style: str, max_lines: Optional[int]) -> str:
    opener_pos = [
        "This aligns with our thesis.",
        "Promising vector for durable growth.",
        "Clear upside with manageable risk.",
    ]
    opener_neu = [
        "Let's evaluate this with discipline.",
        "Potentially interesting; needs sharper framing.",
        "Signal unclear; proceed methodically.",
    ]
    opener_neg = [
        "Risks likely outweigh near-term return.",
        "Not obviously core to our strategy.",
        "Opportunity cost appears high.",
    ]

    if tone_scalar > 0.2:
        opener = _choose(rng, opener_pos)
    elif tone_scalar < -0.2:
        opener = _choose(rng, opener_neg)
    else:
        opener = _choose(rng, opener_neu)

    vectors = [
        "Strategic fit: Does this compound our core advantage?",
        "Market: TAM/SAM with realistic share capture.",
        "Moat: Strengthens switching costs or data advantage.",
        "Economics: Path to attractive unit margins.",
        "Timing: Why now vs. later?",
        "Org readiness: Do we have the leaders and focus?",
    ]

    capital = [
        "Capex minimal; opex scalable",
        "Requires focused senior bandwidth",
        "High learning value even if we pivot",
        "Opportunity cost against top-3 bets",
    ]

    decision = _choose(rng, [
        "Sponsor a 6-week validation sprint with clear exit criteria.",
        "Defer until core metrics hit target; re-evaluate next quarter.",
        "Proceed if we secure a lighthouse customer.",
        "Kill for now; not core to our 12-month plan.",
    ])

    lines = [
        f"CEO view: {opener}",
        f"Proposal: {message.strip()}",
        "—",
        *_dedupe_pick(rng, vectors, 4),
        "Capital allocation:",
        f"- {_choose(rng, capital)}",
        f"- {_choose(rng, capital)}",
        "Risk/Return:",
        f"- Downside: {_choose(rng, ['focus dilution','brand risk','execution drag','vendor lock-in'])}",
        f"- Upside: {_choose(rng, ['incremental ARR','retention lift','strategic optionality','category leadership'])}",
        "Decision:",
        f"- {decision}",
    ]

    text = "\n".join(lines)
    return _apply_style(text, style, max_lines)


def _dedupe_pick(rng: random.Random, items: List[str], k: int) -> List[str]:
    k = max(0, min(k, len(items)))
    items_copy = items[:]
    rng.shuffle(items_copy)
    selected = items_copy[:k]
    return [f"- {s}" for s in selected]


def generate_reactions(
    message: str,
    personas: List[str],
    tone: str = "neutral",
    style: str = "detailed",
    max_lines: Optional[int] = None,
    seed: Optional[str] = None,
) -> Dict[str, str]:
    if tone not in _ALLOWED_TONES:
        raise ValueError(f"Unknown tone: {tone}. Allowed: {sorted(_ALLOWED_TONES)}")
    if style not in _ALLOWED_STYLES:
        raise ValueError(f"Unknown style: {style}. Allowed: {sorted(_ALLOWED_STYLES)}")

    # Deterministic seed based on message and optional seed
    seed_material = f"{message}\n{tone}\n{style}\n{seed or ''}"
    rng = _seed_rng(seed_material)
    tscalar = _tone_to_scalar(tone)

    outputs: Dict[str, str] = {}
    for persona in personas:
        if persona == "child":
            outputs[persona] = _child_reaction(message, tscalar, rng, style, max_lines)
        elif persona == "pm":
            outputs[persona] = _pm_reaction(message, tscalar, rng, style, max_lines)
        elif persona == "ceo":
            outputs[persona] = _ceo_reaction(message, tscalar, rng, style, max_lines)
        else:
            raise ValueError(f"Unsupported persona: {persona}")

    return outputs

