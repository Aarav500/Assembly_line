import argparse
import json
import logging
import os
import sys
from suggester.analyzer import FeatureDetector, AcceptanceTestDetector
from suggester.suggest import SuggestionEngine


def run(repo_path: str, output: str | None = None):
    try:
        if not os.path.exists(repo_path):
            raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
        
        if not os.path.isdir(repo_path):
            raise NotADirectoryError(f"Repository path is not a directory: {repo_path}")
        
        feature_detector = FeatureDetector()
        test_detector = AcceptanceTestDetector()
        engine = SuggestionEngine()

        features = feature_detector.detect_features(repo_path)
        tests = test_detector.detect_acceptance_tests(repo_path)
        suggestions = engine.suggest(features, tests)
        summary = engine.summary(suggestions, features, tests)

        result = {
            "summary": summary,
            "features": features,
            "tests": tests,
            "suggestions": suggestions,
        }

        if output:
            try:
                os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
                with open(output, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2)
                logging.info(f"Wrote suggestions to {output}")
            except OSError as e:
                raise OSError(f"Failed to write output file: {e}")
        else:
            logging.info(json.dumps(result, indent=2))
    except FileNotFoundError as e:
        logging.error(f"Error: {e}")
        sys.exit(1)
    except NotADirectoryError as e:
        logging.error(f"Error: {e}")
        sys.exit(1)
    except OSError as e:
        logging.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Suggest missing acceptance tests for detected features")
    parser.add_argument("repo_path", help="Path to repository root")
    parser.add_argument("--output", "-o", help="Path to write JSON output")
    args = parser.parse_args()
    run(args.repo_path, args.output)