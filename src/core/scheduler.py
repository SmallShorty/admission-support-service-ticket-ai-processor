"""
Priority recalculation scheduler.

Runs every RECALC_INTERVAL_MINUTES and recalculates w_wait-driven priority for
all open tickets by calling the Nest.js batch endpoint. The job is skipped
outside the configured working window (default 10:00–18:00 Moscow time).

Hardcoded defaults (overridable via .env):
  RECALC_INTERVAL_MINUTES = 30
  RECALC_HOUR_START       = 10   (inclusive, local tz)
  RECALC_HOUR_END         = 18   (exclusive, local tz)
  RECALC_TIMEZONE         = Europe/Moscow
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python < 3.9

from .config import settings
from .priority import calculate_priority

logger = logging.getLogger("scheduler.priority")


def _is_within_recalc_window(tz: ZoneInfo) -> bool:
    """Return True if current local time falls inside the recalculation window."""
    local_hour = datetime.now(tz).hour
    return settings.RECALC_HOUR_START <= local_hour < settings.RECALC_HOUR_END


async def _fetch_open_tickets(client: httpx.AsyncClient) -> list[dict]:
    """Fetch all open tickets from the Nest.js API."""
    url = f"{settings.NEST_API_BASE_URL}{settings.NEST_API_RECALC_ENDPOINT}"
    response = await client.get(url, timeout=settings.NEST_API_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


async def _push_priorities(client: httpx.AsyncClient, updates: list[dict]) -> None:
    """Send recalculated priorities back to Nest.js in a single batch call."""
    url = settings.NEST_API_BATCH_URL
    response = await client.patch(url, json=updates, timeout=settings.NEST_API_TIMEOUT_SECONDS)
    response.raise_for_status()


def _recalc_ticket(ticket: dict, now: datetime) -> dict | None:
    """
    Recalculate priority for a single ticket dict.
    Expected ticket fields (camelCase, as returned by Nest.js):
      id, intent, confidence, createdAt,
      applicant.hasBvi, applicant.hasSpecialQuota, applicant.hasTargetQuota,
      applicant.hasSeparateQuota, applicant.hasPriorityRight,
      applicant.originalDocumentReceived, applicant.examScores[].score
    Returns None if the ticket lacks required fields (intent / confidence).
    """
    intent = ticket.get("intent")
    confidence = ticket.get("confidence")

    if not intent or confidence is None:
        return None

    created_at_raw = ticket.get("createdAt")
    if not created_at_raw:
        return None
    created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))

    applicant = ticket.get("applicant") or {}
    scores = applicant.get("examScores") or []
    total_score = sum(s.get("score", 0) for s in scores)

    result = calculate_priority(
        category=intent,
        confidence=float(confidence),
        created_at=created_at,
        has_bvi=bool(applicant.get("hasBvi")),
        has_special_quota=bool(applicant.get("hasSpecialQuota")),
        has_target_quota=bool(applicant.get("hasTargetQuota")),
        has_separate_quota=bool(applicant.get("hasSeparateQuota")),
        has_priority_right=bool(applicant.get("hasPriorityRight")),
        original_submitted=bool(applicant.get("originalDocumentReceived")),
        score=total_score,
        now=now,
    )

    return {"id": ticket["id"], "priority": result["priority"]}


async def run_recalculation() -> int:
    """
    Fetch open tickets, recalculate priorities, push updates to Nest.js.
    Returns the number of tickets updated.
    """
    now = datetime.now(timezone.utc)
    async with httpx.AsyncClient() as client:
        tickets = await _fetch_open_tickets(client)

        updates = [u for t in tickets if (u := _recalc_ticket(t, now)) is not None]

        if not updates:
            logger.info("Recalculation: no eligible tickets found")
            return 0

        await _push_priorities(client, updates)
        logger.info(f"Recalculation: updated {len(updates)}/{len(tickets)} tickets")
        return len(updates)


def _seconds_until_next_tick(interval_minutes: int) -> float:
    """
    Return seconds until the next wall-clock boundary aligned to interval_minutes.
    Example: interval=30, current time 14:07:22 → sleeps until 14:30:00 (1358s).
    """
    now = datetime.now(timezone.utc)
    total_minutes = now.hour * 60 + now.minute
    minutes_into_slot = total_minutes % interval_minutes
    minutes_to_wait = interval_minutes - minutes_into_slot
    seconds_to_wait = minutes_to_wait * 60 - now.second - now.microsecond / 1_000_000
    # Guard against sub-second drift landing exactly on a boundary
    return seconds_to_wait if seconds_to_wait > 1 else seconds_to_wait + interval_minutes * 60


async def priority_scheduler_loop() -> None:
    """
    Asyncio task that fires run_recalculation() aligned to wall-clock boundaries.

    Sleeps until the next :00 or :30 mark (for a 30-min interval), then checks
    whether the current local time falls inside the working window before running.
    This mirrors cron behaviour — the job always fires at predictable times.
    """
    tz = ZoneInfo(settings.RECALC_TIMEZONE)

    logger.info(
        f"Priority scheduler started — every {settings.RECALC_INTERVAL_MINUTES} min "
        f"at wall-clock boundaries, "
        f"{settings.RECALC_HOUR_START:02d}:00–{settings.RECALC_HOUR_END:02d}:00 "
        f"{settings.RECALC_TIMEZONE}"
    )

    while True:
        sleep_seconds = _seconds_until_next_tick(settings.RECALC_INTERVAL_MINUTES)
        next_tick = datetime.now(tz) + timedelta(seconds=sleep_seconds)
        logger.debug(f"Next recalculation tick at {next_tick.strftime('%H:%M:%S %Z')}")

        await asyncio.sleep(sleep_seconds)

        if not _is_within_recalc_window(tz):
            logger.debug("Recalculation skipped: outside working window")
            continue

        try:
            await run_recalculation()
        except Exception:
            logger.exception("Recalculation run failed")
