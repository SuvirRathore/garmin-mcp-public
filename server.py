"""Read-only MCP server exposing Garmin Connect running, strength and calorie data."""

import garth
from mcp.server.mcpserver import MCPServer

garth.resume("~/.garth")
mcp = MCPServer("garmin")


def _pace(duration_s: float | None, distance_m: float | None) -> str | None:
    if not duration_s or not distance_m:
        return None
    sec_per_km = duration_s / (distance_m / 1000)
    m, s = divmod(round(sec_per_km), 60)
    return f"{m}:{s:02d} /km"


def _active(total: float | None, bmr: float | None) -> int | None:
    if total is None or bmr is None:
        return None
    return round(total - bmr)


@mcp.tool()
def list_runs(limit: int = 5, start: int = 0) -> list[dict]:
    """Most recent runs: date, run type, distance, time, avg pace, avg/max HR, cadence,
    temperature. start offsets further back into history."""
    acts = garth.connectapi(
        "/activitylist-service/activities/search/activities",
        params={"start": start, "limit": limit, "activityType": "running"},
    )
    return [
        {
            "date": a.get("startTimeLocal"),
            "run_type": (a.get("activityType") or {}).get("typeKey"),
            "distance_km": round(a.get("distance", 0) / 1000, 2),
            "time_min": round(a.get("duration", 0) / 60, 1),
            "avg_pace": _pace(a.get("duration"), a.get("distance")),
            "avg_hr": a.get("averageHR"),
            "max_hr": a.get("maxHR"),
            "cadence_spm": a.get("averageRunningCadenceInStepsPerMinute"),
            "temp_c": a.get("minTemperature"),
        }
        for a in acts
    ]


@mcp.tool()
def list_strength(limit: int = 5, start: int = 0) -> list[dict]:
    """Most recent strength-training gym sessions: date, session name, duration, sets,
    reps, calories, avg/max HR. start offsets further back into history."""
    acts = garth.connectapi(
        "/activitylist-service/activities/search/activities",
        params={"start": start, "limit": limit * 3,
                "activityType": "fitness_equipment"},
    )
    gym = [
        a for a in acts
        if (a.get("activityType") or {}).get("typeKey") == "strength_training"
    ]
    return [
        {
            "date": a.get("startTimeLocal"),
            "name": a.get("activityName"),
            "time_min": round(a.get("duration", 0) / 60, 1),
            "sets": a.get("totalSets"),
            "reps": a.get("totalReps"),
            "calories": a.get("calories"),
            "active_kcal": _active(a.get("calories"), a.get("bmrCalories")),
            "avg_hr": a.get("averageHR"),
            "max_hr": a.get("maxHR"),
        }
        for a in gym[:limit]
    ]


@mcp.tool()
def daily_calories(days: int = 7, end: str | None = None) -> list[dict]:
    """Daily calories burned (total/active/BMR), steps, resting HR, most recent day first.
    days: how many days back to fetch. end: last day as YYYY-MM-DD, defaults to today."""
    out = []
    for s in garth.DailySummary.list(end, days):
        total, active = s.total_kilocalories, s.active_kilocalories
        out.append({
            "date": s.calendar_date.isoformat(),
            "total_kcal": total,
            "active_kcal": active,
            "bmr_kcal": None if total is None or active is None else total - active,
            "steps": s.total_steps,
            "resting_hr": s.resting_heart_rate,
        })
    return out


if __name__ == "__main__":
    mcp.run()
