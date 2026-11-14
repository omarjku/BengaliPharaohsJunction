"""Read-only delivery calendar data plus buyer-owned weekly menus and recurring actions."""
import copy
import json
import os
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import ask, config, kitchen, menu, orders, profile, valio


WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
FULL_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
DAY_ALIASES = {**dict(zip(WEEKDAYS, FULL_WEEKDAYS)), **dict(zip(FULL_WEEKDAYS, FULL_WEEKDAYS))}
HELSINKI = ZoneInfo("Europe/Helsinki")
SEED = Path(__file__).with_name("calendar_seed.json")
SEEDS = json.loads(SEED.read_text(encoding="utf-8"))
MAX_RANGE_DAYS = 62
_file_lock = threading.Lock()


class PerCover(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient: str = Field(min_length=1, max_length=160)
    amount: float = Field(gt=0, le=100_000, allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=20)

    @field_validator("ingredient", "unit")
    @classmethod
    def non_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class Dish(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    recipe: str | None = Field(default=None, max_length=4000)
    per_cover: list[PerCover] | None = Field(default=None, max_length=50)

    @field_validator("name")
    @classmethod
    def non_blank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("recipe")
    @classmethod
    def clean_recipe(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class WeeklyMenuInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekday: str | None = None
    name: str = Field(min_length=1, max_length=200)
    dishes: list[Dish] = Field(min_length=1, max_length=12)
    covers: int | None = Field(default=None, ge=1, le=2000)
    active: bool = True

    @field_validator("weekday")
    @classmethod
    def known_weekday(cls, value: str | None) -> str | None:
        if value is not None and value.lower() not in WEEKDAYS:
            raise ValueError("weekday must be mon, tue, wed, thu, fri, sat or sun")
        return value.lower() if value is not None else None

    @field_validator("name")
    @classmethod
    def non_blank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


def _today() -> date:
    return datetime.now(HELSINKI).date()


def _menu_path(buyer_id: str) -> Path:
    return config.DATA_DIR / "menus" / f"{buyer_id}.json"


def _skip_path(buyer_id: str) -> Path:
    return config.DATA_DIR / "calendar" / f"{buyer_id}.json"


def _canonical_weekday(value: str) -> str:
    key = str(value).strip().lower()
    if key not in DAY_ALIASES:
        raise HTTPException(422, detail="unknown weekday")
    return DAY_ALIASES[key]


def _menu_weekday(value: str) -> str:
    key = str(value).strip().lower()
    if key not in WEEKDAYS:
        raise HTTPException(422, detail="weekday must be mon, tue, wed, thu, fri, sat or sun")
    return key


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except (OSError, ValueError):
        raise HTTPException(503, detail="Calendar data could not be read") from None


def _atomic_write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _seed_for(buyer_id: str) -> list[dict]:
    rows = SEEDS.get(buyer_id)
    if rows is None and buyer_id.startswith("try-"):
        rows = SEEDS.get("try-*")
    return copy.deepcopy(rows or [])


def _stored_menus(buyer_id: str) -> tuple[list[dict], bool]:
    raw = _read_json(_menu_path(buyer_id))
    if raw is None:
        return _seed_for(buyer_id), False
    if not isinstance(raw, list) or not all(isinstance(row, dict) for row in raw):
        raise HTTPException(503, detail="Saved weekly menus are invalid")
    return copy.deepcopy(raw), True


def _sort_menus(rows: list[dict]) -> list[dict]:
    order = {weekday: index for index, weekday in enumerate(WEEKDAYS)}
    return sorted(rows, key=lambda row: order.get(row.get("weekday"), len(WEEKDAYS)))


def weekly_menus(buyer_id: str) -> list[dict]:
    """Return the buyer's weekly menus, including the labelled demo seed when no edits exist."""
    rows, _ = _stored_menus(buyer_id)
    return _sort_menus(rows)


def save_weekly_menu(buyer_id: str, weekday: str, value: WeeklyMenuInput) -> dict:
    day = _menu_weekday(weekday)
    if value.weekday is not None and value.weekday != day:
        raise HTTPException(422, detail="The body weekday must match the route")
    rows, _ = _stored_menus(buyer_id)
    saved = value.model_dump(mode="json", exclude_none=True)
    saved["weekday"] = day
    rows = [row for row in rows if row.get("weekday") != day]
    rows.append(saved)
    with _file_lock:
        _atomic_write(_menu_path(buyer_id), _sort_menus(rows))
    return saved


def delete_weekly_menu(buyer_id: str, weekday: str) -> dict:
    day = _menu_weekday(weekday)
    rows, _ = _stored_menus(buyer_id)
    if not any(row.get("weekday") == day for row in rows):
        raise HTTPException(404, detail="No weekly menu for that weekday")
    rows = [row for row in rows if row.get("weekday") != day]
    with _file_lock:
        _atomic_write(_menu_path(buyer_id), _sort_menus(rows))
    return {"weekday": day, "deleted": True}


def _read_skips(buyer_id: str) -> set[str]:
    raw = _read_json(_skip_path(buyer_id))
    if raw is None:
        return set()
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise HTTPException(503, detail="Saved calendar skips are invalid")
    return set(raw)


def _validate_weekday_date(weekday: str, target: date) -> str:
    full = _canonical_weekday(weekday)
    if target.weekday() != FULL_WEEKDAYS.index(full):
        raise HTTPException(422, detail=f"{target.isoformat()} is not a {full} date")
    return full


def skip_recurring(buyer_id: str, weekday: str, target: date) -> dict:
    full = _validate_weekday_date(weekday, target)
    if not any(row.get("weekday") == full for row in profile.standing_orders(buyer_id)):
        raise HTTPException(404, detail="No standing order for that weekday")
    skips = _read_skips(buyer_id)
    skips.add(target.isoformat())
    with _file_lock:
        _atomic_write(_skip_path(buyer_id), sorted(skips))
    return {"weekday": full, "date": target.isoformat(), "skipped": True}


def _standing_order(buyer_id: str, weekday: str) -> tuple[str, dict]:
    full = _canonical_weekday(weekday)
    for row in profile.standing_orders(buyer_id):
        if row.get("weekday") == full:
            return full, row
    raise HTTPException(404, detail="No standing order for that weekday")


async def place_recurring(buyer_id: str, weekday: str, target: date) -> dict:
    full, _ = _standing_order(buyer_id, weekday)
    _validate_weekday_date(full, target)
    if target.isoformat() in _read_skips(buyer_id):
        raise HTTPException(409, detail="That recurring order was skipped for this date")
    return await ask.ask(f"usual {full} order", target, buyer_id)


def _menu_text(row: dict) -> str:
    lines = [str(row.get("name") or "weekly menu")]
    for dish in row.get("dishes") or []:
        name = str(dish.get("name") or "").strip()
        recipe = str(dish.get("recipe") or "").strip()
        portions = ", ".join(f"{item.get('amount')} {item.get('unit')} {item.get('ingredient')}"
                             for item in dish.get("per_cover") or [])
        detail = ": ".join(part for part in (recipe, portions) if part)
        lines.append(f"{name}: {detail}" if detail else name)
    return "\n".join(lines)


async def plan_weekly_menu(buyer_id: str, weekday: str, target: date) -> dict:
    day = _menu_weekday(weekday)
    _validate_weekday_date(day, target)
    row = next((item for item in weekly_menus(buyer_id)
                if item.get("weekday") == day and item.get("active", True)), None)
    if row is None:
        raise HTTPException(404, detail="No active weekly menu for that weekday")
    if row.get("covers") is None:
        raise HTTPException(422, detail="This weekly menu has no covers")
    return await menu.propose(_menu_text(row), int(row["covers"]), target, buyer_id)


def _order_records(buyer_id: str) -> list[dict]:
    seen = set()
    ids = []
    for row in orders.audit_log(buyer_id, 10_000):
        status = (row.get("front_door") or {}).get("status")
        order_id = ((row.get("input") or {}).get("request") or {}).get("id")
        if status in {"confirmed", "pending_approval"} and order_id and order_id not in seen:
            seen.add(order_id)
            ids.append(order_id)
    records = []
    for order_id in ids:
        try:
            record = orders.get(order_id, buyer_id)
        except HTTPException:
            continue
        if record.get("status") in {"confirmed", "pending_approval"}:
            records.append(record)
    return records


def _delivery_entry(record: dict) -> dict:
    pending = record.get("status") == "pending_approval"
    entry = {"kind": "delivery_pending" if pending else "delivery_confirmed",
             "order_id": record.get("id"),
             "title": "Delivery waiting for your OK" if pending else "Confirmed delivery",
             "lines": [{"name": line.get("name") or line.get("product_id"),
                        "quantity": line.get("quantity"), "unit": line.get("unit")}
                       for line in record.get("lines") or []],
             "total_cents": record.get("total_cents"), "status": record.get("status")}
    if pending:
        entry["reason"] = "waiting for your OK"
    return entry


def _fresh_cached_cutoffs(today: date) -> dict[date, dict]:
    candidates: dict[date, list[dict]] = {}
    now_mono = time.monotonic()
    cache = getattr(valio, "_cache", {})
    for key, cached in cache.items():
        if not isinstance(key, tuple) or len(key) != 2 or not isinstance(cached, tuple) or len(cached) != 2:
            continue
        _, requested = key
        try:
            requested_day = date.fromisoformat(str(requested))
        except ValueError:
            continue
        if requested_day < today:
            continue
        timestamp, quote = cached
        if not isinstance(timestamp, (int, float)) or now_mono - timestamp > valio.CACHE_TTL_S:
            continue
        if not isinstance(quote, dict) or not quote.get("order_cutoff"):
            continue
        candidates.setdefault(requested_day, []).append(quote)
    out = {}
    for requested_day in sorted(candidates):
        quotes = candidates[requested_day]
        quote = min(quotes, key=lambda item: item.get("order_cutoff") or "")
        closing = quote.get("order_cutoff")
        try:
            parsed = datetime.fromisoformat(closing)
            passed = parsed <= datetime.now(timezone.utc) if parsed.tzinfo else parsed <= datetime.now()
        except (TypeError, ValueError):
            continue
        out[requested_day] = {"closing_time": closing, "passed": passed}
    return out


def calendar_view(buyer_id: str, start: date, end: date) -> dict:
    if end < start:
        raise HTTPException(422, detail="to must be on or after from")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise HTTPException(422, detail=f"Calendar ranges may contain at most {MAX_RANGE_DAYS} days")
    today = _today()
    records = _order_records(buyer_id)
    by_date: dict[str, list[dict]] = {}
    for record in records:
        requested = record.get("requested_date")
        if isinstance(requested, str):
            by_date.setdefault(requested, []).append(record)
    standing = profile.standing_orders(buyer_id)
    menus = {row.get("weekday"): row for row in weekly_menus(buyer_id) if row.get("active", True)}
    skips = _read_skips(buyer_id)
    context = kitchen.kitchen_context(buyer_id)
    average_covers = ((context.get("covers") or {}).get("avg_per_weekday") or {})
    cutoffs = _fresh_cached_cutoffs(today)
    days = []
    for offset in range((end - start).days + 1):
        target = start + timedelta(days=offset)
        target_iso = target.isoformat()
        day_key = WEEKDAYS[target.weekday()]
        entries = [_delivery_entry(record) for record in by_date.get(target_iso, [])]
        for order in standing:
            if order.get("weekday") != FULL_WEEKDAYS[target.weekday()] or target_iso in skips:
                continue
            entries.append({"kind": "recurring_order", "weekday": order["weekday"],
                            "lines": copy.deepcopy(order.get("lines") or []),
                            "source": order.get("source") or "you told me",
                            "placed": bool(by_date.get(target_iso))})
        if row := menus.get(day_key):
            entries.append({"kind": "weekly_menu", "name": row.get("name"),
                            "dishes": [{"name": dish.get("name"), "has_recipe": bool(dish.get("recipe"))}
                                       for dish in row.get("dishes") or []],
                            "covers": row.get("covers")})
        expected = average_covers.get(day_key)
        if expected is not None and (context.get("simulated") or context.get("sources")):
            entries.append({"kind": "guests_expected", "value": expected,
                            "simulated": bool(context.get("simulated"))})
        day = {"date": target_iso, "today": target == today, "entries": entries}
        if target in cutoffs:
            day["cutoff"] = cutoffs[target]
        days.append(day)
    return {"days": days,
            "legend": {"delivery_confirmed": "Confirmed delivery", "delivery_pending": "Waiting for your OK",
                        "recurring_order": "Recurring order", "weekly_menu": "Weekly menu",
                        "guests_expected": "Expected guests"}}
