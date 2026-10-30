"""Optional Gemini integration, grounded in user-verified diagram data.

* The API key is read from the environment and never logged or displayed.
* The app works fully without a key or without the google-genai package.
* The drawing image is only sent if the caller explicitly passes it.
* Answers are NOT verified engineering facts.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from PIL import Image

from modules.process_graph import ALL_STATUSES, ProcessGraph

DEFAULT_MODEL = "gemini-2.5-flash"  # override with GEMINI_MODEL
MAX_IMAGE_SIDE = 2048

DISCLAIMER = (
    "AI output is not a verified engineering fact. Check every statement against "
    "the drawing and apply qualified engineering judgement."
)

SYSTEM_INSTRUCTION = (
    "You assist with reading piping and instrumentation diagrams (P&IDs). "
    "Use ONLY the structured diagram data and the attached image (if any) supplied "
    "in the user message. Rules: "
    "(1) Never invent equipment, tags, connections, instrument readings, set points, "
    "or plant conditions. "
    "(2) Treat connections marked 'proposed' or 'uncertain' as unverified and say so. "
    "(3) If the information needed is missing, say what is missing instead of guessing. "
    "(4) Cite the tags or evidence you relied on. "
    "(5) Do not state that a system is safe or that a safeguard exists unless the "
    "supplied data shows it. "
    "(6) Keep answers concise and flag any assumption explicitly."
)


class AIStatus(str, Enum):
    """Outcome categories for an AI request."""

    OK = "ok"
    NOT_CONFIGURED = "not_configured"
    NO_CONTEXT = "no_context"
    INVALID_INPUT = "invalid_input"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass(frozen=True)
class AIResponse:
    """Result of an AI request."""

    status: AIStatus
    text: str = ""
    message: str = ""


@dataclass(frozen=True)
class AIConfig:
    """Model configuration, kept separate from request logic."""

    api_key: Optional[str] = field(default=None, repr=False)  # never printed
    model: str = DEFAULT_MODEL
    temperature: float = 0.1
    max_output_tokens: int = 1024

    @property
    def is_configured(self) -> bool:
        """True when an API key is available."""
        return bool(self.api_key)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def load_config() -> AIConfig:
    """Read configuration from the environment (and an optional .env file)."""
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return AIConfig(
        api_key=key or None,
        model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        temperature=_env_float("GEMINI_TEMPERATURE", 0.1),
        max_output_tokens=_env_int("GEMINI_MAX_OUTPUT_TOKENS", 1024),
    )


def build_context(graph: ProcessGraph) -> str:
    """Serialise the current model for the AI. Returns '' if the graph is empty."""
    records = graph.equipment()
    if not records:
        return ""
    lines = ["EQUIPMENT (tag | type | verified | description):"]
    for r in records:
        lines.append(
            f"- {r.tag} | {r.equipment_type.value} | "
            f"{'verified' if r.verified else 'unverified'} | {r.description or 'n/a'}"
        )
    lines.append("")
    lines.append("CONNECTIONS (source -> target | status | direction | line label):")
    connections = graph.connections(ALL_STATUSES)
    if not connections:
        lines.append("- none entered")
    for c in connections:
        arrow = "->" if c.direction_known else "--"
        direction = "known" if c.direction_known else "unknown"
        lines.append(
            f"- {c.source_tag} {arrow} {c.target_tag} | {c.status.value} | "
            f"{direction} | {c.line_label or 'n/a'}"
        )
    lines.append("")
    lines.append(
        "Only 'confirmed' connections are verified. 'proposed' and 'uncertain' "
        "connections must not be treated as facts."
    )
    return "\n".join(lines)


def image_to_png_bytes(image: Image.Image, max_side: int = MAX_IMAGE_SIDE) -> bytes:
    """Downscale (if needed) and encode an image as PNG bytes."""
    copy = image.convert("RGB")
    copy.thumbnail((max_side, max_side))
    buffer = io.BytesIO()
    copy.save(buffer, format="PNG")
    return buffer.getvalue()


def _api_error_response(exc: Exception) -> AIResponse:
    """Map an SDK error to a safe message (no request content, no key)."""
    code = getattr(exc, "code", None)
    if code == 429:
        return AIResponse(
            AIStatus.RATE_LIMITED,
            message="Rate limit or quota reached. Wait a while and try again.",
        )
    if code in (401, 403):
        return AIResponse(
            AIStatus.ERROR,
            message="The API key was rejected or lacks permission for this model.",
        )
    if code == 404:
        return AIResponse(
            AIStatus.ERROR,
            message="The configured model was not found. Check GEMINI_MODEL.",
        )
    if isinstance(code, int) and code >= 500:
        return AIResponse(
            AIStatus.UNAVAILABLE,
            message="The Gemini service is temporarily unavailable. Try again later.",
        )
    return AIResponse(AIStatus.ERROR, message=f"The API request failed (code {code}).")


class GeminiInterpreter:
    """Thin, safe wrapper around the Google Gen AI SDK."""

    def __init__(self, config: Optional[AIConfig] = None) -> None:
        self._config = config or load_config()

    @property
    def is_configured(self) -> bool:
        """True when an API key is available."""
        return self._config.is_configured

    def ask(
        self,
        question: str,
        context: str,
        image: Optional[Image.Image] = None,
    ) -> AIResponse:
        """Answer a question using only the supplied context (and image)."""
        question = (question or "").strip()
        if not question:
            return AIResponse(AIStatus.INVALID_INPUT, message="Enter a question first.")
        if not self._config.is_configured:
            return AIResponse(
                AIStatus.NOT_CONFIGURED,
                message="No GEMINI_API_KEY configured. See the README to enable AI.",
            )
        if not context.strip() and image is None:
            return AIResponse(
                AIStatus.NO_CONTEXT,
                message=(
                    "There is no diagram data to ground an answer. Enter equipment "
                    "and connections first, or opt in to sending the drawing image."
                ),
            )

        try:  # Imported lazily so the app starts without the package.
            from google import genai
            from google.genai import errors as genai_errors
            from google.genai import types
        except ImportError:
            return AIResponse(
                AIStatus.UNAVAILABLE,
                message="The 'google-genai' package is not installed.",
            )

        diagram_data = context if context.strip() else "(no structured data entered)"
        prompt = f"DIAGRAM DATA:\n{diagram_data}\n\nQUESTION:\n{question}"

        try:
            client = genai.Client(api_key=self._config.api_key)
            contents: list = [prompt]
            if image is not None:
                contents.append(
                    types.Part.from_bytes(
                        data=image_to_png_bytes(image), mime_type="image/png"
                    )
                )
            response = client.models.generate_content(
                model=self._config.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=self._config.temperature,
                    max_output_tokens=self._config.max_output_tokens,
                ),
            )
        except genai_errors.APIError as exc:
            return _api_error_response(exc)
        except Exception as exc:  # Never echo request content or secrets.
            return AIResponse(
                AIStatus.ERROR,
                message=f"Unexpected error while contacting Gemini ({type(exc).__name__}).",
            )

        text = (getattr(response, "text", None) or "").strip()
        if not text:
            return AIResponse(
                AIStatus.ERROR,
                message="The model returned no text (the response may have been blocked).",
            )
        return AIResponse(AIStatus.OK, text=text)