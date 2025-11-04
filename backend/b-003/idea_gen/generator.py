import random
from typing import Dict, List, Any, Tuple
from .config import (
    DEFAULT_CONSTRAINTS,
    default_categories,
    templates_by_category,
    verb_phrases,
    adjectives_generic,
    adjectives_by_tone,
    closers_by_tone,
    twists,
    timeframes,
    objects,
    alt_targets,
)
from .normalize import normalize_for_dedupe, contains_any, contains_all, violates_exclusions


class IdeaGenerator:
    def __init__(self):
        pass

    def _merge_constraints(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        c = dict(DEFAULT_CONSTRAINTS)
        if constraints:
            for k, v in constraints.items():
                c[k] = v
        # Normalize lists
        for key in [
            "must_include_all",
            "must_include_any",
            "must_exclude",
            "tones",
            "categories",
            "prefixes",
            "suffixes",
        ]:
            if not isinstance(c.get(key), list):
                c[key] = [] if c.get(key) in (None, "", False) else [str(c.get(key))]
            c[key] = [str(x) for x in c[key]]
        # Bounds sanity
        c["min_length"] = max(1, int(c.get("min_length", DEFAULT_CONSTRAINTS["min_length"])))
        c["max_length"] = max(c["min_length"], int(c.get("max_length", DEFAULT_CONSTRAINTS["max_length"])))
        c["avoid_duplicates_by_stem"] = bool(c.get("avoid_duplicates_by_stem", True))
        c["allow_numbers"] = bool(c.get("allow_numbers", True))
        return c

    def _choose_category(self, rng: random.Random, allowed: List[str]) -> str:
        pool = allowed if allowed else default_categories
        # Weight listicle and how_to slightly higher
        weighted = []
        for cat in pool:
            weight = 2 if cat in ("listicle", "how_to") else 1
            weighted.extend([cat] * weight)
        return rng.choice(weighted)

    def _pick_tone(self, rng: random.Random, tones: List[str]) -> str:
        if tones:
            return rng.choice(tones)
        # default: sometimes no tone, sometimes random
        options = [""] + list(adjectives_by_tone.keys())
        return rng.choice(options)

    def _num_for_list(self, rng: random.Random) -> int:
        return rng.choice([3, 5, 7, 8, 9, 10, 12, 15, 21])

    def _build_from_template(
        self,
        rng: random.Random,
        category: str,
        template: str,
        topic: str,
        tone: str,
        allow_numbers: bool,
    ) -> str:
        n = self._num_for_list(rng) if allow_numbers else "many"
        adj = rng.choice(adjectives_generic)
        if tone and tone in adjectives_by_tone and rng.random() < 0.7:
            adj = rng.choice(adjectives_by_tone[tone])
        vp = rng.choice(verb_phrases)
        tw = rng.choice(twists)
        tf = rng.choice(timeframes)
        obj = rng.choice(objects)
        alt = rng.choice(alt_targets)
        goal = rng.choice(["stay on budget", "learn fast", "have fun", "ship daily", "stay consistent"]) 

        s = template.format(
            n=n,
            adjective=adj,
            verb_phrase=vp,
            twist=tw,
            timeframe=tf,
            object=obj,
            topic=topic,
            alt=alt,
            goal=goal,
        )

        # Tone closer sometimes
        if tone and tone in closers_by_tone and rng.random() < 0.5:
            s = f"{s} {rng.choice(closers_by_tone[tone])}"
        return " ".join(s.split())

    def _maybe_prefix_suffix(self, rng: random.Random, s: str, prefixes: List[str], suffixes: List[str]) -> str:
        if prefixes:
            if rng.random() < 0.7:
                s = f"{rng.choice(prefixes).strip()} {s}"
        if suffixes:
            if rng.random() < 0.7:
                s = f"{s} {rng.choice(suffixes).strip()}"
        return " ".join(s.split())

    def _enforce_inclusions(self, s: str, must_all: List[str], must_any: List[str]) -> str:
        out = s
        low = out.lower()
        # Ensure ALL terms from must_all exist
        for term in must_all:
            if term.lower() not in low:
                out = f"{out} {term}"
                low = out.lower()
        # Ensure ANY term from must_any exists
        if must_any and not contains_any(low, must_any):
            out = f"{out} {must_any[0]}"
        return " ".join(out.split())

    def _valid(self, s: str, c: Dict[str, Any]) -> Tuple[bool, str]:
        if len(s) < c["min_length"]:
            return False, "too_short"
        if len(s) > c["max_length"]:
            return False, "too_long"
        if c["must_exclude"] and violates_exclusions(s, c["must_exclude"]):
            return False, "must_exclude"
        if c["must_include_all"] and not contains_all(s, c["must_include_all"]):
            return False, "missing_all"
        if c["must_include_any"] and not contains_any(s, c["must_include_any"]):
            return False, "missing_any"
        return True, "ok"

    def generate(self, topic: str, count: int = 50, constraints: Dict[str, Any] = None, seed: Any = None) -> Dict[str, Any]:
        c = self._merge_constraints(constraints or {})
        rng = random.Random(seed)

        ideas: List[str] = []
        seen = set()
        attempts = 0
        max_attempts = max(150, count * 30)
        warnings: List[str] = []

        allowed_categories = [cat for cat in c["categories"] if cat in templates_by_category] if c["categories"] else []

        while len(ideas) < count and attempts < max_attempts:
            attempts += 1
            category = self._choose_category(rng, allowed_categories)
            template = rng.choice(templates_by_category[category])
            tone = self._pick_tone(rng, c["tones"])
            s = self._build_from_template(rng, category, template, topic.strip(), tone, c["allow_numbers"])
            s = self._maybe_prefix_suffix(rng, s, c["prefixes"], c["suffixes"])
            # Enforce inclusions after base build
            s = self._enforce_inclusions(s, c["must_include_all"], c["must_include_any"])
            ok, reason = self._valid(s, c)
            if not ok:
                continue
            key = normalize_for_dedupe(s, by_stem=c["avoid_duplicates_by_stem"])
            if key in seen:
                continue
            seen.add(key)
            ideas.append(s)

        if len(ideas) < count:
            warnings.append(
                f"Only generated {len(ideas)} out of requested {count}. Consider relaxing constraints or increasing max_length."
            )

        return {
            "topic": topic,
            "constraints": c,
            "ideas": ideas,
            "meta": {
                "requested": count,
                "generated": len(ideas),
                "attempts": attempts,
                "seed": seed,
                "warnings": warnings,
            },
        }

