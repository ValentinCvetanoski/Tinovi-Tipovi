from flask import Flask, jsonify
from flask_cors import CORS
import datetime
import requests
import os
import random
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
CORS(app)

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
SPORT = "upcoming"
REGION = "eu"

CATEGORIES = {
    "safe": (1.3, 1.8),
    "risky": (1.9, 3.5),
}

# === API HELPERS ===

def get_odds():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": REGION,
        "markets": "h2h,totals",
        "oddsFormat": "decimal"
    }
    r = requests.get(url, params=params, timeout=25)
    r.raise_for_status()
    return r.json()

def get_fixtures_today():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"date": today, "timezone": "Europe/Belgrade"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        r.raise_for_status()
        return r.json().get("response", [])
    except Exception:
        return []

def get_team_ids(team_name, fixtures):
    for f in fixtures:
        home = f["teams"]["home"]["name"].lower()
        away = f["teams"]["away"]["name"].lower()
        if team_name.lower() == home:
            return f["teams"]["home"]["id"], f["teams"]["away"]["id"], f["league"]["id"]
        if team_name.lower() == away:
            return f["teams"]["away"]["id"], f["teams"]["home"]["id"], f["league"]["id"]
    return None, None, None

def get_team_position(league_id, team_id):
    """Try to get league position; return 'N/A' if blocked or missing."""
    if not league_id or not team_id:
        return "N/A"
    url = "https://v3.football.api-sports.io/standings"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"league": league_id, "season": datetime.datetime.now().year}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
        if r.status_code != 200:
            return "N/A"
        data = r.json().get("response", [])
        for group in data:
            for team in group["league"]["standings"][0]:
                if team["team"]["id"] == team_id:
                    return team["rank"]
        return "N/A"
    except Exception:
        return "N/A"

# === MAIN LOGIC ===
def categorize_games():
    odds_data = get_odds()
    fixtures = get_fixtures_today()
    now = datetime.datetime.now(datetime.timezone.utc)
    seen = set()
    results = {"safe": [], "risky": [], "overunder": []}
    all_tips = []

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

        best_h2h = {"label": None, "odds": 0}
        best_ou = {"label": None, "odds": 0}

        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                key = market.get("key")
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name", "")
                    odds = float(outcome.get("price", 0))
                    if odds <= 0:
                        continue
                    if key == "h2h" and name.lower() != "draw":
                        if 1.4 <= odds <= 4.0 and (best_h2h["odds"] == 0 or abs(2 - odds) < abs(2 - best_h2h["odds"])):
                            best_h2h = {"label": name, "odds": odds}
                    elif key == "totals" and "2.5" in name:
                        if 1.4 <= odds <= 4.0 and (best_ou["odds"] == 0 or abs(2 - odds) < abs(2 - best_ou["odds"])):
                            best_ou = {"label": name, "odds": odds}

        if not best_h2h["label"] and not best_ou["label"]:
            continue

        home_id, away_id, league_id = get_team_ids(home, fixtures)
        home_pos = get_team_position(league_id, home_id)
        away_pos = get_team_position(league_id, away_id)

        valid_tips = []
        if best_h2h["label"]:
            valid_tips.append({
                "match": f"{home} vs {away}",
                "kickoff": kickoff.strftime("%Y-%m-%d %H:%M"),
                "tip": best_h2h["label"],
                "odds": round(best_h2h["odds"], 2),
                "probability": f"{round(100 / best_h2h['odds'], 1)}%",
                "type": "Match Winner",
                "home_position": home_pos,
                "away_position": away_pos
            })
        if best_ou["label"]:
            valid_tips.append({
                "match": f"{home} vs {away}",
                "kickoff": kickoff.strftime("%Y-%m-%d %H:%M"),
                "tip": f"{best_ou['label']} goals",
                "odds": round(best_ou["odds"], 2),
                "probability": f"{round(100 / best_ou['odds'], 1)}%",
                "type": "Over/Under",
                "home_position": home_pos,
                "away_position": away_pos
            })

        all_tips.extend(valid_tips)

    # Shuffle for variety
    random.shuffle(all_tips)

    # Assign tips to categories: all h2h in safe/risky, all over/under in overunder
    for tip in all_tips:
        if tip["type"] == "Over/Under":
            results["overunder"].append(tip)
        else:
            for cat, (min_odds, max_odds) in CATEGORIES.items():
                if min_odds <= tip["odds"] <= max_odds and len(results[cat]) < 10:
                    results[cat].append(tip)
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
