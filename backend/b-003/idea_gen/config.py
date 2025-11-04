# Default configuration for idea generation

default_categories = [
    "listicle",
    "how_to",
    "challenge",
    "twist",
    "comparison",
    "prompt",
    "metaphor",
]

templates_by_category = {
    "listicle": [
        "Top {n} {adjective} ideas for {topic}",
        "{n} quick ways to {verb_phrase} {topic}",
        "{n} clever {topic} hacks you can try today",
        "{n} {adjective} {topic} tips for busy people",
        "{n} simple {topic} experiments to try this week",
    ],
    "how_to": [
        "How to {verb_phrase} {topic} {twist}",
        "A step-by-step guide to {verb_phrase} {topic}",
        "How to master {topic} in {timeframe}",
        "How to avoid common pitfalls with {topic}",
    ],
    "challenge": [
        "{n}-day {topic} challenge: {twist}",
        "Can you {goal} with {topic}? {twist}",
        "Weekend challenge: {verb_phrase} {topic} without spending a dime",
        "{topic} sprint: {n} tasks in {timeframe}",
    ],
    "twist": [
        "What if you {twist} with {topic}?",
        "The unexpected side of {topic}: {twist}",
        "Flip the script: {topic} but {twist}",
        "{topic}, but make it {adjective}",
    ],
    "comparison": [
        "{topic} vs {alt}: {n} surprising differences",
        "Old-school vs modern: {topic} compared to {alt}",
        "DIY {topic} vs outsourced: which wins?",
        "{n} reasons {topic} beats {alt} (sometimes)",
    ],
    "prompt": [
        "Brainstorm: {n} prompts for {topic} that are {adjective}",
        "Creative prompts to explore {topic}",
        "{n} journaling prompts about {topic}",
        "Writing ideas: explore {topic} from {n} angles",
    ],
    "metaphor": [
        "If {topic} were a {object}, how would you {verb_phrase} it?",
        "Imagine {topic} as a journey: {n} checkpoints",
        "{topic} explained with a {object}",
        "What does {topic} look like through a {object}?",
    ],
}

# Pools for dynamic substitution
verb_phrases = [
    "level up",
    "optimize",
    "rethink",
    "remix",
    "streamline",
    "kickstart",
    "revamp",
    "unlock",
    "supercharge",
    "reimagine",
]

adjectives_generic = [
    "practical",
    "bold",
    "surprising",
    "beginner-friendly",
    "advanced",
    "time-saving",
    "budget-friendly",
    "data-driven",
    "creative",
    "high-impact",
]

# Tone-specific adjectives and closers inserted optionally
adjectives_by_tone = {
    "funny": ["witty", "cheeky", "playful", "punny"],
    "informative": ["insightful", "comprehensive", "practical"],
    "inspirational": ["uplifting", "motivational", "visionary"],
    "casual": ["laid-back", "chill", "easy"],
    "serious": ["rigorous", "evidence-based", "methodical"],
}

closers_by_tone = {
    "funny": ["(with a dash of humor)", "(no boring bits)", "(puns included)"],
    "informative": ["(backed by facts)", "(clear and concise)", "(with examples)"],
    "inspirational": ["(dream big)", "(aim higher)", "(fuel your why)"],
    "casual": ["(no stress)", "(keep it simple)", "(low effort)"],
    "serious": ["(deep dive)", "(no fluff)", "(research-first)"],
}

twists = [
    "without breaking the bank",
    "using only what's on hand",
    "in just 10 minutes a day",
    "with zero jargon",
    "the minimalist way",
    "like a pro",
    "with a community twist",
    "the sustainable way",
]

timeframes = [
    "a weekend",
    "7 days",
    "30 days",
    "an afternoon",
    "one hour",
]

objects = [
    "toolbox",
    "garden",
    "recipe",
    "map",
    "puzzle",
    "kit",
    "workout",
]

alt_targets = [
    "the traditional approach",
    "modern methods",
    "DIY hacks",
    "outsourced solutions",
    "quick fixes",
    "long-term strategies",
]

# Default constraint values
DEFAULT_CONSTRAINTS = {
    "min_length": 16,
    "max_length": 120,
    "must_include_all": [],
    "must_include_any": [],
    "must_exclude": [],
    "tones": [],
    "categories": [],
    "prefixes": [],
    "suffixes": [],
    "avoid_duplicates_by_stem": True,
    "allow_numbers": True,
}

