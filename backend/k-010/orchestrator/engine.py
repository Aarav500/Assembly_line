from __future__ import annotations
import copy
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from orchestrator.storage import Storage, now_iso


@dataclass
class StepResult:
    status: str  # "done" or "waiting"
    state_delta: Dict[str, Any]
    message: Optional[str] = None
    wait_for: Optional[str] = None


class Step:
    name: str

    def __init__(self, name: str):
        self.name = name

    def execute(self, context: "ExecutionContext") -> StepResult:
        raise NotImplementedError


class Flow:
    name: str
    steps: List[Step]

    def __init__(self, name: str):
        self.name = name
        self.steps = []

    def initial_state(self, input_state: Dict[str, Any]) -> Dict[str, Any]:
        # Default behavior: store user input under 'input'
        return {"input": input_state, "meta": {"started_at": now_iso()}, "signals": {}}


@dataclass
class ExecutionContext:
    flow_id: str
    flow_name: str
    step_index: int
    step_name: str
    state: Dict[str, Any]


class Engine:
    def __init__(self, storage_path: str):
        self.storage = Storage(storage_path)
        self._flows: Dict[str, Flow] = {}

    def register_flow(self, name: str, flow: Flow):
        flow.name = name
        self._flows[name] = flow

    def start_flow(self, flow_name: str, input_state: Dict[str, Any], auto_advance: bool = False) -> Tuple[str, Dict[str, Any]]:
        if flow_name not in self._flows:
            raise ValueError(f"Unknown flow: {flow_name}")
        flow_def = self._flows[flow_name]
        state = flow_def.initial_state(input_state)
        flow_id = self.storage.create_flow(flow_name, state=state, status="running", current_step_index=0)
        # Create an initial checkpoint at step -1 (START)
        self.storage.add_execution_log(flow_id, step_index=-1, step_name="START", status="started", message="Flow started", details={"input": input_state})
        self.storage.add_checkpoint(flow_id, step_index=-1, step_name="START", state=state)
        flow = self.storage.get_flow(flow_id)
        if auto_advance:
            self.advance(flow_id, max_steps=100)
            flow = self.storage.get_flow(flow_id)
        return flow_id, flow

    def get_flow_def(self, flow_name: str) -> Flow:
        if flow_name not in self._flows:
            raise ValueError(f"Unknown flow: {flow_name}")
        return self._flows[flow_name]

    def advance(self, flow_id: str, max_steps: int = 10) -> Dict[str, Any]:
        flow = self.storage.get_flow(flow_id)
        if not flow:
            raise ValueError("Flow not found")
        if flow["status"] in ("completed", "failed", "canceled"):
            return {"executed": 0, "status": flow["status"], "message": f"Flow already {flow['status']}"}

        flow_def = self.get_flow_def(flow["name"])
        executed = 0
        last_result = None

        while executed < max_steps:
            current_index = flow["current_step_index"]
            if current_index >= len(flow_def.steps):
                # Completed
                self.storage.update_flow(flow_id, status="completed")
                self.storage.add_execution_log(flow_id, step_index=current_index, step_name="END", status="completed", message="Flow completed", details={})
                break

            step = flow_def.steps[current_index]
            ctx = ExecutionContext(
                flow_id=flow_id,
                flow_name=flow["name"],
                step_index=current_index,
                step_name=step.name,
                state=copy.deepcopy(flow["state"])  # pass a copy to the step
            )

            try:
                result = step.execute(ctx)
                if not isinstance(result, StepResult):
                    raise ValueError(f"Step {step.name} must return StepResult")
            except Exception as e:
                self.storage.add_execution_log(flow_id, step_index=current_index, step_name=step.name, status="error", message=str(e), details={})
                self.storage.update_flow(flow_id, status="failed")
                return {"executed": executed, "status": "failed", "error": str(e)}

            # Merge delta into state
            new_state = flow["state"] or {}
            new_state.update(result.state_delta or {})
            flow["state"] = new_state

            if result.status == "waiting":
                self.storage.update_flow(flow_id, state=new_state, status="waiting")
                self.storage.add_execution_log(flow_id, step_index=current_index, step_name=step.name, status="waiting", message=result.message or f"Waiting for {result.wait_for}", details={"wait_for": result.wait_for})
                last_result = {"status": "waiting", "step_index": current_index, "wait_for": result.wait_for}
                break
            elif result.status == "done":
                # Checkpoint post step completion
                self.storage.update_flow(flow_id, state=new_state, current_step_index=current_index + 1, status="running")
                self.storage.add_checkpoint(flow_id, step_index=current_index, step_name=step.name, state=new_state)
                self.storage.add_execution_log(flow_id, step_index=current_index, step_name=step.name, status="done", message=result.message or "Step completed", details={})
                executed += 1
                last_result = {"status": "done", "step_index": current_index}
                # Refresh flow for next loop
                flow = self.storage.get_flow(flow_id)
                continue
            else:
                raise ValueError(f"Invalid step result status: {result.status}")

        # If after the loop the step index equals steps length, finalize
        flow = self.storage.get_flow(flow_id)
        if flow["current_step_index"] >= len(self.get_flow_def(flow["name"]).steps) and flow["status"] != "completed":
            self.storage.update_flow(flow_id, status="completed")
            self.storage.add_execution_log(flow_id, step_index=flow["current_step_index"], step_name="END", status="completed", message="Flow completed", details={})
        flow = self.storage.get_flow(flow_id)
        return {"executed": executed, "status": flow["status"], "last_result": last_result}

    def replay(self, flow_id: str, from_checkpoint_id: Optional[str] = None, from_step_index: Optional[int] = None, auto_advance: bool = True) -> Dict[str, Any]:
        flow = self.storage.get_flow(flow_id)
        if not flow:
            raise ValueError("Flow not found")
        if from_checkpoint_id:
            ck = self.storage.get_checkpoint(from_checkpoint_id)
            if not ck or ck["flow_id"] != flow_id:
                raise ValueError("Invalid checkpoint")
            base_state = ck["state"]
            start_index = ck["step_index"] + 1
        else:
            # from_step_index is treated as if we had checkpointed after completing from_step_index - 1
            if from_step_index is None:
                raise ValueError("Provide from_checkpoint_id or from_step_index")
            checkpoints = self.storage.get_checkpoints(flow_id)
            # If we have a checkpoint matching the step, use it; else use the nearest before
            base_state = None
            start_index = max(0, int(from_step_index))
            for c in reversed(checkpoints):
                if c["step_index"] <= (start_index - 1):
                    base_state = c["state"]
                    break
            if base_state is None:
                # Use initial state from flows table (which is effectively START checkpoint)
                base_state = flow["state"]
                start_index = 0

        # Reset the flow to replay point
        self.storage.update_flow(flow_id, state=base_state, current_step_index=start_index, status="running")
        self.storage.add_execution_log(flow_id, step_index=start_index, step_name="REPLAY", status="replay", message="Flow replay requested", details={"from_checkpoint_id": from_checkpoint_id, "from_step_index": from_step_index})

        executed_summary = {"start_index": start_index, "auto_advanced": False, "executed": 0}
        if auto_advance:
            result = self.advance(flow_id, max_steps=1000)
            executed_summary["auto_advanced"] = True
            executed_summary["executed"] = result.get("executed")
            executed_summary["final_status"] = result.get("status")
        return executed_summary

