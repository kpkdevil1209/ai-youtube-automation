import os
import json
import random
import datetime
from niche_brain import scout_live_viral_trend, load_history, save_history_entry

def load_channel_profile():
    print("[*] Reading channel_profile.json...")
    default_profile = {
        "channel_name": "DEVIL INSANITY",
        "player_tag": "DEVIL-999",
        "primary_game": "Free Fire",
        "upload_time_pkt": "18:00",
        "long_video_interval_days": 3
    }
    if os.path.exists("channel_profile.json"):
        try:
            with open("channel_profile.json", "r", encoding="utf-8") as f:
                loaded = json.load(f)
                default_profile.update(loaded)
        except Exception as e:
            print(f"[!] Profile read notice: {e}. Using defaults.")
    return default_profile

def plan_today_tasks():
    profile = load_channel_profile()
    history = load_history()
    run_index = history.get("total_planned", 0) + 1

    # Shorts daily; Long Video (14m - 16.5m) every N days based on cadence
    interval = int(profile.get("long_video_interval_days", 3))
    is_long_day = (interval > 0 and run_index % interval == 0 and os.environ.get("FORCE_SHORT", "0") != "1")

    if is_long_day:
        format_type = "long"
        target_duration = round(random.uniform(840.0, 990.0), 1)  # 14m - 16.5m
        scene_count = 7
    else:
        format_type = "short"
        target_duration = round(random.uniform(26.5, 33.8), 1)   # Extended 26.5s - 33.8s viral Short
        scene_count = 7

    print(f"[*] Scouting Live Pillar & Trends for {profile.get('channel_name', 'DEVIL INSANITY')} ({format_type.upper()})...")
    trend = scout_live_viral_trend(format_type=format_type)

    plan = {
        "date": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
        "channel_name": profile.get("channel_name", "DEVIL INSANITY"),
        "player_tag": profile.get("player_tag", "DEVIL-999"),
        "format_type": format_type,
        "type": format_type,
        "target_duration": target_duration,
        "scene_count": scene_count,
        "pillar": trend.get("pillar", trend.get("pillar_name", "Weapon Mastery & Drag Physics")),
        "pillar_id": trend.get("pillar_id", "weapon_drag_physics"),
        "weapon": trend.get("weapon", "Desert Eagle"),
        "damage": trend.get("damage", "495"),
        "strategy": trend.get("strategy", trend.get("psychology_strategy", "01_Frame_Zero_Shock")),
        "search_query": trend.get("search_query", ""),
        "topic": trend.get("topic", ""),
        "source": trend.get("source", "live_youtube_reddit_scout")
    }

    # Write both standard filenames so all downstream scripts read cleanly
    for out_file in ["daily_plan.json", "task_plan.json"]:
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2)

    save_history_entry(pillar_id=plan["pillar_id"], increment_planned=True)

    print("==================================================")
    print(f"[+] DAILY TASK PLAN READY ({format_type.upper()})")
    print(f" -> Pillar: {plan['pillar']} ({plan['weapon']})")
    print(f" -> Strategy: {plan['strategy']}")
    print(f" -> Duration: {target_duration}s ({scene_count} Multi-Stage Scenes)")
    print("==================================================")
    return plan

if __name__ == "__main__":
    plan_today_tasks()
