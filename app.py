import os
import sqlite3
import json
import traceback 
from datetime import datetime
from flask import Flask, render_template, request, jsonify, g
from dotenv import load_dotenv
from openai import OpenAI

# Prefer class-based parser if available; fall back to module-level parse()
try:
    from workout_parser import WorkoutParser
    _PARSER_MODE = "class"
except Exception:  # pragma: no cover
    import workout_parser  # type: ignore
    WorkoutParser = None  # type: ignore
    _PARSER_MODE = "module"

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

def parse_intervals(text: str):
    """Parse workout text using the best available parser variant."""
    if WorkoutParser is not None:
        try:
            return WorkoutParser().parse_chatgpt_workout(text)
        except Exception:
            pass
    # Fallback to module-level parser if present
    try:
        return workout_parser.parse(text)  # type: ignore[name-defined]
    except Exception:
        return []

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
        intervals = parse_intervals(txt)
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
        intervals_json = json.dumps(intervals)
        db = get_db()
        cursor = db.cursor()
        cursor.execute("INSERT INTO workouts (description, intervals) VALUES (?, ?)", (description, intervals_json))
        db.commit()
        return jsonify(success=True, workout_id=cursor.lastrowid)
    except sqlite3.Error as e:
        return jsonify(success=False, error=f"Database error: {str(e)}"), 500
    except Exception as e:
        return jsonify(success=False, error=f"Unexpected error: {str(e)}"), 500

@app.route("/workouts")
def get_workouts():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, description, intervals FROM workouts ORDER BY id DESC")
    rows = cursor.fetchall()
    workouts = []
    for row in rows:
        workouts.append({
            "id": row["id"],
            "description": row["description"],
            "intervals": json.loads(row["intervals"])
        })
    return jsonify(workouts)

@app.route("/generate_workout", methods=["POST"])
def generate_workout():
    """Generate workout using OpenAI with robust error handling and safe fallback."""
    try:
        # Check API key
        api_key = os.environ.get("OPENAI_API_KEY")
        print(f"API Key present: {bool(api_key)}")  # debug log
        if not api_key:
            return jsonify(success=False, error="OpenAI API key not configured"), 500

        # Validate input
        body = request.get_json() or {}
        user_request = (body.get("request") or "").strip()
        if not user_request:
            return jsonify(success=False, error="Please describe the workout"), 400

        # Call OpenAI
        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a running coach. Generate a treadmill workout as plain text, one interval per line. "
                        "Use the exact format: `<minutes> min @ <speed> mph (<short label>)`. "
                        "Optionally include 'incline X' like `, incline 2`. Keep total duration ≤ 60 minutes."
                    ),
                },
                {"role": "user", "content": user_request},
            ],
            temperature=0.7,
            max_tokens=600,
        )

        workout_text = (completion.choices[0].message.content or "").strip()

        # Parse the generated workout using our parser wrapper
        intervals = []
        try:
            intervals = parse_intervals(workout_text)
        except Exception as parse_err:
            print(f"Parse error: {parse_err}")

        # Fallback if parsing failed
        if not intervals:
            intervals = [{
                "duration_min": 30,
                "speed_mph": 5.5,
                "incline": 0,
                "description": "Generated workout - manual parsing needed"
            }]

        total_minutes = sum(float(i.get("duration_min", 0) or 0) for i in intervals)
        name = f"AI Workout {int(total_minutes)}min"

        return jsonify(
            success=True,
            workout_text=workout_text,
            intervals=intervals,
            total_minutes=total_minutes,
            name=name
        )

    except Exception as e:
        # Ensure JSON error response (avoid HTML)
        print(f"Error in generate_workout: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(success=False, error=f"Generation failed: {str(e)}"), 500

@app.route("/saved_workouts")
def saved_workouts():
    """Return list of saved workouts"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id, description, intervals FROM workouts ORDER BY id DESC")
        rows = cursor.fetchall()
        
        workouts = []
        for row in rows:
            intervals_data = json.loads(row["intervals"])
            total_min = sum(float(i.get("duration_min", 0)) for i in intervals_data)
            
            workouts.append({
                "id": row["id"],
                "name": row["description"],
                "interval_count": len(intervals_data),
                "total_minutes": int(total_min),
                "method": "manual",  # or detect from description
                "created": "2024-01-01"  # You might want to add a created_at column
            })
        
        return jsonify(workouts)
    except Exception as e:
        print(f"Error in saved_workouts: {e}")
        return jsonify([])

@app.route("/load_workout/<int:workout_id>")
def load_workout(workout_id):
    """Load a specific workout by ID"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT description, intervals FROM workouts WHERE id = ?", (workout_id,))
        row = cursor.fetchone()
        
        if row:
            return jsonify({
                "success": True,
                "name": row["description"],
                "intervals": json.loads(row["intervals"])
            })
        else:
            return jsonify({"success": False, "error": "Workout not found"}), 404
            
    except Exception as e:
        print(f"Error in load_workout: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)