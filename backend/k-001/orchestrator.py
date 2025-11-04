import os
from typing import Any, Dict, Optional
from agents.planner import PlannerAgent
from agents.builder import BuilderAgent
from agents.tester import TesterAgent
from agents.repair import RepairAgent

class Orchestrator:
    def __init__(self):
        self.planner = PlannerAgent()
        self.builder = BuilderAgent()
        self.tester = TesterAgent()
        self.repair = RepairAgent()
        os.makedirs("artifacts", exist_ok=True)

    def run(self, goal: Optional[str], user_tests=None, function_name: Optional[str]=None, max_iters: int=3) -> Dict[str, Any]:
        history = []
        # Plan
        plan = self.planner.plan(goal=goal, user_tests=user_tests, function_name=function_name)
        history.append({"agent": self.planner.name, "plan": plan})

        # Build
        artifact = self.builder.build(plan)
        history.append({"agent": self.builder.name, "artifact_file": artifact.get("file_path"), "function_name": artifact.get("function_name")})

        # Test & Repair Loop
        iterations = 0
        last_test_results = None
        success = False
        while iterations < max_iters:
            iterations += 1
            test_results = self.tester.test(artifact, plan.get("tests", []))
            last_test_results = test_results
            history.append({"agent": self.tester.name, "iteration": iterations, "summary": {
                "passed": test_results.get("passed"),
                "passed_count": test_results.get("passed_count"),
                "failed_count": test_results.get("failed_count")
            }})
            if test_results.get("passed"):
                success = True
                break

            # Attempt repair
            repair_outcome = self.repair.repair(artifact=artifact, plan=plan, test_results=test_results)
            history.append({"agent": self.repair.name, "iteration": iterations, "patched": repair_outcome.get("patched"), "notes": repair_outcome.get("notes"), "strategies": repair_outcome.get("strategies")})
            if not repair_outcome.get("patched"):
                break
            # Update artifact code and write to file
            artifact["code"] = repair_outcome["code"]
            # overwrite file
            file_path = artifact.get("file_path")
            if file_path:
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(artifact["code"])
                except Exception:
                    pass

        response = {
            "success": success,
            "iterations": iterations,
            "plan": plan,
            "artifact": {
                "file_path": artifact.get("file_path"),
                "function_name": artifact.get("function_name"),
                "code": artifact.get("code")
            },
            "test_results": last_test_results,
            "history": history
        }
        return response

