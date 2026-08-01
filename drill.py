import json
import os
import sys

from dotenv import load_dotenv
from anthropic import Anthropic, APIError

load_dotenv()

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    sys.exit("ANTHROPIC_API_KEY not found. Check your .env file.")

client = Anthropic(api_key=api_key)

MODEL = "claude-opus-5"

SENTENCES_SCHEMA = {
    "type": "object",
    "properties": {
        "sentences": {
            "type": "array",
            "items": {"type": "string"},
        }
    },
    "required": ["sentences"],
    "additionalProperties": False,
}

FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "feedback": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "concept_pass": {
                        "type": "boolean",
                        "description": (
                            "PASS/FAIL on the TARGET grammar concept only. "
                            "True only if the target structure was used "
                            "correctly. If any error involves the target "
                            "structure at all, this is False (FAIL) — even if "
                            "that error is also a general grammar mistake. "
                            "Errors with nothing to do with the target "
                            "structure must NOT affect this value."
                        ),
                    },
                    "concept_note": {
                        "type": "string",
                        "description": (
                            "One short sentence explaining the concept "
                            "PASS/FAIL: what the user did right or wrong with "
                            "the target structure specifically."
                        ),
                    },
                    "other_errors": {
                        "type": "string",
                        "description": (
                            "A brief description of any mistakes NOT related "
                            "to the target concept (wrong characters, word "
                            "order, missing/extra words, tone/measure-word "
                            "slips, etc.). If there are no other errors, say "
                            "so briefly (e.g. 'No other errors.')."
                        ),
                    },
                    "corrected_translation": {
                        "type": "string",
                        "description": (
                            "The fully corrected Chinese translation. Empty "
                            "string only if the translation was completely "
                            "correct with nothing to fix."
                        ),
                    },
                },
                "required": [
                    "concept_pass",
                    "concept_note",
                    "other_errors",
                    "corrected_translation",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["feedback"],
    "additionalProperties": False,
}


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


def generate_sentences(concept: str, count: int) -> list[str]:
    prompt = (
        f"Generate exactly {count} English sentences that would require the "
        f"Chinese grammar concept '{concept}' to translate naturally into "
        f"Mandarin.\n\n"
        f"Keep each sentence simple and focused on isolating '{concept}'. "
        f"Each sentence must clearly require the target concept, but keep "
        f"everything else about it as simple as possible: avoid pulling in "
        f"other complex structures (e.g. comparison structures like 比…得多, "
        f"complex time clauses, multi-clause sentences) and avoid advanced or "
        f"obscure vocabulary. The goal is that if the learner makes a mistake, "
        f"it is because of the target concept, not unrelated complexity. Keep "
        f"the sentences natural and everyday-usable — just not overloaded. "
        f"Vary the subject matter."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        thinking={"type": "disabled"},
        output_config={"format": {"type": "json_schema", "schema": SENTENCES_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )

    text = next(block.text for block in response.content if block.type == "text")
    data = json.loads(text)
    return data["sentences"]


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


def get_feedback(
    concept: str, sentences: list[str], translations: list[str]
) -> list[dict]:
    pairs = "\n".join(
        f"{i}. English: {en}\n   Chinese (user's translation): {zh}"
        for i, (en, zh) in enumerate(zip(sentences, translations), start=1)
    )

    prompt = (
        f"The user is drilling the Chinese grammar concept '{concept}' (the "
        f"'target concept'). Below are {len(sentences)} English sentences and "
        f"the user's attempted Chinese translations. For EACH translation, "
        f"give two SEPARATE assessments.\n\n"
        f"LANGUAGE: Write ALL explanations (both concept_note and "
        f"other_errors) in English. Do NOT write the explanations in Chinese. "
        f"When you need to refer to a specific character, word, or phrase from "
        f"the user's translation, quote the actual Chinese inline followed by "
        f"a brief English gloss in parentheses — e.g. \"you wrote 房租 (rent) "
        f"but this should be 房子 (house).\" So: English sentences, with "
        f"Chinese quoted only for the specific characters/phrases being "
        f"discussed.\n\n"
        f"1. concept_pass (PASS/FAIL on the target concept ONLY): Set to true "
        f"only if the user correctly used the target concept '{concept}'. "
        f"Apply this boundary rule strictly — if an error involves the target "
        f"structure at all, it is a FAIL (concept_pass = false), even when "
        f"that same error is also a general grammar mistake. If an error has "
        f"nothing to do with the target structure, it must NOT affect "
        f"concept_pass. Also give a one-sentence concept_note explaining the "
        f"PASS/FAIL for the target structure specifically.\n\n"
        f"2. other_errors (everything else): Briefly describe any OTHER "
        f"mistakes not related to the target concept — wrong characters, word "
        f"order, missing or extra words, wrong measure words, etc. If there "
        f"are none, say so briefly. Provide corrected_translation with the "
        f"fully corrected Chinese sentence (empty string only if nothing at "
        f"all needs fixing).\n\n"
        f"Do NOT treat the following as errors, in either section:\n"
        f"- Punctuation: ignore missing or nonstandard punctuation entirely "
        f"(periods, commas, 。，、! ? etc.). Never mention punctuation in "
        f"other_errors and never 'correct' punctuation.\n"
        f"- Regional vocabulary: treat all standard regional variants "
        f"(Mainland, Taiwan, Hong Kong usage) as equally acceptable. Do not "
        f"push the user toward any one region's usage. For example, 功课 and "
        f"作业 are both valid and neither should be corrected to the other. "
        f"Only flag a word choice if it is actually wrong, not merely "
        f"regionally different.\n\n"
        f"Keep the concept judgment and the other-errors judgment strictly "
        f"independent. Return feedback for all {len(sentences)} in the same "
        f"order they were given.\n\n{pairs}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "disabled"},
        output_config={"format": {"type": "json_schema", "schema": FEEDBACK_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )

    text = next(block.text for block in response.content if block.type == "text")
    data = json.loads(text)
    return data["feedback"]


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

    print(f"\nGenerating {count} sentences for '{concept}'...")
    try:
        sentences = generate_sentences(concept, count)
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
