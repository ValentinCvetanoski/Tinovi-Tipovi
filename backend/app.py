from flask import Flask, jsonify
import datetime
import requests
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# === CONFIG ===
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
SPORT = "upcoming"
REGION = "eu"

CATEGORIES = {
    "safe": (1.5, 1.8),
    "risky": (2.0, 3.0),
    "bomb": (3.01, 10.0)
}

def get_odds():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": REGION,
        "markets": "h2h",
        "oddsFormat": "decimal"
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()

def categorize_games():
    odds_data = get_odds()
    now = datetime.datetime.now(datetime.timezone.utc)
    seen = set()
    results = {"safe": [], "risky": [], "bomb": []}

    for event in odds_data:
        home = event.get("home_team")
        away = event.get("away_team")
        kickoff_iso = event.get("commence_time")
        if not home or not away or not kickoff_iso:
            continue
        kickoff = datetime.datetime.fromisoformat(kickoff_iso.replace("Z", "+00:00"))
        if kickoff <= now:
            continue

        match_key = f"{home}_{away}".lower()
        if match_key in seen:
            continue
        seen.add(match_key)

        best_tip, best_odds = None, 0
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    team = outcome["name"]
                    odds = float(outcome["price"])
                    if team.lower() == "draw":
                        continue
                    if odds > best_odds:
                        best_odds = odds
                        best_tip = team

        if not best_tip:
            continue

        for cat, (min_odds, max_odds) in CATEGORIES.items():
            if min_odds <= best_odds <= max_odds and len(results[cat]) < 10:
                results[cat].append({
                    "match": f"{home} vs {away}",
                    "kickoff": kickoff.strftime("%Y-%m-%d %H:%M"),
                    "tip": best_tip,
                    "odds": best_odds
                })
                break

    return results


@app.route("/tips")
def tips():
    try:
        data = categorize_games()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
