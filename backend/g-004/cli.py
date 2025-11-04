import argparse
import json
from harness.suites import SuiteRepository
from harness.adapters import build_adapter
from harness.evaluator import Evaluator
import config


def main():
    parser = argparse.ArgumentParser(description="Evaluation harness CLI")
    parser.add_argument("--suite", required=True, help="Suite name (file without .json)")
    parser.add_argument("--model", required=True, help="Model spec as JSON string, e.g. '{""type"":""echo""}'")
    parser.add_argument("--max-items", type=int, default=None, help="Max items to evaluate")
    parser.add_argument("--shuffle", action="store_true", help="Shuffle items before evaluating")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for shuffling")

    args = parser.parse_args()

    suite_repo = SuiteRepository(config.SUITES_DIR)
    suite = suite_repo.get_suite(args.suite)
    if not suite:
        raise SystemExit(f"Suite not found: {args.suite}")

    try:
        model_spec = json.loads(args.model)
    except Exception as e:
        raise SystemExit(f"Invalid model JSON: {e}")

    adapter = build_adapter(model_spec)

    evaluator = Evaluator()
    result = evaluator.evaluate_suite(suite, adapter, max_items=args.max_items, shuffle=args.shuffle, seed=args.seed)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

