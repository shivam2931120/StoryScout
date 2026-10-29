"""Validated transport models; the NLP domain remains Python dataclasses."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from src.schemas import ConversationState, Preferences


class PreferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferred_genres: list[str] = Field(default_factory=list, max_length=30)
    excluded_genres: list[str] = Field(default_factory=list, max_length=30)
    desired_mood: str | None = Field(default=None, max_length=100)
    themes: list[str] = Field(default_factory=list, max_length=30)
    language: str | None = Field(default=None, max_length=80)
    min_year: int | None = Field(default=None, ge=1, le=2100)
    max_year: int | None = Field(default=None, ge=1, le=2100)
    referenced_title: str | None = Field(default=None, max_length=300)
    positive_content: list[str] = Field(default_factory=list, max_length=30)
    negative_content: list[str] = Field(default_factory=list, max_length=30)
    max_pages: int | None = Field(default=None, ge=1, le=10000)
    max_runtime: int | None = Field(default=None, ge=1, le=1000)
    contradiction_messages: list[str] = Field(default_factory=list, max_length=10)


class MessageInput(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=10000)


class StateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preferences: PreferenceInput = Field(default_factory=PreferenceInput)
    media_selection: Literal["books", "movies", "both"] = "both"
    has_explicit_media: bool = False
    selected_reference_id: str | None = Field(default=None, max_length=200)
    last_recommendations: list[str] = Field(default_factory=list, max_length=20)
    pending_title_choices: list[str] = Field(default_factory=list, max_length=20)
    messages: list[MessageInput] = Field(default_factory=list, max_length=80)
    retrieval_mode: Literal["tfidf", "semantic", "hybrid"] = "hybrid"
    last_content_query: str = Field(default='', max_length=4000)
    seen_recommendations: list[str] = Field(default_factory=list, max_length=300)

    def to_domain(self) -> ConversationState:
        values = self.model_dump()
        values["preferences"] = Preferences(**values["preferences"])
        return ConversationState(**values)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)
    state: StateInput = Field(default_factory=StateInput)
    reference_id: str | None = Field(default=None, max_length=200)
    lookup_id: str | None = Field(default=None, max_length=200)
    search_action: Literal["auto", "new", "refine", "similar"] = "auto"
    per_domain: int = Field(default=3, ge=1, le=5)


class JudgmentRequest(BaseModel):
    csv_text: str = Field(min_length=1, max_length=1_000_000)
