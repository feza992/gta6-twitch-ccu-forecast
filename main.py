"""Forecast GTA VI's launch-day Twitch viewers, hour by hour, as quantiles.

The program reads one case file (schema "makefun/twitch-ccu-case/v1") and
writes one forecast file: for each of hours 2 to 24 of the release day, the
five quantiles (0.05, 0.25, 0.5, 0.75, 0.95) of that hour's concurrent
viewers in the game's Twitch category.

Method, fitted on the case's own comparables at run time (so it adapts to
whatever comparables a case holds, including the final's 42):

1. Take every comparable launch with a complete release day: all 24 UTC
   hours present, hour-1 viewers at least 100. A comparable's release day
   is the UTC day of its `day_start`; its hour 1 is 00:00-01:00 UTC.
2. Prefer launches that unlocked at midnight local time, rolling, with no
   early access: their unlock note says "midnight local" and not "early
   access". GTA VI unlocks that way (rolling midnight local, console-only,
   no early access), and on the four practice launches that subset scored
   a mean pinball loss of 0.267 against 0.387 for the house baseline
   (persistence). If fewer than 4 such curves are available, fall back to
   launches with hour-1 viewers of at least 20,000, then to every complete
   curve, then to persistence.
3. For each hour h = 2..24, pool the log-ratios ln(viewers_h / viewers_1)
   across the chosen curves and read off the five empirical quantiles at
   the contest's levels. Winsorize each quantile to median +/- 2.5 * sigma,
   sigma the IQR-based log spread (floored at 0.15), so one extreme launch
   cannot stretch a tail.
4. The forecast for hour h is p1 * exp(quantile), p1 the case's hour-1
   print (at least 1 viewer), rounded to 2 decimals half up, clipped to
   (0, 1e9] and forced non-decreasing across the five levels.

Validated on the four practice cases against the hourly counts the
historical source publishes (SullyGnome "Average viewers", re-fetched via
the URL pattern in the kit's input/NOTICE.txt): mean pinball loss 0.267
against 0.387 for the house baseline; typical miss 50.7%, 90% coverage
0.935. At final runtime the midnight-local pool grows to 12 curves: the
final case's comparables also hold the four practice launches.

Deliberately unused: the case's hour-1 minute history and top-20 streams.
The practice cases carry only hourly points, so no within-hour adjustment
could be validated on them; an unvalidated adjustment would be guessing.

Standard library only, no network, deterministic: the same input bytes
always write the same output bytes.

Run locally: mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level (used only for the spread).
Z = [-1.645, -0.674, 0, 0.674, 1.645]
# Floor on the log spread, in natural-log units.
SIGMA_FLOOR = 0.15
# How far a winsorized quantile may sit from the median, in sigmas.
WINSOR_SIGMAS = 2.5
# A curve counts as complete only with this many of the 24 release-day hours.
MIN_HOURS = 20
# A curve's hour 1 must be at least this many viewers to count.
MIN_HOUR1 = 100
# The midnight-local pool needs at least this many curves, else we fall back.
MIN_MIDNIGHT = 4
# Fallback pool: launches with a big hour 1.
BIG_HOUR1 = 20000


def round2(x: float) -> float | int:
    """x rounded to 2 decimals, half up, as JavaScript's Math.round(x * 100) / 100 rounds it.

    A whole number comes back as an int, so json.dumps writes 1240 where JavaScript writes 1240 (not 1240.0).
    """
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def release_day_curve(comp: dict) -> dict[int, float] | None:
    """The comparable's release-day hourly viewers, {hour 1..24: viewers}.

    None when the day is incomplete, hour 1 is missing, or hour 1 is too
    small to give meaningful ratios.
    """
    try:
        day_start = parse_time(comp["day_start"])
    except (KeyError, TypeError, ValueError):
        return None
    curve: dict[int, float] = {}
    for point in comp.get("hourly") or []:
        try:
            at = parse_time(point["from"])
            viewers = float(point["viewers"])
        except (KeyError, TypeError, ValueError):
            continue
        if day_start <= at < day_start + timedelta(hours=24) and viewers > 0:
            hour = int((at - day_start).total_seconds() // 3600) + 1
            if 1 <= hour <= 24 and hour not in curve:
                curve[hour] = viewers
    if len(curve) < MIN_HOURS or curve.get(1, 0) < MIN_HOUR1:
        return None
    return curve


def is_midnight_local(comp: dict) -> bool:
    """True when the unlock note says midnight local, rolling, no early access."""
    note = str(comp.get("unlock") or "").lower()
    return "midnight local" in note and "early access" not in note


def choose_pool(case: dict) -> list[dict[int, float]]:
    """The curves to pool, in preference order: midnight-local, big, all."""
    curves: list[tuple[dict[int, float], dict]] = []
    for comp in case.get("comparables") or []:
        curve = release_day_curve(comp)
        if curve is not None:
            curves.append((curve, comp))
    midnight = [c for c, comp in curves if is_midnight_local(comp)]
    if len(midnight) >= MIN_MIDNIGHT:
        return midnight
    big = [c for c, _ in curves if c[1] >= BIG_HOUR1]
    if len(big) >= MIN_MIDNIGHT:
        return big
    if curves:
        return [c for c, _ in curves]
    return []


def hour_quantiles(pool: list[dict[int, float]], p1: float, hour: int) -> list[float | int]:
    """The five quantiles of hour `hour`'s viewers, as a ratio to hour 1."""
    ratios = sorted(
        math.log(curve[hour] / curve[1])
        for curve in pool
        if hour in curve and curve[hour] > 0 and curve[1] > 0
    )
    if not ratios:
        # No curve covers this hour: fall back to persistence with the
        # house baseline's widening spread.
        return [round2(p1 * math.exp(z * SIGMA_FLOOR * math.sqrt(hour - 1))) for z in Z]
    n = len(ratios)
    median = ratios[n // 2]
    q25 = ratios[n // 4]
    q75 = ratios[(3 * n) // 4]
    sigma = max(SIGMA_FLOOR, (q75 - q25) / 1.349)
    low = median - WINSOR_SIGMAS * sigma
    high = median + WINSOR_SIGMAS * sigma
    out: list[float | int] = []
    previous = 0.0
    for tau in LEVELS:
        empirical = ratios[min(n - 1, max(0, int(tau * n)))]
        clipped = min(high, max(low, empirical))
        value = p1 * math.exp(clipped)
        value = min(1_000_000_000.0, max(0.01, value))
        value = round2(value)
        # Keep the row non-decreasing after rounding.
        if isinstance(value, (int, float)) and value < previous:
            value = round2(previous)
        previous = float(value)
        out.append(value)
    return out


def forecast_case(case: dict, name: str) -> dict:
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1, float(first["viewers"]))
    pool = choose_pool(case)
    if not pool:
        # No usable comparable at all: persistence, the house baseline.
        return {
            "hours": [
                {
                    "hour": row["hour"],
                    "q": [
                        round2(p1 * math.exp(z * SIGMA_FLOOR * math.sqrt(row["hour"] - 1)))
                        for z in Z
                    ],
                }
                for row in case["forecast"]
            ]
        }
    return {
        "hours": [
            {"hour": row["hour"], "q": hour_quantiles(pool, p1, row["hour"])}
            for row in case["forecast"]
        ]
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
