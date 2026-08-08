"""Command-line interface for the grammar drill.

This file is now ONLY about talking to a human in the terminal: asking the
questions, printing the sentences, collecting typed translations, and printing
feedback. The actual work — calling the model to generate sentences and grade
translations — lives in drill_core.py, which the web backend also imports. That
way the CLI and the backend share one identical copy of the grading logic.
"""

import sys

from anthropic import APIError

from drill_core import generate_sentences, get_feedback


def get_concept() -> str:
    concept = input("Grammar concept to drill (e.g. '把-construction'): ").strip()
    if not concept:
        sys.exit("No concept entered.")
    return concept


def get_count() -> int:
    raw = input("How many sentences? (press enter for 10): ").strip()
    if not raw:
        return 10
    try:
        count = int(raw)
    except ValueError:
        sys.exit(f"'{raw}' is not a number.")
    if count < 1:
        sys.exit("Number of sentences must be at least 1.")
    return count


def get_hsk_level() -> int | None:
    raw = input(
        "HSK vocab level? (1-6, press enter for natural/default): "
    ).strip()
    if not raw:
        return None
    try:
        level = int(raw)
    except ValueError:
        sys.exit(f"'{raw}' is not a number.")
    if level < 1 or level > 6:
        sys.exit("HSK level must be between 1 and 6.")
    return level


def print_sentences(sentences: list[str]) -> None:
    print("\nTranslate these into Chinese:\n")
    for i, sentence in enumerate(sentences, start=1):
        print(f"{i}. {sentence}")
    print()


def collect_translations(sentences: list[str]) -> list[str]:
    translations = []
    for i, sentence in enumerate(sentences, start=1):
        print(f"\n{i}. {sentence}")
        translation = input("   Your translation: ").strip()
        translations.append(translation)
    return translations


def print_feedback(
    sentences: list[str], translations: list[str], feedback: list[dict]
) -> None:
    print("\n" + "=" * 60)
    print("FEEDBACK")
    print("=" * 60)

    for i, (sentence, translation, fb) in enumerate(
        zip(sentences, translations, feedback), start=1
    ):
        print(f"\n{i}. {sentence}")
        print(f"   You wrote: {translation}")

        # Piece 1: concept PASS/FAIL — the thing being drilled.
        if fb["concept_pass"]:
            print(f"   CONCEPT: ✓ PASS — {fb['concept_note']}")
        else:
            print(f"   CONCEPT: ✗ FAIL — {fb['concept_note']}")

        # Piece 2: other, unrelated errors, kept visually separate.
        print(f"   OTHER:   {fb['other_errors']}")
        if fb["corrected_translation"]:
            print(f"   Corrected: {fb['corrected_translation']}")


def main() -> None:
    concept = get_concept()
    count = get_count()
    hsk_level = get_hsk_level()

    print(f"\nGenerating {count} sentences for '{concept}'...")
    try:
        sentences = generate_sentences(concept, count, hsk_level)
    except APIError as e:
        sys.exit(f"API error while generating sentences: {e}")

    print_sentences(sentences)
    translations = collect_translations(sentences)

    print("\nGetting feedback...")
    try:
        feedback = get_feedback(concept, sentences, translations)
    except APIError as e:
        sys.exit(f"API error while getting feedback: {e}")

    print_feedback(sentences, translations, feedback)


if __name__ == "__main__":
    main()
