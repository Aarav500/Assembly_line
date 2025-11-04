import re
from textwrap import dedent

class PitchGenerator:
    def __init__(self):
        pass

    def _clean(self, text, default=""):
        if not text:
            return default
        # Normalize spaces and ensure proper sentence punctuation.
        t = re.sub(r"\s+", " ", str(text)).strip()
        return t

    def _ensure_period(self, text):
        if not text:
            return text
        text = text.strip()
        if text[-1] in [".", "!", "?"]:
            return text
        return text + "."

    def _cap(self, words, max_words):
        tokens = re.findall(r"\S+", words or "")
        if len(tokens) <= max_words:
            return words.strip()
        trimmed = " ".join(tokens[:max_words])
        # Try to trim back to the last sentence end if present.
        last_period = trimmed.rfind(".")
        if last_period != -1 and last_period > max_words * 0.5:
            return trimmed[: last_period + 1].strip()
        return trimmed.strip() + "..."

    def _normalize_tone(self, tone):
        tone = (tone or "concise").strip().lower()
        allowed = {"concise", "confident", "friendly", "visionary"}
        if tone not in allowed:
            return "concise"
        return tone

    def _style_prefix(self, tone):
        if tone == "confident":
            return ""
        if tone == "friendly":
            return ""
        if tone == "visionary":
            return ""
        return ""

    def generate_elevator(self, d):
        name = self._clean(d.get("project_name", ""))
        tagline = self._clean(d.get("tagline", ""))
        problem = self._clean(d.get("problem", ""))
        solution = self._clean(d.get("solution", ""))
        users = self._clean(d.get("target_users", ""))
        value = self._clean(d.get("value_proposition", ""))
        diff = self._clean(d.get("differentiation", ""))
        model = self._clean(d.get("business_model", ""))
        traction = self._clean(d.get("traction", ""))
        ask = self._clean(d.get("ask", ""))

        parts = []
        if tagline:
            parts.append(self._ensure_period(f"{name}: {tagline}"))
        else:
            parts.append(self._ensure_period(f"{name} helps {users or 'its target users'} by solving {problem.lower()}"))

        parts.append(self._ensure_period(f"The problem: {problem}"))
        parts.append(self._ensure_period(f"Our solution: {solution}"))
        if value:
            parts.append(self._ensure_period(f"Why it matters: {value}"))
        if diff:
            parts.append(self._ensure_period(f"What makes us different: {diff}"))
        if model:
            parts.append(self._ensure_period(f"Business model: {model}"))
        if traction:
            parts.append(self._ensure_period(f"Early traction: {traction}"))
        if ask:
            parts.append(self._ensure_period(f"Our ask: {ask}"))

        paragraph = " ".join(parts)
        paragraph = self._cap(paragraph, 110)  # ~45-75 seconds
        return paragraph

    def generate_two_min(self, d):
        name = self._clean(d.get("project_name", ""))
        tagline = self._clean(d.get("tagline", ""))
        problem = self._clean(d.get("problem", ""))
        solution = self._clean(d.get("solution", ""))
        users = self._clean(d.get("target_users", ""))
        value = self._clean(d.get("value_proposition", ""))
        market = self._clean(d.get("market_size", ""))
        model = self._clean(d.get("business_model", ""))
        traction = self._clean(d.get("traction", ""))
        competition = self._clean(d.get("competition", ""))
        diff = self._clean(d.get("differentiation", ""))
        gtm = self._clean(d.get("go_to_market", ""))
        team = self._clean(d.get("team", ""))
        ask = self._clean(d.get("ask", ""))

        lines = []
        intro = f"Hi, I'm here to introduce {name}."
        if tagline:
            intro = f"{name}: {tagline}."
        lines.append(intro)
        lines.append(f"We serve {users or 'our target customers'}, who face: {problem}.")
        lines.append(f"Our solution: {solution}.")
        if value:
            lines.append(f"Core value: {value}.")
        if market:
            lines.append(f"Market opportunity: {market}.")
        if model:
            lines.append(f"Revenue model: {model}.")
        if competition or diff:
            comp_line = "Competitive landscape: "
            if competition:
                comp_line += competition
            if diff:
                comp_line += (" " if competition else "") + f"Our edge: {diff}."
            lines.append(self._ensure_period(comp_line))
        if gtm:
            lines.append(f"Go-to-market: {gtm}.")
        if traction:
            lines.append(f"Traction so far: {traction}.")
        if team:
            lines.append(f"Team: {team}.")
        if ask:
            lines.append(f"We're currently seeking: {ask}.")
        lines.append("Thank you.")

        paragraph = " ".join(self._ensure_period(x) for x in lines)
        paragraph = self._cap(paragraph, 320)  # ~2 minutes @ ~150 wpm
        return paragraph

    def generate_one_pager(self, d):
        name = self._clean(d.get("project_name", ""))
        tagline = self._clean(d.get("tagline", ""))
        problem = self._clean(d.get("problem", ""))
        solution = self._clean(d.get("solution", ""))
        users = self._clean(d.get("target_users", ""))
        value = self._clean(d.get("value_proposition", ""))
        market = self._clean(d.get("market_size", ""))
        model = self._clean(d.get("business_model", ""))
        traction = self._clean(d.get("traction", ""))
        competition = self._clean(d.get("competition", ""))
        diff = self._clean(d.get("differentiation", ""))
        gtm = self._clean(d.get("go_to_market", ""))
        team = self._clean(d.get("team", ""))
        roadmap = self._clean(d.get("roadmap", ""))
        ask = self._clean(d.get("ask", ""))
        contact = self._clean(d.get("contact", ""))

        lines = []
        title = name
        if tagline:
            title = f"{name} — {tagline}"
        lines.append(title)
        lines.append("")

        # Problem & Solution
        lines.append("Problem")
        lines.append(self._ensure_period(problem))
        lines.append("")

        lines.append("Solution")
        sol_parts = []
        sol_parts.append(self._ensure_period(f"Target users: {users or 'N/A'}"))
        sol_parts.append(self._ensure_period(f"Product/approach: {solution}"))
        if value:
            sol_parts.append(self._ensure_period(f"Value proposition: {value}"))
        if diff:
            sol_parts.append(self._ensure_period(f"Differentiation: {diff}"))
        lines.extend(sol_parts)
        lines.append("")

        # Market & Model
        if market or model:
            lines.append("Market & Business Model")
            if market:
                lines.append(self._ensure_period(f"Market size/opportunity: {market}"))
            if model:
                lines.append(self._ensure_period(f"Monetization: {model}"))
            lines.append("")

        # Competition
        if competition:
            lines.append("Competition")
            comp_text = self._ensure_period(competition)
            if diff:
                comp_text = comp_text + " " + self._ensure_period(f"Our edge: {diff}")
            lines.append(comp_text)
            lines.append("")

        # Go-to-Market & Traction
        if gtm or traction:
            lines.append("Go-to-Market & Traction")
            if gtm:
                lines.append(self._ensure_period(f"Go-to-market: {gtm}"))
            if traction:
                lines.append(self._ensure_period(f"Traction: {traction}"))
            lines.append("")

        # Team & Roadmap
        if team or roadmap:
            lines.append("Team & Roadmap")
            if team:
                lines.append(self._ensure_period(f"Team: {team}"))
            if roadmap:
                lines.append(self._ensure_period(f"Roadmap: {roadmap}"))
            lines.append("")

        # The Ask
        if ask:
            lines.append("The Ask")
            lines.append(self._ensure_period(ask))
            lines.append("")

        # Contact
        if contact:
            lines.append("Contact")
            lines.append(self._ensure_period(contact))

        text = "\n".join(lines).strip()
        text = self._cap(text, 800)  # keep readable within 1-page
        return text

    def generate_all(self, data):
        tone = self._normalize_tone(data.get("tone"))
        elevator = self.generate_elevator(data)
        two_min = self.generate_two_min(data)
        one_pager = self.generate_one_pager(data)

        def wc(t):
            return len(re.findall(r"\S+", t or ""))

        return {
            "elevator_pitch": elevator,
            "two_min_pitch": two_min,
            "one_pager": one_pager,
            "meta": {
                "word_counts": {
                    "elevator_pitch": wc(elevator),
                    "two_min_pitch": wc(two_min),
                    "one_pager": wc(one_pager),
                }
            },
        }

