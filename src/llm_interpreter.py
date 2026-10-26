"""Optional OpenAI query interpretation; retrieval and result filtering stay local."""
from __future__ import annotations

import json
import os
from typing import Any

from .schemas import Preferences

QUERY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["recommend", "similar", "refine", "show_preferences", "explain", "reset", "help"]},
        "media_selection": {"type": "string", "enum": ["books", "movies", "both", "inherit"]},
        "search_query": {"type": "string"},
        "reference_title": {"type": ["string", "null"]},
        "preferred_genres": {"type": "array", "items": {"type": "string"}},
        "excluded_genres": {"type": "array", "items": {"type": "string"}},
        "desired_mood": {"type": ["string", "null"]},
        "themes": {"type": "array", "items": {"type": "string"}},
        "language": {"type": ["string", "null"]},
        "min_year": {"type": ["integer", "null"]},
        "max_year": {"type": ["integer", "null"]},
        "max_pages": {"type": ["integer", "null"]},
        "max_runtime": {"type": ["integer", "null"]},
        "negative_content": {"type": "array", "items": {"type": "string"}},
        "explicit_fields": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["intent", "media_selection", "search_query", "reference_title", "preferred_genres", "excluded_genres", "desired_mood", "themes", "language", "min_year", "max_year", "max_pages", "max_runtime", "negative_content", "explicit_fields"],
    "additionalProperties": False,
}


def configured_api_key(streamlit_secrets: Any | None = None) -> str | None:
    """Return a server-side key from the environment or Streamlit secrets."""
    env_key = os.getenv("NVIDIA_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        secret_key = str(streamlit_secrets.get("NVIDIA_API_KEY", "")).strip() if streamlit_secrets is not None else ""
    except Exception:
        secret_key = ""
    return secret_key or None


class NemotronQueryInterpreter:
    def __init__(self, api_key: str, model: str | None = None, client: Any | None = None):
        self.model = model or os.getenv("STORYSCOUT_NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
        self.last_call_ok: bool | None = None
        self.last_error_code: str | None = None
        self.catalog_titles: list[str] = []
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url="https://integrate.api.nvidia.com/v1", timeout=20.0, max_retries=1)
        self.client = client

    def interpret(self, text: str, selection: str, preferences: Preferences) -> dict[str, Any] | None:
        active = {
            "media_selection": selection,
            "preferred_genres": preferences.preferred_genres,
            "excluded_genres": preferences.excluded_genres,
            "desired_mood": preferences.desired_mood,
            "themes": preferences.themes,
            "language": preferences.language,
            "min_year": preferences.min_year,
            "max_year": preferences.max_year,
            "max_pages": preferences.max_pages,
            "max_runtime": preferences.max_runtime,
        }
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": (
                        "Interpret messages for a book and movie catalog search. Return only valid JSON matching the requested fields. "
                        "Normalize spelling and titles in search_query, "
                        "preserve the user's meaning, and extract only constraints stated in the current message. Do not recommend "
                        "items or invent catalog facts. A bare title, character, topic, or misspelled phrase is a search request. "
                        "Detect negation as exclusions. Use media_selection=inherit unless the desired result medium is explicit. "
                        "A reference title is distinct from the desired result medium. Never infer unstated numeric limits. "
                        "Return every key, even when its value is empty. Exact JSON keys: intent, media_selection, search_query, "
                        "reference_title, preferred_genres, excluded_genres, desired_mood, themes, language, min_year, max_year, "
                        "max_pages, max_runtime, negative_content, explicit_fields. intent must be recommend, similar, refine, "
                        "show_preferences, explain, reset, or help. media_selection must be books, movies, both, or inherit. "
                        "Use null for unknown single values, [] for empty lists, and list only fields explicitly stated in this message "
                        "inside explicit_fields. Valid explicit_fields names: preferred_genres, excluded_genres, desired_mood, themes, "
                        "language, min_year, max_year, max_pages, max_runtime, negative_content, referenced_title. For short topic or "
                        "character phrases, produce a useful catalog search query rather than help. Correct obvious misspellings, "
                        "expand character names into matching catalog concepts, and keep search_query short."
                    )},
                    {"role": "user", "content": json.dumps({"message": text, "active_preferences": active, "catalog_titles": self.catalog_titles}, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
                max_tokens=1000,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            content = response.choices[0].message.content
            if not content:
                self.last_call_ok = False
                self.last_error_code = "empty_response"
                return None
            content = content.strip()
            if content.startswith("```"):
                content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            payload = json.loads(content)
            required = set(QUERY_SCHEMA["required"])
            if not isinstance(payload, dict) or not required.issubset(payload):
                self.last_call_ok = False
                self.last_error_code = "invalid_response"
                return None
            for field in ("preferred_genres", "excluded_genres", "themes", "negative_content", "explicit_fields"):
                if payload[field] is None:
                    payload[field] = []
                if not isinstance(payload[field], list):
                    self.last_call_ok = False
                    self.last_error_code = "invalid_response"
                    return None
            allowed_explicit = {"preferred_genres", "excluded_genres", "desired_mood", "themes", "language", "min_year", "max_year", "max_pages", "max_runtime", "negative_content", "referenced_title"}
            payload["explicit_fields"] = [field for field in payload["explicit_fields"] if field in allowed_explicit]
            for field in ("preferred_genres", "excluded_genres", "themes", "negative_content"):
                if field not in payload["explicit_fields"]:
                    payload[field] = []
            for field in ("desired_mood", "language", "min_year", "max_year", "max_pages", "max_runtime"):
                if field not in payload["explicit_fields"]:
                    payload[field] = None
            self.last_call_ok = True
            self.last_error_code = None if self.last_call_ok else "invalid_response"
            return payload
        except Exception as exc:
            # Network, authentication, and SDK errors preserve the local NLP path.
            self.last_call_ok = False
            status = getattr(exc, "status_code", None)
            self.last_error_code = f"http_{status}" if status else type(exc).__name__
            return None
