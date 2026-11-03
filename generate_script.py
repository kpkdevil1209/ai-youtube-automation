import json, os, re, sys
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("\n[ERROR] GEMINI_API_KEY GitHub Secret mein nahi mili!")
    print("👉 Repo Settings > Secrets and variables > Actions mein jakar 'GEMINI_API_KEY' add karein.")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)

# Agar channels_config.json na ho toh default auto-create karein
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
    print("Default channels_config.json automatically created!")

channels = json.load(open(config_file, "r", encoding="utf-8"))["channels"]
target = channels[0]
print(f"Generating Script for Channel: {target['name']} ({target['format']})")

model = genai.GenerativeModel(
    "gemini-1.5-flash",
    generation_config={"response_mime_type": "application/json"}
)

prompt = f"""
You are an expert viral YouTube scriptwriter.
Create an engaging video script for:
Channel: {target['name']}
Niche: {target['niche']}
Format: {target['format']} (If 'short', keep voiceover under 50 words with a strong 3-second hook).

Output strictly in this JSON structure:
{{
  "title": "Viral Catchy Title (max 70 chars)",
  "description": "Engaging description with #Shorts #AI #Tech hashtags",
  "script_text": "The full spoken voiceover narration script without speaker names."
}}
"""

response = model.generate_content(prompt)
clean_text = re.sub(r"^```(?:json)?\s*", "", response.text.strip(), flags=re.MULTILINE)
clean_text = re.sub(r"\s*```$", "", clean_text.strip(), flags=re.MULTILINE)
script_data = json.loads(clean_text)

with open("current_script.json", "w", encoding="utf-8") as f:
    json.dump(script_data, f, ensure_ascii=False, indent=4)

print("\n🎉 [SUCCESS] Script generated and saved to current_script.json!")
print("Title:", script_data.get("title"))
