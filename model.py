# list_claude_models.py
# Run this to see ALL currently available Claude models (November 2025+)
import os
import json
import requests
from dotenv import load_dotenv

# === Load API Key ===
load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not API_KEY:
    print("❌ ERROR: ANTHROPIC_API_KEY not found in .env file!")
    print("   Create a .env file with: ANTHROPIC_API_KEY=sk-ant-...")
    exit(1)

print(f"API Key loaded: {API_KEY[:10]}...{API_KEY[-4:]}")

# === Make Request ===
url = "https://api.anthropic.com/v1/models"
headers = {
    "x-api-key": API_KEY,
    "anthropic-version": "2023-06-01",
    "Content-Type": "application/json"
}

print("\nFetching available models from Anthropic API...\n")
try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    # === Save to file ===
    with open("available_models.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("Saved full response → available_models.json")

    # === Pretty Print Models ===
    models = data.get("data", [])
    if not models:
        print("No models returned. Check your API key or network.")
        exit(1)

    print("\n" + "="*60)
    print(" AVAILABLE CLAUDE MODELS (as of Nov 15, 2025)")
    print("="*60)

    recommended = None
    for model in models:
        model_id = model["id"]
        display_name = model.get("display_name", "Unknown")
        print(f"  {model_id}")
        print(f"     → {display_name}")

        # Auto-detect best for your use case
        if "sonnet-4.5" in model_id.lower() and "latest" not in model_id.lower():
            recommended = model_id

    print("="*60)

    # === Recommendation ===
    if recommended:
        print(f"\nRECOMMENDED FOR SocialSentry:")
        print(f"   MODEL = \"{recommended}\"")
        print(f"\n   Paste this into your app.py:")
        print(f'   MODEL = "{recommended}"')
    else:
        print("\nNo Sonnet 4.5 model found. Using fallback...")
        print('   MODEL = "claude-sonnet-4.5"  # Try this alias')

    print("\nDone! Check available_models.json for full details.")

except requests.exceptions.HTTPError as e:
    print(f"\nHTTP Error: {e}")
    if response.status_code == 401:
        print("   → Invalid API key!")
    elif response.status_code == 404:
        print("   → Endpoint not found. Check anthropic-version header.")
except Exception as e:
    print(f"\nUnexpected error: {e}")