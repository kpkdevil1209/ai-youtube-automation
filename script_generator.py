import json
import os
import google.generativeai as genai

# Gemini API Key configure karein (GitHub Secrets se uthayega ya environment variable se)
# Aap apni GEMINI_API_KEY ko bhi GitHub Secrets mein add kar sakte hain
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

def load_channels():
    with open("channels_config.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["channels"]

def generate_script_with_gemini(channel_name, niche, format_type):
    # Gemini model initialize karein
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    prompt = f"""
    You are an expert YouTube content creator and scriptwriter.
    Create a highly engaging and viral video script for a YouTube {format_type} channel.
    
    Channel Name: {channel_name}
    Niche / Topic Focus: {niche}
    Format: {format_type} (If 'short', keep it under 50 words, fast-paced, hook-driven. If 'long', make it detailed, engaging, and structured).
    
    Please provide the output strictly in the following JSON format without any extra text:
    {{
      "title": "Catchy YouTube video title here",
      "description": "Optimized YouTube description with hashtags",
      "script_text": "The exact voiceover script that will be read out."
    }}
    """
    
    response = model.generate_content(prompt)
    try:
        # Clean response and parse JSON
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3].strip()
        script_data = json.loads(text)
        return script_data
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        return None

def main():
    channels = load_channels()
    print(f"Total channels loaded: {len(channels)}")
    
    # Test ke tor par pehle channel ke liye script generate karte hain
    target_channel = channels[0] 
    print(f"Generating content for: {target_channel['name']} ({target_channel['format']})")
    
    script_data = generate_script_with_gemini(
        target_channel['name'], 
        target_channel['niche'], 
        target_channel['format']
    )
    
    if script_data:
        print("\n--- Generated Script ---")
        print(f"Title: {script_data['title']}")
        print(f"Description: {script_data['description']}")
        print(f"Script: {script_data['script_text']}")
        
        # Generated script ko file mein save kar lete hain taake agle step (TTS/Colab) mein use ho sake
        with open("current_script.json", "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False, indent=4)
        print("\nScript successfully saved to current_script.json!")

if __name__ == "__main__":
    main()
      
