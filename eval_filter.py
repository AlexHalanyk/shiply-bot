"""Offline evaluation harness for the relevance filter.

Manual tool, NOT part of the bot's runtime loop and NOT run in CI (it makes
real Gemini/Ollama API calls). Run by hand:

    python eval_filter.py                  # all three configs
    python eval_filter.py --backend gemini  # just one

Reads golden_set.csv (columns: title,expected — expected is 1/0 or YES/NO),
runs each title through gemini-only, ollama-only, and cascade configurations
using the bot's own is_relevant_ai / is_relevant_ai_ollama, and prints
accuracy/precision/recall plus false positive/negative titles per config.
"""
import argparse
import csv
import time

from bot import is_relevant_ai, is_relevant_ai_ollama

GOLDEN_SET_PATH = "golden_set.csv"
BACKENDS = ["gemini", "ollama", "cascade"]

# is_relevant_ai() already sleeps 13s after every call to stay under Gemini's
# free-tier rate limit; this is just a small extra buffer around it.
GEMINI_CALL_DELAY = 1


def load_golden_set(path):
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append({
                "title": row["title"],
                "expected": row["expected"].strip().upper() in ("1", "YES", "TRUE"),
            })
    return rows


def _job_from_title(title):
    # Only the title feeds the keyword/AI relevance decision; company and
    # location are unused by the prompt but expected to be present.
    return {"title": title, "company": "", "location": ""}


def classify_gemini(title):
    decision = is_relevant_ai(_job_from_title(title))
    time.sleep(GEMINI_CALL_DELAY)
    return decision


def classify_ollama(title):
    return is_relevant_ai_ollama(_job_from_title(title))


def classify_cascade(title):
    gemma_decision = is_relevant_ai_ollama(_job_from_title(title))
    if not gemma_decision:
        return gemma_decision  # False or None short-circuits before the Gemini call
    decision = is_relevant_ai(_job_from_title(title))
    time.sleep(GEMINI_CALL_DELAY)
    return decision


CLASSIFIERS = {
    "gemini": classify_gemini,
    "ollama": classify_ollama,
    "cascade": classify_cascade,
}


def evaluate(backend, rows):
    true_positives = 0
    true_negatives = 0
    false_positives = []
    false_negatives = []
    no_decision = []

    classify = CLASSIFIERS[backend]

    for row in rows:
        title, expected = row["title"], row["expected"]
        decision = classify(title)

        if decision is None:
            no_decision.append(title)
        elif decision and expected:
            true_positives += 1
        elif not decision and not expected:
            true_negatives += 1
        elif decision and not expected:
            false_positives.append(title)
        else:
            false_negatives.append(title)

    classified = true_positives + true_negatives + len(false_positives) + len(false_negatives)
    accuracy = (true_positives + true_negatives) / classified if classified else 0.0
    predicted_positive = true_positives + len(false_positives)
    actual_positive = true_positives + len(false_negatives)
    precision = true_positives / predicted_positive if predicted_positive else 0.0
    recall = true_positives / actual_positive if actual_positive else 0.0

    return {
        "backend": backend,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "no_decision": no_decision,
    }


def print_report(results):
    header = f"{'Backend':<10} {'Accuracy':>10} {'Precision':>10} {'Recall':>10}"
    print(header)
    print("-" * len(header))
    for result in results:
        print(
            f"{result['backend']:<10} "
            f"{result['accuracy'] * 100:>9.1f}% "
            f"{result['precision'] * 100:>9.1f}% "
            f"{result['recall'] * 100:>9.1f}%"
        )

    for result in results:
        print(f"\n--- {result['backend']} ---")
        print(f"False positives ({len(result['false_positives'])}): {result['false_positives']}")
        print(f"False negatives ({len(result['false_negatives'])}): {result['false_negatives']}")
        if result["no_decision"]:
            print(f"No decision/errors ({len(result['no_decision'])}): {result['no_decision']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=BACKENDS, help="Run only this configuration instead of all three")
    parser.add_argument("--golden-set", default=GOLDEN_SET_PATH, help="Path to the golden set CSV")
    args = parser.parse_args()

    rows = load_golden_set(args.golden_set)
    backends = [args.backend] if args.backend else BACKENDS

    results = [evaluate(backend, rows) for backend in backends]
    print_report(results)


if __name__ == "__main__":
    main()
