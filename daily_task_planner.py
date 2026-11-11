"""
daily_task_planner.py (Version 5.0)
Autonomous Daily Task & Extended Duration Planner.
- Shorts Duration: Randomly 26.0s - 34.0s (Sweet Spot: ~29s).
- Long Video Duration: Randomly 14.0m - 16.5m (Every 3 Days).
- Community Poll: Every 2 Days.
"""

import json
import os
import random
from datetime import datetime, date
from niche_brain import scout_live_viral_trend

PROFILE_PATH = "channel_profile.json"
OUTPUT_MANIFEST = "today_tasks.json"

def calculate_days_difference(last_date_str: str) -> int:
    if not last_date_str:
        return 999
    try:
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
        return (date.today() - last_date).days
    except Exception:
        return 999

def get_randomized_short_duration() -> float:
    return round(random.uniform(26.0, 34.0), 1)

def get_randomized_long_duration() -> float:
    return round(random.uniform(14.0, 16.5), 2)

def plan_today_tasks():
    print("[*] Reading channel_profile.json...")
    profile = {}
    if os.path.exists(PROFILE_PATH):
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                profile = json.load(f)
        except Exception:
            pass

    today_str = date.today().strftime("%Y-%m-%d")
    history = profile.get("history", {})
    schedule = profile.get("schedule", {})

    days_since_long = calculate_days_difference(history.get("last_long_video_date"))
    days_since_comm = calculate_days_difference(history.get("last_community_post_date"))

    long_interval = schedule.get("long_video_interval_days", 3)
    comm_interval = schedule.get("community_post_interval_days", 2)

    do_short = True
    do_long = days_since_long >= long_interval
    do_comm = days_since_comm >= comm_interval

    trend = scout_live_viral_trend()
    short_duration_sec = get_randomized_short_duration()
    calculated_scenes_count = 7
    long_duration_mins = get_randomized_long_duration() if do_long else 0

    manifest = {
        "date": today_str,
        "channel_name": profile.get("channel_name", "DEVIL INSANITY"),
        "in_game_tag": profile.get("content_strategy", {}).get("in_game_name_tag", "DEVIL-999"),
        "tasks": {
            "daily_short": {
                "active": do_short,
                "pillar": trend["pillar"],
                "topic": trend["hook"],
                "featured_weapon": trend["weapon"],
                "headshot_dmg": trend["headshot_dmg"],
                "target_duration_sec": short_duration_sec,
                "calculated_scenes_count": calculated_scenes_count,
                "pacing": "extended_sandwich_splicing",
                "subtitles": ["ur", "en"]
            },
            "long_video": {
                "active": do_long,
                "days_since_last": days_since_long,
                "interval_required": long_interval,
                "target_duration_mins": long_duration_mins
            },
            "community_poll": {
                "active": do_comm,
                "days_since_last": days_since_comm,
                "interval_required": comm_interval
            }
        }
    }

    print("\n==========================================")
    print(f"[*] MASTER WORK PLAN 5.0: {today_str}")
    print(f" -> Topic: {trend['hook']}")
    print(f" -> Duration: {short_duration_sec}s (7 Multi-Stage Scenes)")
    print("==========================================\n")

    with open(OUTPUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    plan_today_tasks()
