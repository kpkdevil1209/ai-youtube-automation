"""
daily_task_planner.py
Autonomous Daily Task & Dynamic Timing Engine for DEVIL Gaming Empire.
Randomized Timing Logic:
- Shorts: Randomly chosen between 18.5s and 25.5s (Sweet-spot for 150%+ retention).
- Long Videos: Randomly chosen between 13.8m and 16.2m (~15 mins for high RPM & Watchtime).
"""

import json
import os
import random
from datetime import datetime, date
from niche_brain import pick_daily_short_topic, pick_long_video_topic

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
    return round(random.uniform(18.5, 25.5), 1)

def get_randomized_long_duration() -> float:
    return round(random.uniform(13.8, 16.2), 2)

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

    short_topic = pick_daily_short_topic()
    long_topic = pick_long_video_topic() if do_long else None

    short_duration_sec = get_randomized_short_duration()
    calculated_scenes_count = max(8, int(round(short_duration_sec / 1.8)))
    long_duration_mins = get_randomized_long_duration() if do_long else 0

    manifest = {
        "date": today_str,
        "channel_name": profile.get("channel_name", "DEVIL INSANITY"),
        "in_game_tag": profile.get("content_strategy", {}).get("in_game_name_tag", "DEVIL-999"),
        "tasks": {
            "daily_short": {
                "active": do_short,
                "topic_id": short_topic["id"],
                "topic": short_topic["name"],
                "suggested_title": short_topic["hook"],
                "featured_weapon": short_topic["weapon"],
                "pacing": "1.5s_to_2.0s_fast_cuts",
                "target_duration_sec": short_duration_sec,
                "calculated_scenes_count": calculated_scenes_count,
                "subtitles": ["ur", "en"]
            },
            "long_video": {
                "active": do_long,
                "days_since_last": days_since_long,
                "interval_required": long_interval,
                "topic": long_topic["title"] if do_long else None,
                "target_duration_mins": long_duration_mins,
                "structure": "3_act_documentary_with_midroll_anchors" if do_long else None
            },
            "community_poll": {
                "active": do_comm,
                "days_since_last": days_since_comm,
                "interval_required": comm_interval,
                "poll": {
                    "question": f"Free Fire mein {short_topic['weapon']} chalane ka best secret kya hai? 🔥",
                    "options": ["Rotation Drag", "Straight Up Drag", "Quick Scope", "Sit Up Headshot"]
                } if do_comm else None
            }
        }
    }

    print("\n==========================================")
    print(f"[*] MASTER WORK PLAN: {today_str}")
    print(f" -> Channel: {manifest['channel_name']}")
    print(f" -> Daily Short: [YES] {short_topic['hook']}")
    print(f"    * Randomized Duration: {short_duration_sec}s ({calculated_scenes_count} scenes)")
    print(f" -> Long Video (Every 3 Days): {'[YES] ' + long_topic['title'] if do_long else f'[WAIT - Day {days_since_long}/{long_interval}]'}")
    if do_long:
        print(f"    * Randomized Duration: {long_duration_mins} mins")
    print(f" -> Community Poll: {'[YES - POST POLL]' if do_comm else f'[WAIT - Day {days_since_comm}/{comm_interval}]'}")
    print("==========================================\n")

    with open(OUTPUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"[+] Dynamic manifest written to {OUTPUT_MANIFEST}!")

if __name__ == "__main__":
    plan_today_tasks()
