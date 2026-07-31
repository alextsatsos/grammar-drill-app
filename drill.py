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
                    "correct": {"type": "boolean"},
                    "explanation": {
                        "type": "string",
                        "description": (
                            "If correct, a short confirmation. If incorrect, "
                            "a clear explanation of the grammar mistake."
                        ),
                    },
                    "corrected_translation": {
                        "type": "string",
                        "description": (
                            "The corrected Chinese translation if incorrect. "
                            "Empty string if the original was correct."
                        ),
                    },
                },
                "required": ["correct", "explanation", "corrected_translation"],
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


def generate_sentences(concept: str) -> list[str]:
    prompt = (
        f"Generate exactly 10 English sentences that would require the Chinese "
        f"grammar concept '{concept}' to translate naturally into Mandarin. "
        f"The sentences should be varied in subject matter and everyday-usable, "
        f"ranging from simple to moderately challenging."
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
        f"The user is drilling the Chinese grammar concept '{concept}'. "
        f"Below are 10 English sentences and the user's attempted Chinese "
        f"translations. For each one, judge whether the translation is "
        f"grammatically correct and natural, with particular attention to "
        f"whether it correctly applies '{concept}'. Return feedback for all "
        f"10 in the same order they were given.\n\n{pairs}"
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
        if fb["correct"]:
            print(f"   ✓ Correct — {fb['explanation']}")
        else:
            print(f"   ✗ {fb['explanation']}")
            print(f"   Corrected: {fb['corrected_translation']}")


def main() -> None:
    concept = get_concept()

    print(f"\nGenerating 10 sentences for '{concept}'...")
    try:
        sentences = generate_sentences(concept)
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
