# SocialSentry backend - SQLite Persistence & HITL Integration
import os
import json
import time
import threading
import sqlite3
import pandas as pd
import requests
import re
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from anthropic import Anthropic

# === Load Environment ===
load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")

# Configuration
TWEET_CSV = os.path.join("data", "sample_tweets.csv")
DB_PATH = "socialsentry.db"
GEOCODE_CACHE = {}

# === Database Engine ===
def init_db():
    """Initializes the SQLite database with structured fields and HITL support."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Using individual columns allows for powerful SQL analytics and filtering
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tweet_id TEXT,
            username TEXT,
            created_at TEXT,
            tweet_text TEXT,
            
            -- AI Classifications
            threat_detected INTEGER, 
            category TEXT,
            severity INTEGER,
            summary TEXT,
            indicators TEXT, 
            
            -- Geospatial Data
            lat REAL,
            lng REAL,
            location_label TEXT,
            
            -- Human-in-the-Loop Workflow
            review_status TEXT DEFAULT 'pending', -- pending, verified, dismissed
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Intelligence Database Initialized")

def save_alert_to_db(alert_data):
    """Maps the analysis dictionary into structured SQL columns."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        meta = alert_data['meta']
        analysis = alert_data['analysis']
        loc = alert_data['location']
        
        # Store indicators as comma-separated for readability
        indicators_str = ", ".join(analysis.get('indicators', []))
        
        cursor.execute('''
            INSERT INTO alerts (
                tweet_id, username, created_at, tweet_text, 
                threat_detected, category, severity, summary, indicators, 
                lat, lng, location_label
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(meta['tweet_id']), meta['user'], meta['created_at'], alert_data['text'],
            1 if analysis.get('threat_detected') else 0,
            analysis.get('category', 'none'), analysis.get('severity', 1),
            analysis.get('summary', ''), indicators_str,
            loc['lat'], loc['lng'], loc['label']
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return False

def update_alert_status(alert_id, new_status):
    """Executes the Human-in-the-Loop status change in the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE alerts SET review_status = ? WHERE id = ?', (new_status, alert_id))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        print(f"❌ Status Update Failed: {e}")
        return False

# === Geocoding Logic ===
def geocode_location(location_str):
    if not location_str or location_str.strip() in ["", "Unknown"]:
        return None, None
    location_str = location_str.strip()
    if location_str in GEOCODE_CACHE: return GEOCODE_CACHE[location_str]
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": f"{location_str}, Kenya", "format": "json", "limit": 1}
        headers = {"User-Agent": "SocialSentry/1.1"}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        data = response.json()
        if data:
            lat, lng = float(data[0]["lat"]), float(data[0]["lon"])
            GEOCODE_CACHE[location_str] = (lat, lng)
            return lat, lng
        return None, None
    except: return None, None

# === AI Intelligence Setup ===
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = Anthropic(api_key=ANTHROPIC_API_KEY)
# FIXED: Stable model ID to prevent 404s
MODEL = "claude-sonnet-4-5-20250929"  

PROMPT = """
You are a national security AI classifier. Return ONLY a valid JSON object.
{{
  "threat_detected": true or false,
  "category": "terrorism" | "hate_speech" | "civil_unrest" | "misinformation" | "safety_report" | "none",
  "severity": 1-5,
  "summary": "short summary",
  "indicators": ["keyword1","keyword2"]
}}
Analyze Signal: \"\"\"{tweet}\"\"\"
"""

def analyze_tweet(text: str):
    try:
        response = client.messages.create(
            model=MODEL, max_tokens=300, temperature=0,
            messages=[{"role": "user", "content": PROMPT.format(tweet=text)}]
        )
        match = re.search(r"\{[\s\S]*\}", response.content[0].text)
        return json.loads(match.group(0)) if match else None
    except Exception as e:
        print(f"❌ AI Analysis Failure: {e}")
        return None

# === Live Stream Processor ===
def tweet_producer():
    print("\n=== Intelligence Pipeline Online ===\n")
    if not os.path.exists(TWEET_CSV): return
    df = pd.read_csv(TWEET_CSV)
    for _, row in df.iterrows():
        text = str(row.get("text", ""))
        location = row.get("location", "Unknown")
        analysis = analyze_tweet(text)
        lat, lng = geocode_location(location)
        if analysis and (analysis.get("threat_detected") or analysis.get("category") != "none"):
            save_alert_to_db({
                "meta": {"tweet_id": row.get("tweet_id"), "user": row.get("user"), "created_at": row.get("created_at")},
                "text": text, "analysis": analysis,
                "location": {"label": location, "lat": lat, "lng": lng}
            })
        time.sleep(4)

# === Web Endpoints ===
@app.route("/")
def index(): return render_template("dashboard.html")

@app.route("/alerts")
def get_alerts():
    """Returns alerts reconstructed from SQL rows."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 50')
        rows = cursor.fetchall()
        alerts = []
        for row in rows:
            alerts.append({
                "id": row['id'],
                "meta": {"tweet_id": row['tweet_id'], "user": row['username'], "created_at": row['created_at']},
                "text": row['tweet_text'],
                "analysis": {
                    "threat_detected": bool(row['threat_detected']),
                    "category": row['category'],
                    "severity": row['severity'],
                    "summary": row['summary'],
                    "indicators": row['indicators'].split(", ") if row['indicators'] else []
                },
                "location": {"label": row['location_label'], "lat": row['lat'], "lng": row['lng']},
                "status": row['review_status'],
                "timestamp": row['timestamp']
            })
        conn.close()
        return jsonify(alerts)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/update_status", methods=["POST"])
def update_status():
    """Processes Human-in-the-Loop verification actions."""
    data = request.json
    if update_alert_status(data.get("alert_id"), data.get("status")):
        return jsonify({"success": True})
    return jsonify({"success": False}), 500

@app.route("/analyze", methods=["POST"])
def analyze_text():
    text = request.json.get("text", "")
    return jsonify({"analysis": analyze_tweet(text)})

if __name__ == "__main__":
    init_db()
    threading.Thread(target=tweet_producer, daemon=True).start()
    app.run(debug=True, port=5000)