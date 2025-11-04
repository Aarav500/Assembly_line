from typing import List


def refine_prompt(previous_prompt: str, missing_criteria: List[str], last_output: str) -> str:
    if not missing_criteria:
        return previous_prompt

    feedback_block = []
    feedback_block.append("\nSystem feedback:")
    feedback_block.append("Your previous answer did not meet all criteria. Please revise accordingly.")
    feedback_block.append("Missing criteria were:")
    for c in missing_criteria:
        feedback_block.append(f"- {c}")
    feedback_block.append("")
    feedback_block.append("Ensure your answer satisfies all of the following criteria:")
    for c in missing_criteria:
        feedback_block.append(f"- {c}")
    feedback_block.append("")
    feedback_block.append("Do not include apologies. Provide the final, improved answer.")

    return previous_prompt.rstrip() + "\n\n" + "\n".join(feedback_block)

