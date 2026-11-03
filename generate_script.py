import json, os, re, sys
import google.generativeai as genai

# 1. API Key Check
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("\n[ERROR] GEMINI_API_KEY GitHub Secret mein nahi mili!")
    print("👉 Repo Settings > Secrets and variables > Actions mein jakar GEMINI_API_KEY add karein.")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)

# 2. Channels Config Load ya Auto-create
config_file = "channels_config.json"
if not os.path.exists(config_file):
    default_cfg = {
        "channels": [
            {
                "name": "AI Tech Hub",
                "niche": "Mind-blowing Tech Facts and Future AI Innovations",
                "format": "short"
            }
        ]
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(default_cfg, f, indent=4)
    print("Default channels_config.json auto-created!")

with open(config_file, "r", encoding="utf-8") as f:
    channels = json.load(f).get("channels", [])

if not channels:
    print("\n[ERROR] channels_config.json mein koi channel nahi mila!")
    sys.exit(1)

# 3. History Load karein
history_file = "uploaded_topics.json"
past_topics = []
if os.path.exists(history_file):
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            past_topics = json.load(f).get("history", [])
    except Exception:
        past_topics = []

# Target channel details
target_channel = channels[0]
channel_name = target_channel.get("name", "YouTube Channel")
niche = target_channel.get("niche", "Technology")
format_type = target_channel.get("format") or target_channel.get("format_short") or "short"

print(f"Generating unique content for: {channel_name} ({format_type})")
print(f"Total topics in history so far: {len(past_topics)}")

# Aakhri 30 topics prompt mein pass karein taake token waste na hon
recent_topics = past_topics[-30:] if len(past_topics) > 30 else past_topics
avoid_topics_text = json.dumps(recent_topics, ensure_ascii=False) if recent_topics else "None (First video)"

# 4. Gemini AI Call (Guaranteed JSON Output)
model = genai.GenerativeModel(
    "gemini-1.5-flash",
    generation_config={"response_mime_type": "application/json"}
)

prompt = f"""
You are an expert YouTube content creator and viral scriptwriter.
Create a highly engaging, unique, and viral video script for a YouTube {format_type} channel.

Channel Name: {channel_name}
Niche / Topic Focus: {niche}
Format: {format_type} (If 'short', voiceover strictly 40-50 words, fast hook in first 3 seconds. If 'long', detailed and engaging).

CRITICAL RULES:
1. Do NOT repeat or rephrase any of the following already covered topics:
{avoid_topics_text}
2. Pick a completely fresh, exciting, trending, and unique new topic in this niche.

Output strictly in this JSON format:
{{
  "title": "Viral Catchy Title (max 70 chars)",
  "description": "Optimized description with #Shorts #AI #Tech hashtags",
  "script_text": "The full voiceover narration script without speaker names."
}}
"""

response = model.generate_content(prompt)
clean_text = re.sub(r"^```(?:json)?\s*", "", response.text.strip(), flags=re.MULTILINE)
clean_text = re.sub(r"\s*```$", "", clean_text.strip(), flags=re.MULTILINE)
script_data = json.loads(clean_text)

new_title = script_data.get("title", "").strip()
print(f"\n--- Generated New Script ---")
print(f"Title: {new_title}")
print(f"Description: {script_data.get('description')}")
print(f"Script: {script_data.get('script_text')}")

# Current script save karein (Audio/Video creation ke liye)
with open("current_script.json", "w", encoding="utf-8") as f:
    json.dump(script_data, f, ensure_ascii=False, indent=4)

# 5. History mein save karein
if new_title and new_title not in past_topics:
    past_topics.append(new_title)
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump({"history": past_topics}, f, ensure_ascii=False, indent=4)
    print(f"\n✓ '{new_title}' successfully added to history ({history_file})!")

print("\n🎉 [SUCCESS] Script generated and history updated!")
