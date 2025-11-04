from __future__ import annotations
from typing import Any, Dict, List, Optional
from .models import Plan, Step, ChecklistItem, gen_id, ChecklistUpdateRequest
from .storage import PlanStore
from .utils import estimate_complexity, infer_resources, default_step_names
from datetime import datetime


class PlanningAgent:
    def __init__(self, store: PlanStore) -> None:
        self.store = store

    def generate_plan(self, goal: str, context: str = "", constraints: List[str] | None = None, preferences: Dict[str, Any] | None = None) -> Plan:
        constraints = constraints or []
        preferences = preferences or {}
        plan_id = gen_id("plan")
        base_resources = infer_resources(goal)
        complexity = estimate_complexity(goal)

        steps: List[Step] = []
        names = default_step_names(goal)

        for idx, name in enumerate(names):
            step_id = gen_id(f"s{idx+1}")
            description = self._desc_for(name)
            checklist = self._checklist_for(name)
            acceptance = self._acceptance_for(name)
            estimate = round(self._estimate_for(name, complexity), 2)
            dependencies = [] if idx == 0 else [steps[idx-1].step_id]
            step_resources = self._resources_for(name, base_resources)
            step = Step(
                step_id=step_id,
                name=name,
                description=description,
                dependencies=dependencies,
                inputs=self._inputs_for(name, goal, context),
                outputs=self._outputs_for(name, goal),
                required_resources=step_resources,
                checklist=checklist,
                acceptance_criteria=acceptance,
                estimate_hours=estimate,
                status="pending" if idx > 0 else "ready",
            )
            steps.append(step)

        manifest = self._build_manifest(goal, context, constraints, base_resources, steps, complexity)

        plan = Plan(
            plan_id=plan_id,
            goal=goal,
            context=context,
            constraints=constraints,
            preferences=preferences,
            created_at=datetime.utcnow().isoformat() + 'Z',
            status="draft",
            steps=steps,
            manifest=manifest,
        )

        plan.add_log("info", "Plan generated with stepwise manifests and checklists")
        self.store.save(plan)
        return plan

    def _desc_for(self, name: str) -> str:
        mapping = {
            "Define Objectives & Success Criteria": "Clarify scope, objectives, and measurable outcomes for the task.",
            "Gather Information & Resources": "Collect relevant information, prior work, and resources required.",
            "Plan Approach & Milestones": "Design the approach, break down tasks, sequence with dependencies, and estimate.",
            "Execute Core Work": "Perform the primary work according to the plan and coding/creation standards.",
            "Review, Test, and Iterate": "Validate results against criteria; test, review, and iterate to quality.",
            "Finalize & Deliver": "Polish deliverables, document, package, and hand off to stakeholders.",
            "Deployment & Monitoring": "Release to target environment and establish monitoring/rollback.",
            "Post-Delivery Follow-up": "Gather feedback, capture lessons learned, and schedule maintenance.",
        }
        return mapping.get(name, name)

    def _checklist_for(self, name: str) -> List[ChecklistItem]:
        items: List[str] = []
        if name == "Define Objectives & Success Criteria":
            items = [
                "Document SMART objectives",
                "Identify stakeholders and decision-makers",
                "Define measurable success criteria",
                "Confirm scope boundaries and constraints",
            ]
        elif name == "Gather Information & Resources":
            items = [
                "Collect existing assets and references",
                "Validate assumptions with stakeholders",
                "List and secure required tools and access",
            ]
        elif name == "Plan Approach & Milestones":
            items = [
                "Break work into milestones and tasks",
                "Map dependencies and critical path",
                "Assess risks with mitigations",
                "Estimate effort per task",
            ]
        elif name == "Execute Core Work":
            items = [
                "Set up environment and tools",
                "Implement tasks as per plan",
                "Record work log and decisions",
            ]
        elif name == "Review, Test, and Iterate":
            items = [
                "Self-review vs acceptance criteria",
                "Peer review or testing completed",
                "Address defects and re-test",
            ]
        elif name == "Finalize & Deliver":
            items = [
                "Prepare final deliverables",
                "Complete documentation and handover",
                "Obtain stakeholder sign-off",
            ]
        elif name == "Deployment & Monitoring":
            items = [
                "Prepare deployment plan with rollback",
                "Execute deployment to target",
                "Set up monitoring and alerts",
            ]
        elif name == "Post-Delivery Follow-up":
            items = [
                "Collect feedback from stakeholders",
                "Retrospective and lessons learned",
                "Plan follow-ups and maintenance",
            ]
        return [ChecklistItem(item_id=gen_id("c"), text=txt, done=False, mandatory=True) for txt in items]

    def _acceptance_for(self, name: str) -> List[str]:
        mapping = {
            "Define Objectives & Success Criteria": ["Objectives documented and approved", "Success metrics defined"],
            "Gather Information & Resources": ["All required accesses/tools available", "Assumptions validated"],
            "Plan Approach & Milestones": ["Plan documented with estimates", "Risks documented with mitigations"],
            "Execute Core Work": ["Work implements planned scope", "No critical defects known"],
            "Review, Test, and Iterate": ["All tests/reviews passed", "Known issues triaged"],
            "Finalize & Deliver": ["Deliverables packaged and documented", "Stakeholder sign-off received"],
            "Deployment & Monitoring": ["Deployment completed", "Monitoring and rollback verified"],
            "Post-Delivery Follow-up": ["Feedback captured", "Retrospective completed"],
        }
        return mapping.get(name, [])

    def _estimate_for(self, name: str, complexity: float) -> float:
        base = {
            "Define Objectives & Success Criteria": 1.0,
            "Gather Information & Resources": 2.0,
            "Plan Approach & Milestones": 2.0,
            "Execute Core Work": 6.0,
            "Review, Test, and Iterate": 3.0,
            "Finalize & Deliver": 1.5,
            "Deployment & Monitoring": 2.0,
            "Post-Delivery Follow-up": 1.0,
        }
        return base.get(name, 1.0) * complexity

    def _resources_for(self, name: str, base: Dict[str, List[str]]) -> Dict[str, List[str]]:
        # Adjust resources slightly per step
        tools = list(base.get("tools", []))
        skills = list(base.get("skills", []))
        materials = list(base.get("materials", []))
        if name.startswith("Define"):
            tools += ["Stakeholder brief", "RACI template"]
            skills += ["Facilitation"]
        if name.startswith("Gather"):
            tools += ["Knowledge base", "Access management"]
            skills += ["Research"]
        if name.startswith("Plan"):
            tools += ["Gantt/Board", "Risk matrix"]
            skills += ["Project planning"]
        if name.startswith("Execute"):
            skills += ["Execution", "Problem solving"]
        if name.startswith("Review"):
            tools += ["Checklist", "Testing framework"]
            skills += ["Quality assurance"]
        if name.startswith("Finalize"):
            tools += ["Packaging", "Documentation tools"]
            skills += ["Documentation"]
        if name.startswith("Deployment"):
            tools += ["CI/CD", "Monitoring"]
            skills += ["DevOps"]
        if name.startswith("Post-Delivery"):
            tools += ["Survey", "Retrospective template"]
            skills += ["Feedback gathering"]
        return {"tools": sorted(set(tools)), "skills": sorted(set(skills)), "materials": sorted(set(materials))}

    def _inputs_for(self, name: str, goal: str, context: str) -> List[str]:
        base = ["Goal statement", "Context notes", "Constraints", "Preferences"]
        if name.startswith("Execute"):
            base += ["Approved plan", "Resources and access"]
        if name.startswith("Deployment"):
            base += ["Change request", "Release notes"]
        return base

    def _outputs_for(self, name: str, goal: str) -> List[str]:
        if name.startswith("Define"):
            return ["Objectives doc", "Success metrics"]
        if name.startswith("Gather"):
            return ["Resource inventory", "Assumption log"]
        if name.startswith("Plan"):
            return ["Work breakdown", "Timeline & estimates", "Risk register"]
        if name.startswith("Execute"):
            return ["Work artifacts", "Work log"]
        if name.startswith("Review"):
            return ["Test/Review report", "Issue list"]
        if name.startswith("Finalize"):
            return ["Packaged deliverables", "Documentation"]
        if name.startswith("Deployment"):
            return ["Deployed release", "Monitoring dashboard"]
        if name.startswith("Post-Delivery"):
            return ["Feedback summary", "Retrospective notes"]
        return []

    def _build_manifest(self, goal: str, context: str, constraints: List[str], base_resources: Dict[str, List[str]], steps: List[Step], complexity: float) -> Dict[str, Any]:
        total_hours = round(sum(s.estimate_hours for s in steps), 2)
        risks = [
            "Ambiguous requirements",
            "Missing access or resources",
            "Underestimated complexity",
        ]
        risks += [f"Constraint: {c}" for c in constraints]
        return {
            "summary": {
                "goal": goal,
                "context": context,
            },
            "overall_resources": base_resources,
            "risks": risks,
            "timeline_estimate": {
                "total_hours": total_hours,
                "by_step": [{"step_id": s.step_id, "name": s.name, "estimate_hours": s.estimate_hours} for s in steps],
            },
            "deliverables": [steps[-2].outputs if len(steps) >= 2 else steps[-1].outputs][0],
        }

    def update_checklist_items(self, plan: Plan, update_req: ChecklistUpdateRequest) -> List[Dict[str, Any]]:
        updated: List[Dict[str, Any]] = []
        step_map = {s.step_id: s for s in plan.steps}
        for upd in update_req.updates:
            step = step_map.get(upd.step_id)
            if not step:
                continue
            item_map = {item.item_id: item for item in step.checklist}
            for item_upd in upd.updates:
                iid = item_upd.get('item_id')
                done = item_upd.get('done')
                if iid in item_map and isinstance(done, bool):
                    item_map[iid].done = done
                    updated.append({"step_id": step.step_id, "item_id": iid, "done": done})
            # Update step readiness
            if step.status in ["pending", "blocked", "ready"]:
                if self._dependencies_done(plan, step):
                    step.status = "ready"
                else:
                    step.status = "blocked"
        if updated:
            plan.add_log("info", f"Checklist updated for {len(updated)} items")
        return updated

    def execute(self, plan: Plan, stepwise: bool = False) -> Dict[str, Any]:
        if plan.status in ["draft"]:
            return {"error": "plan must be approved before execution"}

        plan.status = "executing"
        progressed_steps = []

        for step in plan.steps:
            if step.status in ["done"]:
                continue
            if not self._dependencies_done(plan, step):
                step.status = "blocked"
                plan.add_log("warn", "Step blocked: dependencies incomplete", step.step_id)
                return {
                    "plan_id": plan.plan_id,
                    "status": plan.status,
                    "halted": True,
                    "reason": "dependency",
                    "blocked_step": step.step_id,
                }
            # Ensure checklist completeness
            missing = [c for c in step.checklist if c.mandatory and not c.done]
            if missing:
                step.status = "ready"
                plan.status = "halted"
                plan.add_log("warn", f"Step halted: {len(missing)} checklist items incomplete", step.step_id)
                return {
                    "plan_id": plan.plan_id,
                    "status": plan.status,
                    "halted": True,
                    "reason": "checklist",
                    "step_id": step.step_id,
                    "missing_items": [{"item_id": m.item_id, "text": m.text} for m in missing],
                }
            # Simulate execution
            step.status = "in_progress"
            plan.add_log("info", "Executing step", step.step_id)
            # ... actual work would happen here ...
            step.status = "done"
            step.completed_at = datetime.utcnow().isoformat() + 'Z'
            plan.add_log("info", "Step completed", step.step_id)
            progressed_steps.append(step.step_id)
            if stepwise:
                # Stop after completing one step
                break

        if all(s.status == "done" for s in plan.steps):
            plan.status = "completed"
            plan.add_log("info", "Plan execution completed")

        return {
            "plan_id": plan.plan_id,
            "status": plan.status,
            "progressed_steps": progressed_steps,
            "plan": plan.to_dict(),
        }

    def status(self, plan: Plan) -> Dict[str, Any]:
        return {
            "plan_id": plan.plan_id,
            "status": plan.status,
            "steps": [{"step_id": s.step_id, "name": s.name, "status": s.status, "completed_at": s.completed_at} for s in plan.steps],
            "logs": [l.to_dict() for l in plan.logs],
        }

    def _dependencies_done(self, plan: Plan, step: Step) -> bool:
        if not step.dependencies:
            return True
        done_ids = {s.step_id for s in plan.steps if s.status == "done"}
        return all(d in done_ids for d in step.dependencies)

