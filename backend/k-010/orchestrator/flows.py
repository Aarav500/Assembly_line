from typing import Dict, Any
from orchestrator.engine import Flow, Step, StepResult, ExecutionContext


class GenerateNumbersStep(Step):
    def __init__(self):
        super().__init__("generate_numbers")

    def execute(self, context: ExecutionContext) -> StepResult:
        state_delta: Dict[str, Any] = {}
        # Idempotent: only set if not already present
        numbers = context.state.get("numbers")
        if not numbers:
            numbers = [1, 2, 3]
            state_delta["numbers"] = numbers
        total = sum(numbers)
        state_delta["sum"] = total
        return StepResult(status="done", state_delta=state_delta, message="Generated numbers and computed sum")


class WaitForApprovalStep(Step):
    def __init__(self):
        super().__init__("wait_for_approval")

    def execute(self, context: ExecutionContext) -> StepResult:
        state = context.state
        approved = state.get("approved")
        # Also allow signal bus
        if approved is True:
            return StepResult(status="done", state_delta={}, message="Approval already granted")
        signals = state.get("signals") or {}
        if signals.get("approved") is True:
            return StepResult(status="done", state_delta={"approved": True}, message="Approval granted via signal")
        return StepResult(status="waiting", state_delta={}, message="Waiting for approval", wait_for="approved")


class MultiplyResultStep(Step):
    def __init__(self):
        super().__init__("multiply_result")

    def execute(self, context: ExecutionContext) -> StepResult:
        total = context.state.get("sum")
        if total is None:
            raise ValueError("sum not found in state")
        multiplier = context.state.get("input", {}).get("multiplier", 2)
        result = total * multiplier
        return StepResult(status="done", state_delta={"result": result}, message="Multiplied sum by multiplier")


class FinalizeStep(Step):
    def __init__(self):
        super().__init__("finalize")

    def execute(self, context: ExecutionContext) -> StepResult:
        return StepResult(status="done", state_delta={"finalized": True}, message="Flow finalized")


class SampleFlow(Flow):
    def __init__(self):
        super().__init__("sample")
        self.steps = [
            GenerateNumbersStep(),
            WaitForApprovalStep(),
            MultiplyResultStep(),
            FinalizeStep(),
        ]

    def initial_state(self, input_state: Dict[str, Any]) -> Dict[str, Any]:
        state = super().initial_state(input_state)
        # Ensure approved defaults to False
        state["approved"] = state.get("approved", False)
        return state

