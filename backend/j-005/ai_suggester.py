import os
import json
from typing import List, Dict, Any

class AICodeSuggester:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except Exception:
                self.client = None

    def suggest(self, language: str, code: str, cursor: int, hint: str | None = None) -> List[Dict[str, Any]]:
        # Try model-backed suggestions if possible
        if self.client is not None:
            try:
                return self._suggest_openai(language, code, cursor, hint)
            except Exception:
                pass
        # Fallback heuristic suggestions
        return self._suggest_heuristic(language, code, cursor, hint)

    def _suggest_openai(self, language: str, code: str, cursor: int, hint: str | None) -> List[Dict[str, Any]]:
        prompt = {
            "instruction": "Return code completion suggestions for the given code and cursor position.",
            "requirements": [
                "Respond strictly as a JSON object with key 'suggestions' (array).",
                "Each suggestion must include: label, insertText, kind, detail.",
                "insertText should be the code to insert at the cursor position.",
                "Maximum 3 concise suggestions."
            ],
            "language": language,
            "cursor": cursor,
            "hint": hint or "",
            "code": code
        }
        resp = self.client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.2,
            response_format={"type": "json_object"},
            input=[
                {"role": "system", "content": "You are an expert code completion engine."},
                {"role": "user", "content": json.dumps(prompt)}
            ]
        )
        text = resp.output_text
        data = json.loads(text)
        suggestions = data.get("suggestions")
        if not isinstance(suggestions, list):
            raise ValueError("Invalid AI response schema")
        normalized = []
        for s in suggestions[:3]:
            label = str(s.get("label") or "Suggestion")
            insert_text = str(s.get("insertText") or "")
            kind = str(s.get("kind") or "completion")
            detail = str(s.get("detail") or "")
            if insert_text:
                normalized.append({
                    "label": label,
                    "insertText": insert_text,
                    "kind": kind,
                    "detail": detail
                })
        if not normalized:
            return self._suggest_heuristic(language, code, cursor, hint)
        return normalized

    def _suggest_heuristic(self, language: str, code: str, cursor: int, hint: str | None) -> List[Dict[str, Any]]:
        language = (language or "").lower()
        before = code[:cursor]
        after = code[cursor:]
        line_start = before.rfind("\n") + 1
        line = before[line_start:]
        indent = ""  # compute current indent
        for ch in line:
            if ch == " ":
                indent += " "
            elif ch == "\t":
                indent += "\t"
            else:
                break

        suggestions: List[Dict[str, Any]] = []

        if language == "python":
            if line.strip().startswith("def ") and not line.strip().endswith(":"):
                name = line.strip()[4:].strip() or "function_name(args)"
                insert = ":\n    pass\n"
                suggestions.append({
                    "label": "Complete function signature",
                    "insertText": insert,
                    "kind": "completion",
                    "detail": "Add colon and body"
                })
            if line.rstrip().endswith(":"):
                suggestions.append({
                    "label": "Indent new block",
                    "insertText": "\n" + indent + "    ",
                    "kind": "snippet",
                    "detail": "Start indented block"
                })
            if line.strip().startswith("for ") and " in " in line and not line.strip().endswith(":"):
                suggestions.append({
                    "label": "Complete for-loop",
                    "insertText": ":\n" + indent + "    pass\n",
                    "kind": "completion",
                    "detail": "Add colon and body"
                })
            if line.strip() == "if":
                suggestions.append({
                    "label": "if condition snippet",
                    "insertText": " condition:\n" + indent + "    pass\n",
                    "kind": "snippet",
                    "detail": "Basic if"
                })
            # Common patterns
            suggestions.append({
                "label": "Print debug",
                "insertText": "print(\"DEBUG:\", )",
                "kind": "snippet",
                "detail": "Insert print()"
            })
            suggestions.append({
                "label": "Main guard",
                "insertText": "\n\nif __name__ == '__main__':\n    main()\n",
                "kind": "snippet",
                "detail": "Python entry point"
            })
        else:
            suggestions.append({
                "label": "Todo comment",
                "insertText": "// TODO: ...",
                "kind": "snippet",
                "detail": "Add TODO"
            })

        # Deduplicate and cap at 5
        seen = set()
        unique: List[Dict[str, Any]] = []
        for s in suggestions:
            key = (s.get("label"), s.get("insertText"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(s)
            if len(unique) >= 5:
                break
        return unique

