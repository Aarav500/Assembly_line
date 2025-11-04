from datetime import datetime
from typing import Dict
from evaluator import evaluate_output
from tuner import refine_prompt


def step_run(run: Dict, model) -> Dict:
    # If first step, move status to running
    if run['status'] in ['pending']:
        run['status'] = 'running'

    iteration_num = len(run.get('iterations', [])) + 1
    prompt = run['current_prompt']

    # Generate output
    output = model.generate(prompt)

    # Evaluate
    eval_result = evaluate_output(output, run.get('criteria', []))

    # Record iteration
    iter_record = {
        'iteration': iteration_num,
        'prompt': prompt,
        'output': output,
        'score': eval_result['score'],
        'missing_criteria': eval_result['missing'],
        'matched_criteria': eval_result['matched'],
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    run.setdefault('iterations', []).append(iter_record)

    # Check completion
    target = float(run.get('target_score', 0.9))
    if eval_result['score'] >= target:
        run['status'] = 'completed'
        return run

    # Check max iterations
    if iteration_num >= int(run.get('max_iterations', 5)):
        run['status'] = 'failed'
        return run

    # Refine prompt for next iteration
    refined = refine_prompt(prompt, eval_result['missing'], output)
    run['current_prompt'] = refined

    return run


def auto_run(run: Dict, model) -> Dict:
    # Loop until done or max iterations
    while run['status'] not in ['completed', 'failed', 'stopped']:
        run = step_run(run, model)
        if run['status'] in ['completed', 'failed', 'stopped']:
            break
    return run

