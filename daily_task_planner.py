"""
daily_task_planner.py
Autonomous Daily Task & Decision Engine for DEVIL Gaming Empire.
Calculates today's exact tasks based on cadence:
- Daily 1 Short (Hyper-pacing 1.5s cuts)
- Long Video every 3 days (8-10 mins deep analysis)
- Community Post every 2 days (Interactive polls for algorithm engagement)
Outputs today_tasks.json for downstream engines.
"""

import json
import os
from datetime import datetime, date

PROFILE_PATH = "channel_profile.json"
OUTPUT_MANIFEST = "today_tasks.json"

VIRAL_DEVIL_ANGLES = [
    {
        "angle_id": "devil_hacker_exposed",
        "title_hook": "Is DEVIL Using Secret Config or Pure Reflexes?",
        "topic": "Hacker vs Pure Skill breakdown with 1.5s fast cuts",
        "weapon": "Desert Eagle"
    },
    {
        "angle_id": "devil_m1887_one_tap_secret",
        "title_hook": "99% Players Drag Joystick Wrong on M1887",
        "topic": "Secret high-DPI micro drag tutorial with red damage numbers",
        "weapon": "M1887"
    },
    {
        "angle_id": "devil_1v4_impossible_revenge",
        "title_hook": "When Squad Died and DEVIL Had 5 HP Left...",
        "topic": "Insane 1v4 revenge clutch against full grandmaster squad",
        "weapon": "MP40 & Shotgun"
    },
    {
        "angle_id": "devil_nostalgia_2018_vs_2026",
        "title_hook": "Did Garena Ruin Free Fire? 2018 vs 2026 Truth",
        "topic": "Nostalgia breakdown: Old training ground vs new mechanics",
        "weapon": "Old MP40"
    },
    {
        "angle_id": "devil_secret_trick_pro_hide",
        "title_hook": "The Banned Setting Every Free Fire Pro Hides",
        "topic": "Camera sensitivity setting for 100% headshot accuracy",
        "weapon": "Woodpecker"
    }
]

def calculate_days_difference(last_date_str: str) -> int:
    if not last_date_str:
        return 999  # First run: force execute
    try:
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
        today = date.today()
        return (today - last_date).days
    except Exception:
        return 999

def plan_today_tasks():
    print("[*] Reading channel_profile.json...")
    if not os.path.exists(PROFILE_PATH):
        raise FileNotFoundError(f"{PROFILE_PATH} file nahi mili!")

    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        profile = json.load(f)

    today_str = date.today().strftime("%Y-%m-%d")
    history = profile.get("history", {})
    schedule = profile.get("schedule", {})

    days_since_long = calculate_days_difference(history.get("last_long_video_date"))
    days_since_comm = calculate_days_difference(history.get("last_community_post_date"))

    long_interval = schedule.get("long_video_interval_days", 3)
    comm_interval = schedule.get("community_post_interval_days", 2)

    # Decisions
    do_short = True
    do_long = days_since_long >= long_interval
    do_comm = days_since_comm >= comm_interval

    # Select angle dynamically based on day of year
    day_of_year = date.today().timetuple().tm_yday
    selected_angle = VIRAL_DEVIL_ANGLES[day_of_year % len(VIRAL_DEVIL_ANGLES)]

    manifest = {
        "date": today_str,
        "channel_name": profile.get("channel_name", "DEVIL INSANITY"),
        "in_game_tag": profile["content_strategy"]["in_game_name_tag"],
        "tasks": {
            "daily_short": {
                "active": do_short,
                "angle": selected_angle["angle_id"],
                "suggested_title": selected_angle["title_hook"],
                "topic": selected_angle["topic"],
                "featured_weapon": selected_angle["weapon"],
                "pacing": profile["content_strategy"]["pacing"],
                "audio": {
                    "primary_voice": profile["audio_persona"]["primary_voice"],
                    "speech_rate": profile["audio_persona"]["speech_rate"],
                    "keyboard_sfx": profile["audio_persona"]["foley_keyboard_sfx"]
                },
                "subtitles": ["ur", "en"]
            },
            "long_video": {
                "active": do_long,
                "days_since_last": days_since_long,
                "interval_required": long_interval,
                "estimated_duration_mins": 8 if do_long else 0,
                "structure": "multi_chapter_in_depth_breakdown" if do_long else None
            },
            "community_poll": {
                "active": do_comm,
                "days_since_last": days_since_comm,
                "interval_required": comm_interval,
                "suggested_poll": {
                    "question": f"Konsa gun 1v4 clutch ke liye best hai? 💥",
                    "options": ["M1887 (Double Barrel)", "MP40 (Laser Spray)", "Desert Eagle (One Tap)", "Woodpecker"]
                } if do_comm else None
            }
        }
    }

    print("\n==========================================")
    print(f"[*] TODAY'S MASTER WORK PLAN: {today_str}")
    print(f" -> Channel: {profile.get('channel_name')}")
    print(f" -> Daily Short: [YES] {selected_angle['title_hook']}")
    print(f" -> Long Video (Every 3 Days): {'[YES - TIME TO RENDER]' if do_long else f'[WAIT - Day {days_since_long}/{long_interval}]'}")
    print(f" -> Community Poll (Every 2 Days): {'[YES - TIME TO POST]' if do_comm else f'[WAIT - Day {days_since_comm}/{comm_interval}]'}")
    print("==========================================\n")

    with open(OUTPUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"[+] Manifest successfully written to {OUTPUT_MANIFEST}!")

if __name__ == "__main__":
    plan_today_tasks()
