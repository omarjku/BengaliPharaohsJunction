"""The fixed onboarding questions. Answers are stored as ALWAYS memories (source=onboarding)."""

from __future__ import annotations

from dataclasses import dataclass

from .models import MemoryKind


@dataclass(frozen=True)
class OnboardingQuestion:
    id: str
    question: str
    kind: MemoryKind
    key: str  # conflict key; "" = use the answer itself (allergens: one memory per allergen)


ONBOARDING_QUESTIONS: tuple[OnboardingQuestion, ...] = (
    OnboardingQuestion("business_type", "What kind of business do you run?",
                       MemoryKind.BUSINESS_TYPE, "business_type"),
    OnboardingQuestion("delivery_days", "Which weekdays can you receive deliveries?",
                       MemoryKind.DELIVERY_DAYS, "delivery_days"),
    OnboardingQuestion("allergens", "Which allergens must we always avoid?",
                       MemoryKind.ALLERGEN_AVOID, ""),
    OnboardingQuestion("spend_comfort", "What order total are you comfortable with on your own?",
                       MemoryKind.SPEND_COMFORT, "order_total"),
    OnboardingQuestion("local_preference", "Do you prefer Finnish / local products?",
                       MemoryKind.LOCAL_PREFERENCE, "origin"),
)  # fmt: skip
