"""What Gemini returns: a small closed shape, NOT the Mandate itself (Agent B owns this file).

Why not the raw Mandate schema: Gemini accepts only a subset of JSON Schema, and the model must
never set ids, versions or cents. Code converts this shape into a Mandate (compile.py):
euro amounts are returned AS WRITTEN and converted with eur_to_cents(); scope is only an explicit
cue from the text ("none" = use the caller's scope).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ScopeCue = Literal["this_order", "always", "none"]


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExtractedAllergen(_Closed):
    name: str = Field(description="One allergen, lower-case, e.g. 'peanut', 'gluten'.")
    scope_cue: ScopeCue = "none"


class ExtractedMoney(_Closed):
    amount_eur: str = Field(description="The number exactly as written in the text, e.g. '500'.")
    scope_cue: ScopeCue = "none"


class ExtractedGuidance(_Closed):
    text: str
    scope_cue: ScopeCue = "none"


class ExtractedQuestion(_Closed):
    question: str
    why: str | None = None


class CompilerOutput(_Closed):
    excluded_allergens: list[ExtractedAllergen] = Field(default_factory=list)
    auto_approve_limit: ExtractedMoney | None = None  # "never more than X without asking"
    per_line_cap: ExtractedMoney | None = None
    weekly_budget: ExtractedMoney | None = None
    blocklist_product_ids: list[str] = Field(default_factory=list)  # only ids written in the text
    uncertainty_policy: Literal["ask", "decline", "approve"] | None = None  # None = not stated
    guidance: list[ExtractedGuidance] = Field(default_factory=list)  # soft wishes, never a gate
    open_questions: list[ExtractedQuestion] = Field(default_factory=list)  # ambiguous -> ask
    expires_on: str | None = Field(default=None, description="An explicit date as written, if any.")


# The exact schema sent to the model (fixtures are keyed by hash(prompt, schema, model)).
OUTPUT_SCHEMA = CompilerOutput.model_json_schema()
