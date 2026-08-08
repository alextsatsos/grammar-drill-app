"""Core drill logic shared by the CLI (drill.py) and the web backend (main.py).

This module contains ONLY the reusable pieces: the Anthropic client, the model
name, the JSON schemas, and the two functions that do real work —
generate_sentences() and get_feedback(). It deliberately has NO input()/print()
calls, so it can be imported and called from anywhere (a terminal, a web server,
a test) without assuming there's a human at a keyboard.
"""

import json
import os
import sys

from dotenv import load_dotenv
from anthropic import Anthropic

# Read .env into environment variables. Both the CLI and the web server import
# this module, so loading the key here means it happens exactly once, in one
# place, no matter who calls us. The key stays server-side; it is never returned
# to a caller.
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
                            "order, missing/extra words, wrong tones, missing "
                            "or incorrect measure words, etc.). Measure-word "
                            "mistakes are real grammar errors and must be "
                            "flagged here (unless the target concept IS measure "
                            "words, in which case they belong to concept_pass "
                            "instead) — never wave them through. If there are "
                            "no other errors, say so briefly (e.g. 'No other "
                            "errors.')."
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


def generate_sentences(concept: str, count: int, hsk_level: int | None) -> list[str]:
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

    if hsk_level is not None:
        prompt += (
            f"\n\nVOCABULARY LEVEL: Keep the vocabulary needed to translate "
            f"each sentence into Chinese at or below HSK level {hsk_level}. "
            f"Only use words whose natural Chinese translation is HSK "
            f"{hsk_level} or lower. If a word would push above HSK "
            f"{hsk_level}, choose a simpler everyday alternative that stays "
            f"within the limit. This constraint is about vocabulary "
            f"difficulty only — the target concept '{concept}' must still be "
            f"clearly required in every sentence, even if the grammar of the "
            f"concept itself is above HSK {hsk_level}."
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
        f"MEASURE WORDS (量词): Grade them. A missing measure word (e.g. "
        f"writing 一书 instead of 一本书) or a wrong measure word for the noun "
        f"is a real grammar error — never treat it as acceptable or ignore it. "
        f"Route it by the same boundary rule as everything else: if the target "
        f"concept '{concept}' IS measure words, then a measure-word error makes "
        f"concept_pass = false; otherwise flag it in other_errors like any "
        f"other unrelated grammar mistake. Do not wave measure-word errors "
        f"through in either section.\n\n"
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
