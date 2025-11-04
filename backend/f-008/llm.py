import json
import os
import textwrap
from datetime import datetime


class LLMClient:
    def __init__(self):
        self.provider = os.getenv('LLM_PROVIDER', 'openai').lower()
        self.model = os.getenv('LLM_MODEL', 'gpt-4o-mini')
        self.timeout = float(os.getenv('LLM_TIMEOUT', '30'))
        self._has_openai = False
        self._client = None

        if self.provider == 'openai':
            try:
                from openai import OpenAI  # type: ignore
                self._client = OpenAI()
                # Will raise if key missing when actually calling API; we detect now by env
                self._has_openai = bool(os.getenv('OPENAI_API_KEY'))
            except Exception:
                self._client = None
                self._has_openai = False

    def _system_prompt(self):
        return (
            "You are an SRE/Incident Commander assistant. "
            "Given noisy incident data, produce a concise, structured incident report in JSON. "
            "Be factual, avoid speculation unless clearly marked as hypothesis. "
            "Use crisp language suitable for an executive summary. "
            "Return ONLY JSON, no markdown."
        )

    def _user_prompt(self, raw_input: str, context: str, severity: str) -> str:
        guidelines = textwrap.dedent(
            f"""
            Task:
            - Summarize the incident from the provided raw inputs (logs, alerts, chat transcripts, metrics descriptions).
            - Draft a preliminary Root Cause Analysis (RCA) using a 5-Whys style, and list likely contributing factors.
            - Provide a high-signal timeline (UTC, ISO-8601) with key events only.
            - Recommend immediate remediation and follow-up action items.

            Constraints:
            - Output MUST be a single JSON object with these keys:
              title, summary, impact, timeline, root_cause_hypothesis, contributing_factors,
              detection, remediation, action_items, severity, status
            - Types:
              - title: string
              - summary: string (3-6 sentences)
              - impact: string (scope, duration, affected users/services, financial/SLI impact)
              - timeline: array of objects: {{"ts": ISO-8601 string (UTC), "event": string}}
              - root_cause_hypothesis: string (note uncertainty if applicable)
              - contributing_factors: array of strings
              - detection: string (how detected, signal-to-noise)
              - remediation: string (what was done or should be done immediately)
              - action_items: array of objects: {{"owner": string or null, "item": string, "eta": string or null}}
              - severity: string (one of: Sev1, Sev2, Sev3, Sev4, Sev5, low, medium, high)
              - status: string (e.g., draft, monitoring, resolved)
            - If uncertain, state assumptions explicitly in the text fields.
            - Use UTC timestamps. If timestamps are missing in input, infer approximate ordering without fabricating exact minutes; use today's date if unknown.

            Input:
            - Severity hint: {severity}
            - Operational context (optional): {context or '[none]'}
            - Raw incident material (verbatim):\n\n{raw_input}

            Produce the JSON now.
            """
        ).strip()
        return guidelines

    def _call_openai(self, system: str, user: str) -> str:
        # Use Chat Completions with structured output enforcement
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            timeout=self.timeout,
        )
        return completion.choices[0].message.content or "{}"

    def _fallback_local(self, raw_input: str, context: str, severity: str) -> dict:
        # Minimal heuristic summarization to enable offline/dev use
        lines = [ln.strip() for ln in raw_input.splitlines() if ln.strip()]
        title = (lines[0][:120] if lines else "Incident Report")
        now = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        first_events = lines[:5]
        timeline = [{"ts": now, "event": ev[:200]} for ev in first_events] or [{"ts": now, "event": "Incident detected"}]
        contributing = []
        if 'timeout' in raw_input.lower():
            contributing.append('Network timeout conditions')
        if 'cpu' in raw_input.lower():
            contributing.append('High CPU saturation')
        if 'deploy' in raw_input.lower() or 'release' in raw_input.lower():
            contributing.append('Recent deployment')
        result = {
            "title": title,
            "summary": "Automated draft summary based on provided logs. Please refine with actual details.",
            "impact": "Impact undetermined from local analysis. Review affected services and user scope.",
            "timeline": timeline,
            "root_cause_hypothesis": "Preliminary hypothesis based on heuristic signals; requires validation.",
            "contributing_factors": contributing or ["Insufficient data"],
            "detection": "Detected via provided raw inputs.",
            "remediation": "Mitigate by reverting recent risky changes, scaling affected services, and clearing error conditions.",
            "action_items": [
                {"owner": None, "item": "Validate root cause with metrics and logs", "eta": None},
                {"owner": None, "item": "Add alerting for early signals", "eta": None}
            ],
            "severity": severity or "unknown",
            "status": "draft"
        }
        return result

    def generate_incident_report(self, raw_input: str, context: str = "", severity: str = ""):
        system = self._system_prompt()
        user = self._user_prompt(raw_input=raw_input, context=context, severity=severity)

        if self.provider == 'openai' and self._has_openai and self._client is not None:
            content = self._call_openai(system, user)
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Attempt to repair trivial JSON issues
                content_fixed = content.strip()
                if content_fixed.startswith('```'):
                    content_fixed = content_fixed.strip('`')
                try:
                    data = json.loads(content_fixed)
                except Exception as e:
                    # Fallback
                    data = self._fallback_local(raw_input, context, severity)
            return data, self.model
        else:
            # Local fallback for dev/testing without API key
            data = self._fallback_local(raw_input, context, severity)
            return data, 'local-fallback'

