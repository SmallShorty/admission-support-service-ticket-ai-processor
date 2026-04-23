from datetime import datetime, timedelta, timezone
from math import sqrt, floor

K_WAIT = 3.0
MAX_SCORE = 310
CAP_STATUS_RAW = 20
CAP_STATUS_TOTAL = 23.0
CONF_FLOOR = 0.70

# Working hours used exclusively for w_wait calculation (hours elapsed while staff is on duty).
# These are NOT the recalculation schedule window — see Settings.RECALC_HOUR_START/END in config.py.
WORK_START = 9   # 09:00 UTC
WORK_END = 18    # 18:00 UTC

CATEGORY_WEIGHTS: dict[str, float] = {
    "TECHNICAL_ISSUES": 70.0,
    "DEADLINES_TIMELINES": 65.0,
    "ENROLLMENT": 62.0,
    "PAYMENTS_CONTRACTS": 55.0,
    "DOCUMENT_SUBMISSION": 50.0,
    "SCORES_COMPETITION": 45.0,
    "STATUS_VERIFICATION": 30.0,
    "DORMITORY_HOUSING": 25.0,
    "STUDIES_SCHEDULE": 15.0,
    "PROGRAM_CONSULTATION": 12.0,
    "EVENTS": 7.0,
    "GENERAL_INFO": 5.0,
}


def _get_k_conf(conf: float) -> float:
    if conf >= 0.90: return 1.000
    if conf >= 0.75: return 0.950
    if conf >= 0.60: return 0.875
    if conf >= 0.45: return 0.800
    if conf >= 0.30: return 0.725
    return CONF_FLOOR


def _get_score_bonus(score: int) -> float:
    s = min(score, MAX_SCORE)
    if s < 200: return 0.0
    if s < 240: return (s - 200) / 40 * 1.0
    if s < 270: return 1.0 + (s - 240) / 30 * 3.0
    if s < 300: return 4.0 + (s - 270) / 30 * 2.0
    if s < 310: return 6.0 + (s - 300) / 10 * 1.5
    return 8.0


def _work_hours_elapsed(created_at: datetime, now: datetime) -> float:
    total = 0.0
    cur = created_at
    while cur.date() <= now.date():
        day_start = cur.replace(hour=WORK_START, minute=0, second=0, microsecond=0)
        day_end = cur.replace(hour=WORK_END, minute=0, second=0, microsecond=0)
        seg_start = max(cur, day_start)
        seg_end = min(now if cur.date() == now.date() else day_end, day_end)
        if seg_end > seg_start:
            total += (seg_end - seg_start).total_seconds() / 3600
        cur = (cur + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(0.0, total)


def _r3(value: float) -> float:
    return floor(value * 1000) / 1000


def calculate_priority(
    category: str,
    confidence: float,
    created_at: datetime,
    has_bvi: bool = False,
    has_special_quota: bool = False,
    has_target_quota: bool = False,
    has_separate_quota: bool = False,
    has_priority_right: bool = False,
    original_submitted: bool = False,
    score: int = 0,
    now: datetime | None = None,
) -> dict:
    if category not in CATEGORY_WEIGHTS:
        raise ValueError(
            f"Unknown category: {category}. Available: {list(CATEGORY_WEIGHTS.keys())}"
        )
    if now is None:
        now = datetime.now(timezone.utc)

    base_weight = CATEGORY_WEIGHTS[category]
    kc = _get_k_conf(confidence)
    w_topic = _r3(base_weight * kc)

    score = min(score, MAX_SCORE)
    status_sum = sum([
        12 if has_bvi else 0,
        10 if has_special_quota else 0,
        8 if has_target_quota else 0,
        6 if has_separate_quota else 0,
        4 if has_priority_right else 0,
        3 if original_submitted else 0,
    ])
    status_sum = min(status_sum, CAP_STATUS_RAW)
    sb = _get_score_bonus(score)
    w_status = _r3(min(status_sum + sb, CAP_STATUS_TOTAL))

    t_work = _work_hours_elapsed(created_at, now)
    w_wait = _r3(min(8.0, sqrt(t_work) * K_WAIT))

    raw = w_topic + w_status + w_wait
    priority = _r3(min(100.0, max(0.0, raw)))

    return {
        "priority": priority,
        "breakdown": {
            "w_topic": w_topic,
            "base_weight": base_weight,
            "k_conf": kc,
            "w_status": w_status,
            "status_sum": status_sum,
            "score_bonus": _r3(sb),
            "w_wait": w_wait,
            "work_hours": _r3(t_work),
        },
    }
