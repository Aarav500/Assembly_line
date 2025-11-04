from datetime import datetime
from decision_logging import DecisionLogger

class AgentEngine:
    def __init__(self, agent_id: str, version: str = "1.0.0"):
        self.agent_id = agent_id
        self.version = version

    def run(self, input_payload: dict | str, decision_logger: DecisionLogger) -> dict:
        # Capture context
        context = {
            'agent_version': self.version,
            'run_at': datetime.utcnow().isoformat(),
        }
        decision_logger.log_context(context, message='Agent context at run')
        # Capture input
        decision_logger.log_input(input_payload)

        # Normalize input
        if isinstance(input_payload, dict):
            text = str(input_payload.get('input') or input_payload.get('text') or '')
            meta = {k: v for k, v in input_payload.items() if k not in ('input', 'text')}
        else:
            text = str(input_payload)
            meta = {}

        # Simple heuristic: choose action based on keywords and length
        text_lower = text.lower()
        rationale_parts = []
        action = 'process'

        if 'urgent' in text_lower or 'asap' in text_lower:
            action = 'escalate'
            rationale_parts.append("Keyword indicating urgency detected ('urgent' or 'asap').")
        elif len(text) > 180:
            action = 'summarize'
            rationale_parts.append('Input length exceeds 180 characters; summarization preferred.')
        elif 'error' in text_lower or 'fail' in text_lower:
            action = 'create_incident'
            rationale_parts.append("Problem indicators detected ('error'/'fail').")
        else:
            rationale_parts.append('No urgency or error indicators; proceed with normal processing.')

        # Add metadata considerations
        if meta.get('customer_tier') == 'gold':
            rationale_parts.append('Customer tier is gold; elevate priority by one level if applicable.')
            if action == 'process':
                action = 'prioritize'

        rationale = ' '.join(rationale_parts)
        decision_logger.log_rationale(rationale, data={'input_meta': meta})

        # Perform simulated action
        outcome = {
            'selected_action': action,
            'notes': 'Simulated execution completed.'
        }
        decision_logger.log_action(action, message='Action selected and executed', data={'execution': 'simulated'})
        decision_logger.log_decision(
            decision=f"Agent chose to {action}",
            outcome=outcome,
            rationale=rationale
        )
        return outcome

