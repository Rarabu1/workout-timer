import os
import sqlite3
from flask import Flask, render_template, request, jsonify, g
from dotenv import load_dotenv
from openai import OpenAI
import workout_parser

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
DATABASE = 'workouts.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                intervals TEXT NOT NULL
            )
        ''')
        db.commit()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/static/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")

@app.route("/workout_suggestions")
def workout_suggestions():
    suggestions = [
        "30 minute endurance run with steady pacing",
        "20 minute VO2 max intervals (mph only)",
        "40 minute hill repeats (incline work)",
        "45 minute tempo with recoveries",
        "60 minute long run with surges",
        "30 minute fartlek: varied speeds"
    ]
    return jsonify(suggestions)

@app.route("/parse", methods=["POST"])
def parse():
    data = request.get_json() or {}
    txt = (data.get("text") or "").strip()
    if not txt:
        return jsonify(success=False, error="No text provided"), 400
    try:
        intervals = workout_parser.parse(txt)
        return jsonify(success=True, intervals=intervals)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/save_workout", methods=["POST"])
def save_workout():
    data = request.get_json() or {}
    description = (data.get("description") or "").strip()
    intervals = data.get("intervals")
    if not description or not intervals:
        return jsonify(success=False, error="Description and intervals required"), 400
    try:
        import json
        intervals_json = json.dumps(intervals)
        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO workouts (description, intervals) VALUES (?, ?)", (description, intervals_json))
        db.commit()
        return jsonify(success=True, workout_id=cursor.lastrowid)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/workouts")
def get_workouts():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, description, intervals FROM workouts ORDER BY id DESC")
    rows = cursor.fetchall()
    workouts = []
    import json
    for row in rows:
        workouts.append({
            "id": row["id"],
            "description": row["description"],
            "intervals": json.loads(row["intervals"])
        })
    return jsonify(workouts)

@app.route("/generate_workout", methods=["POST"])
def generate_workout():
    data = request.get_json() or {}
    req = (data.get("request") or "").strip()
    if not req:
        return jsonify(success=False, error="Please describe the workout"), 400

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return jsonify(success=False, error="OpenAI API key not configured"), 500

    prompt = f"""
    Create a treadmill workout for the following request:
    '{req}'
    Respond ONLY in JSON with this structure:
    {{
      "intervals": [
        {{
          "duration_min": <number>,
          "speed_mph": <number>,
          "incline": <number>,
          "description": "<short description>"
        }},
        ...
      ]
    }}
    Ensure at least 5 intervals and total time <= 60 minutes.
    """

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            temperature=0.7,
        )
        import json
        intervals = json.loads(response.output_text)["intervals"]
        workout_text = f"Generated plan for: {req}\n" + "\n".join(
            [f"- {it['duration_min']} min @ {it['speed_mph']} mph, incline {it['incline']} ({it['description']})"
             for it in intervals]
        )
        return jsonify(success=True, workout_text=workout_text, intervals=intervals)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/healthz")
def healthz():
    return "ok", 200

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)