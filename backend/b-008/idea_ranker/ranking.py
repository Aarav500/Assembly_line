import math
import re
from typing import List, Dict, Any, Tuple

DEFAULT_WEIGHTS = {"feasibility": 0.34, "novelty": 0.33, "market": 0.33}

_STOPWORDS = set(
    """
    a an and are as at be but by for from has have i if in into is it its of on or our out so that the their them they this to we with you your
    """.split()
)

_COMPLEXITY_KEYWORDS = {
    "blockchain","quantum","fusion","self-driving","autonomous","autonomous vehicle","hardware","semiconductor","space","satellite",
    "genomics","biotech","robotics","drone","metaverse","brain-computer","bci","nanotech","foundation model","llm training",
}

_BUZZWORDS = {"disrupt","revolutionize","groundbreaking","moonshot","impossible","magical","10x"}

_FEASIBILITY_POSITIVE = {
    "prototype","mvp","open source","opensource","api","apis","sdk","nocode","no-code","lowcode","low-code","cloud","aws","gcp","azure",
    "python","flask","django","react","flutter","node","typescript","postgres","sqlite","existing data","public dataset","dataset","csv"
}

_REGULATORY = {"regulated","compliance","hipaa","gdpr","soc2","pci","faa","fda","finra","sec"}

_ARCHETYPES = [
    "food delivery app",
    "ride sharing platform",
    "photo sharing social network",
    "messaging app",
    "task manager todo app",
    "generic chatbot assistant",
    "online marketplace",
    "e-commerce store",
    "fitness tracker",
    "job board",
    "news aggregator",
    "travel booking site",
    "coupon deals site",
]

_COMMON_WORDS = set(
    """
    app platform service tool system solution users people business company customer product market simple easy fast secure ai ml data analytics insight report
    share social photo video message task manage todo online shop store e-commerce marketplace fitness health track tracke tracker finance budget news travel deal
    delivery food ride car taxi driver chat bot chatbot assistant website mobile web cloud software
    """.split()
)

_MARKET_POSITIVE = {
    "enterprise","b2b","b2c","smb","mid-market","global","worldwide","healthcare","finance","insurance","education","logistics","manufacturing","retail","government","public sector",
    "compliance","security","privacy","automation","cost saving","reduce cost","reduce churn","increase revenue","conversion","productivity"
}

_MONETIZATION = {
    "subscription","subscriptions","saas","license","licensing","ads","advertising","transaction fee","take rate","commission","freemium","usage-based","tiered pricing","upsell"
}

_SMALL_NICHE = {"hobby","niche","local only","community","student only","students only","club"}

_AUDIENCE = {
    "enterprise": 0.05,
    "smb": 0.04,
    "consumer": 0.02,
    "students": -0.03,
}

_CLICHE_PATTERNS = [r"uber\s+for\b", r"tinder\s+for\b", r"airbnb\s+for\b"]

_word_re = re.compile(r"[a-zA-Z][a-zA-Z\-']+")
_money_re = re.compile(r"\$?\s*([0-9]{1,3}(?:[,\s][0-9]{3})+|[0-9]+)(?:\s*(million|billion|k|m|bn))?", re.IGNORECASE)


def _tokenize(text: str) -> List[str]:
    text = (text or "").lower()
    return [w for w in _word_re.findall(text)]


def _stem(word: str) -> str:
    # Extremely simple stemmer for our heuristic similarity
    w = word.lower()
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _tokenset(text: str) -> set:
    toks = [_stem(t) for t in _tokenize(text) if t not in _STOPWORDS]
    return set(t for t in toks if t)


def _contains_phrase(text: str, phrase: str) -> bool:
    return phrase in (text or "").lower()


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def score_feasibility(title: str, description: str) -> float:
    text = f"{title} \n {description}".lower()
    toks = _tokenset(text)
    score = 0.6

    # Complexity penalties
    complexity_hits = 0
    for kw in _COMPLEXITY_KEYWORDS:
        if kw in text:
            complexity_hits += 1
    score -= min(0.3, 0.05 * complexity_hits)

    # Buzzword penalty
    buzz_hits = sum(1 for b in _BUZZWORDS if b in toks)
    score -= min(0.15, 0.03 * buzz_hits)

    # Positive feasibility signals
    pos_hits = 0
    for kw in _FEASIBILITY_POSITIVE:
        if kw in text:
            pos_hits += 1
    score += min(0.25, 0.03 * pos_hits)

    # Regulatory friction
    reg_hits = sum(1 for r in _REGULATORY if r in text)
    score -= min(0.15, 0.08 * reg_hits)

    # Length/clarity effect
    word_count = len(_tokenize(text))
    if 30 <= word_count <= 200:
        score += 0.05
    elif word_count > 220:
        score -= 0.05
    elif word_count < 10:
        score -= 0.05

    return _clamp(score)


def score_novelty(title: str, description: str) -> float:
    text = f"{title} \n {description}".lower()
    idea_set = _tokenset(text)

    # Baseline from distance to archetypes
    max_sim = 0.0
    for arch in _ARCHETYPES:
        sim = _jaccard(idea_set, _tokenset(arch))
        if sim > max_sim:
            max_sim = sim
    novelty = 1.0 - max_sim

    # Rare word bonus
    if idea_set:
        rare_ratio = len([w for w in idea_set if w not in _COMMON_WORDS]) / max(1, len(idea_set))
        if rare_ratio > 0.3:
            novelty += 0.1

    # Cliche pattern penalty
    for pat in _CLICHE_PATTERNS:
        if re.search(pat, text):
            novelty -= 0.1

    return _clamp(novelty)


def _parse_money(text: str) -> float:
    # Returns approx dollars as float
    total = 0.0
    for m in _money_re.finditer(text):
        num_s = m.group(1)
        unit = (m.group(2) or '').lower()
        try:
            num = float(num_s.replace(",", "").replace(" ", ""))
        except ValueError:
            continue
        mult = 1.0
        if unit in ("k",):
            mult = 1e3
        elif unit in ("m", "million"):
            mult = 1e6
        elif unit in ("bn", "billion"):
            mult = 1e9
        total += num * mult
    return total


def score_market(title: str, description: str) -> float:
    text = f"{title} \n {description}".lower()
    toks = _tokenset(text)
    score = 0.5

    # Domain/benefit signals
    dom_hits = sum(1 for d in _MARKET_POSITIVE if d in text)
    score += min(0.25, 0.04 * dom_hits)

    # Monetization clarity
    mon_hits = sum(1 for m in _MONETIZATION if m in text)
    score += min(0.2, 0.05 * mon_hits)

    # Audience hints
    for k, v in _AUDIENCE.items():
        if k in text:
            score += v

    # Niche penalty
    niche_hits = sum(1 for n in _SMALL_NICHE if n in text)
    score -= min(0.15, 0.05 * niche_hits)

    # Competition awareness (if notes 'crowded' or 'saturated')
    if "crowded" in toks or "saturated" in toks:
        score -= 0.05

    # Geographic scale
    if "global" in toks or "worldwide" in toks:
        score += 0.04
    if "local" in toks and "only" in toks:
        score -= 0.04

    # TAM heuristics from money mentions
    dollars = _parse_money(text)
    if dollars > 0:
        # Map to 0..0.2 via log scale
        tam_bonus = min(0.2, math.log10(max(1.0, dollars)) / 12.0)
        score += tam_bonus

    return _clamp(score)


def normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    w = {
        "feasibility": float(weights.get("feasibility", DEFAULT_WEIGHTS["feasibility"])),
        "novelty": float(weights.get("novelty", DEFAULT_WEIGHTS["novelty"])),
        "market": float(weights.get("market", DEFAULT_WEIGHTS["market"]))
    }
    s = sum(max(0.0, v) for v in w.values())
    if s <= 0:
        return DEFAULT_WEIGHTS.copy()
    return {k: max(0.0, v) / s for k, v in w.items()}


def score_idea(idea: Dict[str, str]) -> Dict[str, float]:
    title = (idea.get("title") or "").strip()
    description = (idea.get("description") or "").strip()
    feas = score_feasibility(title, description)
    nov = score_novelty(title, description)
    mkt = score_market(title, description)
    return {"feasibility": feas, "novelty": nov, "market": mkt}


def rank_ideas(ideas: List[Dict[str, str]], weights: Dict[str, float] = None) -> Dict[str, Any]:
    w = normalize_weights(weights or DEFAULT_WEIGHTS)
    scored = []
    for idx, idea in enumerate(ideas):
        subscores = score_idea(idea)
        overall = (
            w["feasibility"] * subscores["feasibility"] +
            w["novelty"] * subscores["novelty"] +
            w["market"] * subscores["market"]
        )
        scored.append({
            "index": idx,
            "title": idea.get("title", ""),
            "description": idea.get("description", ""),
            "scores": subscores,
            "overall": round(float(overall), 4)
        })

    scored.sort(key=lambda x: x["overall"], reverse=True)
    for rank, item in enumerate(scored, start=1):
        item["rank"] = rank
        # round subscores for cleaner output
        item["scores"] = {k: round(float(v), 4) for k, v in item["scores"].items()}

    return {
        "weights": w,
        "results": scored
    }

