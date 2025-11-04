import textwrap
from typing import Dict
from .base import Strategy

class BaselineStrategy(Strategy):
    name = "baseline"
    description = "Echoes the prompt in a direct response form."

    def run(self, prompt: str, config: dict) -> str:
        p = (prompt or "").strip()
        if not p:
            return "No input provided."
        return f"Here is a direct response to your request:\n{p}"

class ExpandStrategy(Strategy):
    name = "expand"
    description = "Expands the prompt with step-by-step elaboration."

    def run(self, prompt: str, config: dict) -> str:
        p = (prompt or "").strip()
        if not p:
            return "No input provided."
        base = "Let's explore this step by step:"
        lines = [base]
        # Create simple elaboration points from chunks of the prompt
        words = [w.strip(",.!?;:") for w in p.split() if w.strip()]
        segments = []
        chunk = []
        for i, w in enumerate(words):
            chunk.append(w)
            if len(chunk) >= 6 or i == len(words) - 1:
                segments.append(" ".join(chunk))
                chunk = []
        for idx, seg in enumerate(segments[:5], start=1):
            lines.append(f"{idx}) Consider: {seg}.")
        lines.append("Finally, tie ideas together with a clear takeaway that addresses the core request succinctly.")
        return "\n".join(lines)

class BulletStrategy(Strategy):
    name = "bullet"
    description = "Reformats the prompt into concise bullet points."

    def run(self, prompt: str, config: dict) -> str:
        p = (prompt or "").strip()
        if not p:
            return "No input provided."
        # Split on simple delimiters for bullets
        sentences = []
        buf = []
        for ch in p:
            buf.append(ch)
            if ch in ".!?\n":
                s = "".join(buf).strip()
                if s:
                    sentences.append(s)
                buf = []
        if buf:
            s = "".join(buf).strip()
            if s:
                sentences.append(s)
        if not sentences:
            sentences = [p]
        bullets = [f"- {s.strip()}" for s in sentences]
        return "\n".join(bullets)

class ConciseStrategy(Strategy):
    name = "concise"
    description = "Produces a short, single-sentence takeaway."

    def run(self, prompt: str, config: dict) -> str:
        p = (prompt or "").strip().replace("\n", " ")
        if not p:
            return "No input provided."
        short = p[:180].strip()
        if len(p) > 180:
            short += "..."
        return f"In short: {short}"

class StructureStrategy(Strategy):
    name = "structure"
    description = "Organizes response into sections: Context, Approach, Answer."

    def run(self, prompt: str, config: dict) -> str:
        p = (prompt or "").strip()
        context = textwrap.fill(p, width=80)
        approach = (
            "- Identify goals and constraints\n"
            "- Outline steps with clear rationale\n"
            "- Validate against the prompt's needs"
        )
        answer = "Provide a succinct conclusion that addresses the core question directly."
        return f"Context\n-------\n{context}\n\nApproach\n--------\n{approach}\n\nAnswer\n------\n{answer}"

def build_strategies_registry() -> Dict[str, Strategy]:
    strategies = [
        BaselineStrategy(),
        ExpandStrategy(),
        BulletStrategy(),
        ConciseStrategy(),
        StructureStrategy(),
    ]
    return {s.name: s for s in strategies}

