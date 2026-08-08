"""FastAPI backend for the grammar drill.

Exposes the two core pieces of drill logic over HTTP so a future frontend (or
/docs, or curl) can call them:

    POST /generate  -> generate English sentences for a grammar concept
    POST /feedback  -> grade the user's Chinese translations (two-score feedback)

All the real work is delegated to drill_core.py, the same module the CLI uses,
so the grading behavior here is identical to `python drill.py`. The Anthropic
API key lives only inside drill_core (loaded from .env) and is never part of any
request or response.
"""

from anthropic import APIError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from drill_core import generate_sentences, get_feedback

# The FastAPI application object. Uvicorn (the server) looks for this variable.
app = FastAPI(title="Grammar Drill API")


# ---------------------------------------------------------------------------
# Pydantic models: the typed contracts for each endpoint's input and output.
#
# A `BaseModel` subclass describes the fields, their types, and whether they're
# required. FastAPI uses these to validate incoming JSON, to serialize outgoing
# JSON, and to build the /docs page automatically.
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    """Body for POST /generate."""

    # `...` (Ellipsis) marks a field as REQUIRED. Field(...) also lets us attach
    # validation rules and documentation shown in /docs.
    concept: str = Field(..., description="The grammar concept to drill, e.g. '把-construction'.")
    count: int = Field(..., ge=1, description="How many sentences to generate (at least 1).")
    # Optional field: `int | None` with a default of None. If the caller omits
    # it (or sends null), hsk_level is None and generation uses natural/default
    # vocabulary — exactly like pressing enter in the CLI.
    hsk_level: int | None = Field(
        default=None,
        ge=1,
        le=6,
        description="Optional HSK vocab level 1-6. Omit for natural/default vocabulary.",
    )


class GenerateResponse(BaseModel):
    """Body returned by POST /generate."""

    sentences: list[str]


class FeedbackRequest(BaseModel):
    """Body for POST /feedback."""

    concept: str = Field(..., description="The same grammar concept that was drilled.")
    sentences: list[str] = Field(..., description="The English sentences that were generated.")
    translations: list[str] = Field(..., description="The user's Chinese translations, in the same order.")


class FeedbackItem(BaseModel):
    """One sentence's two-score feedback. Mirrors the model's JSON output."""

    concept_pass: bool
    concept_note: str
    other_errors: str
    corrected_translation: str


class FeedbackResponse(BaseModel):
    """Body returned by POST /feedback."""

    feedback: list[FeedbackItem]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    """Generate English sentences that require the given grammar concept."""
    # By the time this runs, FastAPI has already validated `request` against
    # GenerateRequest. We just hand the clean values to the shared core function.
    try:
        sentences = generate_sentences(request.concept, request.count, request.hsk_level)
    except APIError as e:
        # Turn an Anthropic API failure into a proper HTTP error instead of a
        # raw 500 crash. We surface a generic message — never the API key.
        raise HTTPException(status_code=502, detail=f"API error while generating sentences: {e}")
    return GenerateResponse(sentences=sentences)


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Grade the user's translations with the two-score PASS/FAIL feedback."""
    try:
        result = get_feedback(request.concept, request.sentences, request.translations)
    except APIError as e:
        raise HTTPException(status_code=502, detail=f"API error while getting feedback: {e}")
    # get_feedback returns a list of plain dicts; FastAPI validates each one
    # against FeedbackItem when it builds the FeedbackResponse.
    return FeedbackResponse(feedback=result)
