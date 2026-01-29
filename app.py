# SocialSentry backend
import os
import json
import time
import threading
import pandas as pd
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from anthropic import Anthropic

#  Load env
load_dotenv()


app = Flask(__name__, template_folder="templates", static_folder="static")

TWEET_CSV = os.path.join("data", "sample_tweets.csv")
ALERTS = []

# Import libraries
import requests
from urllib.parse import quote

# Geocode Cache
GEOCODE_CACHE = {}

#get location fuction
def geocode_location(location_str):
    if not location_str or location_str.strip() in ["", "Unknown"]:
        return None, None

    location_str = location_str.strip()
    if location_str in GEOCODE_CACHE:
        return GEOCODE_CACHE[location_str]

    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": f"{location_str}, Kenya",
            "format": "json",
            "limit": 1
        }
        headers = {"User-Agent": "SocialSentry/1.0 (hackathon)"}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        data = response.json()

        if data:
            lat = float(data[0]["lat"])
            lng = float(data[0]["lon"])
            GEOCODE_CACHE[location_str] = (lat, lng)
            return lat, lng
        else:
            GEOCODE_CACHE[location_str] = (None, None)
            return None, None
    except Exception as e:
        print(f"Geocode failed for '{location_str}': {e}")
        GEOCODE_CACHE[location_str] = (None, None)
        return None, None

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.strip() == "":
    raise ValueError("❌ ANTHROPIC_API_KEY is missing or empty in .env file!")

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Initialize anthropic Model name 
MODEL = "claude-sonnet-4-5-20250929"   

#print the model to confirm its the model you are using
print(f"✅ Using Anthropic model: {MODEL}")


#  Prompt Template for the national security classifier 
PROMPT = """
You are a national security AI classifier.

You MUST return ONLY a single valid JSON object.
No markdown. No code blocks. No commentary.

STRICT OUTPUT:
{{
  "threat_detected": true or false,
  "category": "terrorism" | "hate_speech" | "civil_unrest" | "misinformation" | "safety_report" | "none",
  "severity": 1-5,
  "summary": "short summary",
  "indicators": ["keyword1","keyword2"]
}}

Analyze this tweet:
\"\"\"{tweet}\"\"\" 

Return ONLY the JSON.
"""



# Analysis Function
def analyze_tweet(text: str):
    print("\n============================")
    print("Analyzing Tweet:")
    print(text)
    print("============================")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=300,
            temperature=0,
            messages=[{"role": "user", "content": PROMPT.format(tweet=text)}]
        )

        print("\n--- RAW CLAUDE RESPONSE ---")
        print(response)

        # Extract text content
        raw = response.content[0].text
        print("\n--- RAW TEXT ---")
        print(raw)

        # Extract JSON only
        import re
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise ValueError("Claude did not return JSON")

        json_block = match.group(0)
        print("\n--- EXTRACTED JSON BLOCK ---")
        print(json_block)

        parsed = json.loads(json_block)

        print("\n--- PARSED JSON ---")
        print(parsed)

        return parsed

    except Exception as e:
        print("\n❌ ERROR DURING ANALYSIS:", e)

        return {
            "threat_detected": False,
            "category": "none",
            "severity": 1,
            "summary": f"Error: {e}",
            "indicators": []
        }


# Fuction to replicate a live  Tweet Stream 
def tweet_producer():
    print("\n=== Tweet Producer Running ===\n")

    if not os.path.exists(TWEET_CSV):
        print("CSV missing:", TWEET_CSV)
        return

    df = pd.read_csv(TWEET_CSV)

    for _, row in df.iterrows():
        text = str(row.get("text", ""))
        meta = {
            "tweet_id": int(row.get("tweet_id", 0)),
            "user": row.get("user", "unknown"),
            "created_at": row.get("created_at", ""),
            "location": row.get("location", "Unknown")
        }

        analysis = analyze_tweet(text)

        # === GEOCODE LOCATION ===
        location_str = meta["location"]
        lat, lng = geocode_location(location_str)

        alert = {
            "meta": meta,
            "text": text,
            "analysis": analysis,
            "location": {
                "label": location_str,
                "lat": lat,
                "lng": lng,
                "type": "profile"  # since it's from CSV
            }
        }

        # Store only high-threat alerts
        if analysis.get("threat_detected") or analysis.get("category") in [
            "terrorism", "hate_speech", "civil_unrest", "misinformation"
        ]:
            ALERTS.insert(0, alert)
            print("\nALERT ADDED:", alert)
        else:
            print("\nNo alert stored.")

        time.sleep(1)

# Flask routes
@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/alerts")
def get_alerts():
    return jsonify(ALERTS[:50])


@app.route("/analyze", methods=["POST"])
def analyze_text():
    text = request.json.get("text", "")
    result = analyze_tweet(text)
    return jsonify({"text": text, "analysis": result})


# RUN flask app
if __name__ == "__main__":
    t = threading.Thread(target=tweet_producer, daemon=True)
    t.start()
    app.run(debug=True, port=5000)






