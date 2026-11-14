"""The short, transient kitchen-setup interview shared by Talk and the text fallback."""
from dataclasses import dataclass, field

from . import profile

MAX_TRANSCRIPT = 6_000
MAX_ANSWER = 6_000


@dataclass(frozen=True)
class Topic:
    id: str
    question: str
    follow_up: str
    profile_keys: tuple[str, ...]


TOPICS = (
    Topic("kitchen", "What kind of kitchen and cuisine do you run, and how many seats or typical guests do you serve?",
          "Could you tell me a little more about your cuisine, seats, or typical guests?",
          ("business_type", "cuisine", "covers")),
    Topic("delivery_days", "Which weekdays can your kitchen receive deliveries?",
          "Which delivery weekdays work for your kitchen?",
          ("delivery_days",)),
    Topic("standing_orders", "What do you usually order on each weekday, including amounts and units?",
          "Could you give me one weekday and the usual products with their amounts?",
          ("standing_orders",)),
    Topic("dietary_allergens", "Which diets or allergens does your kitchen avoid?",
          "Could you name the diets or allergens the kitchen needs us to avoid?",
          ("dietary", "allergens")),
    Topic("usual_products", "Which products or brands are favourites or usual in your kitchen?",
          "Could you name one or two usual products or brands?",
          ("usual_products",)),
    Topic("budget", "What order total feels comfortable for a typical order?",
          "What approximate amount in euros feels comfortable for one order?",
          ("spend_comfort", "budget")),
    Topic("anything_else", "Is there anything else about your kitchen or suppliers I should remember?",
          "Is there one other kitchen detail you would like me to remember?",
          ("notes",)),
)
_TOPICS = {topic.id: topic for topic in TOPICS}

SYSTEM = """You are a warm, brief kitchen-setup interviewer for a restaurant kitchen.
- Speak in the chef's language; English and Finnish are both welcome, and follow the language the chef uses.
- Ask exactly one question at a time, keeping it short. Cover the remaining topics in this order: kitchen and cuisine plus seats
  and typical guests; delivery days; usual or standing orders for each weekday with amounts and units; diets and
  allergens the kitchen avoids; favourite or usual products and brands; budget comfort per order; anything else.
- The current kitchen profile is supplied as data. Skip a topic that is already answered there unless the chef says
  they want to change it. Follow up once or again only when the chef's answer is genuinely vague.
- After every answer, call record_answer with the topic id and the chef's exact words. Never write a profile memory.
- When the topics are covered, call finish_interview. Then say exactly: "Here's what I'll remember. Check it on screen
  and confirm." The screen and the existing approver-key onboarding endpoint are the only way to save; you cannot
  confirm or approve anything yourself.
- Keep the conversation warm and concise so it finishes in about two or three minutes. Never ask two separate
  questions in one turn, and do not order anything during this interview."""

TOOLS = [{"functionDeclarations": [
    {"name": "record_answer", "description": "Append one chef answer to this interview transcript. This never saves a profile.",
     "parameters": {"type": "OBJECT", "properties": {
         "topic": {"type": "STRING", "description": "One of the interview topic ids."},
         "text": {"type": "STRING", "description": "The chef's answer in their own words."}},
         "required": ["topic", "text"]}},
    {"name": "finish_interview", "description": "Extract the collected answers into the editable onboarding preview.",
     "parameters": {"type": "OBJECT", "properties": {}}},
]}]


def _has_value(value) -> bool:
    return value not in (None, "", [], {})


def _saved_answers(buyer_id: str) -> dict:
    saved = {}
    try:
        questions = profile.onboarding(buyer_id).get("questions", [])
    except Exception:  # noqa: BLE001 - an unavailable profile must not disable the interview
        questions = []
    saved.update({str(q.get("id")): q.get("answer") for q in questions if isinstance(q, dict) and "id" in q})
    try:
        context = profile.context(buyer_id)
        for fact in context.get("onboarding_facts") or []:
            if isinstance(fact, dict) and fact.get("key"):
                saved[str(fact["key"])] = fact.get("value")
        for key in ("delivery_days", "standing_orders", "dietary", "allergens", "notes"):
            if _has_value(context.get(key)):
                saved[key] = context[key]
        usual = context.get("usual_products") or context.get("usual_product_ids")
        if _has_value(usual):
            saved["usual_products"] = usual
    except Exception:  # noqa: BLE001 - a profile read failure leaves all topics available
        pass
    return saved


def _topic_is_saved(topic: Topic, saved: dict) -> bool:
    return any(_has_value(saved.get(key)) for key in topic.profile_keys)


def _normalise_answers(answers) -> list[dict[str, str]]:
    if answers is None:
        return []
    if not isinstance(answers, list):
        raise ValueError("answers must be a list")
    out = []
    for answer in answers:
        if not isinstance(answer, dict):
            raise ValueError("each answer needs a topic and text")
        topic = answer.get("topic")
        text = answer.get("text")
        if not isinstance(topic, str) or topic.strip() not in _TOPICS:
            raise ValueError("unknown interview topic")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{topic}: write a short answer")
        out.append({"topic": topic.strip(), "text": text.strip()[:MAX_ANSWER]})
    return out


def _is_vague(topic: Topic, text: str) -> bool:
    clean = " ".join(text.casefold().strip().rstrip(".!?").split())
    if topic.id == "anything_else" and clean in {"no", "no thanks", "nothing", "nothing else", "that's all"}:
        return False
    if clean in {"yes", "yeah", "yep", "no", "maybe", "same", "not sure", "i don't know", "unknown", "fine"}:
        return True
    # A one- or two-word label such as "a restaurant" does not answer the combined kitchen topic.
    return topic.id == "kitchen" and len(clean.split()) < 3


def transcript_text(answers) -> str:
    """Turn the transient answers into the untrusted text consumed by profile.from_about."""
    rows = _normalise_answers(answers)
    return "\n".join(f"{_TOPICS[row['topic']].id}: {row['text']}" for row in rows)[:MAX_TRANSCRIPT]


async def onboarding_preview(buyer_id: str, answers) -> dict:
    """Return exactly the preview body used by POST /api/profile/onboarding, without storing anything."""
    about = transcript_text(answers)
    proposed, unclear = (await profile.from_about(about)) if about else ({}, [])
    proposed = proposed or {}
    unclear = unclear or []
    questions = {q["id"]: q["question"] for q in profile.onboarding(buyer_id).get("questions", [])}
    return {"stored": False,
            "proposed": [{"id": key, "question": questions.get(key, "What else should I remember about your kitchen?"),
                          "value": value} for key, value in proposed.items()],
            "unclear": unclear,
            "hints": profile.hints(proposed)}


async def next_step(buyer_id: str, answers) -> dict:
    """Advance the stateless text interview by one question or finish with its preview."""
    rows = _normalise_answers(answers)
    last = {row["topic"]: row["text"] for row in rows}
    saved = _saved_answers(buyer_id)
    for topic in TOPICS:
        if topic.id in last:
            if _is_vague(topic, last[topic.id]):
                return {"question": topic.follow_up, "topic": topic.id, "done": False}
            continue
        if _topic_is_saved(topic, saved):
            continue
        return {"question": topic.question, "topic": topic.id, "done": False}
    return {"done": True, "preview": await onboarding_preview(buyer_id, rows)}


@dataclass
class InterviewSession:
    """Per-WebSocket transcript; it deliberately has no profile-writing method."""

    buyer_id: str
    transcript: list[dict[str, str]] = field(default_factory=list)

    def record_answer(self, args: dict) -> dict:
        rows = _normalise_answers([args])
        self.transcript.append(rows[0])
        return {"recorded": True}

    async def finish(self) -> dict:
        return await onboarding_preview(self.buyer_id, self.transcript)


Session = InterviewSession
