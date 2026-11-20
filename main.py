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

from typing import Literal

from anthropic import APIError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from drill_core import generate_sentences, get_feedback

# The FastAPI application object. Uvicorn (the server) looks for this variable.
app = FastAPI(title="Grammar Drill API")

# ---------------------------------------------------------------------------
# CORS: allow the browser-based frontend to call this API.
#
# The Vite dev server runs on a DIFFERENT origin (http://localhost:5173) than
# this backend (http://localhost:8000). By default browsers block cross-origin
# requests, so we explicitly list the frontend's origin as allowed. Middleware
# runs on every request and attaches the Access-Control-Allow-* headers the
# browser looks for. Both localhost and 127.0.0.1 are listed because they count
# as separate origins depending on how you open the page.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://grammar-drill-app.vercel.app",
    ],
    allow_methods=["*"],   # allow GET, POST, OPTIONS preflight, etc.
    allow_headers=["*"],   # allow Content-Type: application/json, etc.
)


# ---------------------------------------------------------------------------
# Pydantic models: the typed contracts for each endpoint's input and output.
#
# A `BaseModel` subclass describes the fields, their types, and whether they're
# required. FastAPI uses these to validate incoming JSON, to serialize outgoing
# JSON, and to build the /docs page automatically.
# ---------------------------------------------------------------------------

# The two scripts a caller may request. `Literal[...]` restricts the field to
# exactly these two strings — any other value is rejected by FastAPI with a 422
# before our code runs. Defined once and reused by both request models so the
# two endpoints stay in lockstep.
Script = Literal["simplified", "traditional"]


class GenerateRequest(BaseModel):
    """Body for POST /generate."""

    # `...` (Ellipsis) marks a field as REQUIRED. Field(...) also lets us attach
    # validation rules and documentation shown in /docs.
    concept: str = Field(..., description="The grammar concept to drill, e.g. '把-construction'.")
    # ge=1 / le=20 is a HARD server-side bound. The frontend also limits this,
    # but that limit is bypassable (curl, /docs, a modified client), so the cap
    # is enforced here too: any request for more than 20 sentences is rejected
    # by FastAPI with a 422 before generation runs, keeping API cost bounded.
    count: int = Field(..., ge=1, le=20, description="How many sentences to generate (1-20).")
    # Optional field: `int | None` with a default of None. If the caller omits
    # it (or sends null), hsk_level is None and generation uses natural/default
    # vocabulary — exactly like pressing enter in the CLI.
    hsk_level: int | None = Field(
        default=None,
        ge=1,
        le=6,
        description="Optional HSK vocab level 1-6. Omit for natural/default vocabulary.",
    )
    # Which Chinese script the model should produce. Defaults to "simplified",
    # so requests that omit this field behave exactly as before. Note: /generate
    # returns ENGLISH sentences, so this field has no visible effect here — it
    # exists for symmetry with /feedback (where the corrected Chinese is what the
    # script actually governs) and for a future UI toggle.
    script: Script = Field(
        default="simplified",
        description="Chinese script the model should produce: 'simplified' or 'traditional'.",
    )


class GenerateResponse(BaseModel):
    """Body returned by POST /generate."""

    sentences: list[str]


class FeedbackRequest(BaseModel):
    """Body for POST /feedback."""

    concept: str = Field(..., description="The same grammar concept that was drilled.")
    sentences: list[str] = Field(..., description="The English sentences that were generated.")
    translations: list[str] = Field(..., description="The user's Chinese translations, in the same order.")
    # Which script the grader writes its corrected Chinese in (corrected_translation
    # and any inline-quoted characters). Defaults to "simplified" so existing
    # requests are unaffected. This governs only the model's OUTPUT script; the
    # user's own input may be in either script and is never penalized for it.
    script: Script = Field(
        default="simplified",
        description="Chinese script the grader should produce: 'simplified' or 'traditional'.",
    )


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
        sentences = generate_sentences(
            request.concept, request.count, request.hsk_level, request.script
        )
    except APIError as e:
        # Turn an Anthropic API failure into a proper HTTP error instead of a
        # raw 500 crash. We surface a generic message — never the API key.
        raise HTTPException(status_code=502, detail=f"API error while generating sentences: {e}")
    return GenerateResponse(sentences=sentences)


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Grade the user's translations with the two-score PASS/FAIL feedback."""
    try:
        result = get_feedback(
            request.concept, request.sentences, request.translations, request.script
        )
    except APIError as e:
        raise HTTPException(status_code=502, detail=f"API error while getting feedback: {e}")
    # get_feedback returns a list of plain dicts; FastAPI validates each one
    # against FeedbackItem when it builds the FeedbackResponse.
    return FeedbackResponse(feedback=result)
