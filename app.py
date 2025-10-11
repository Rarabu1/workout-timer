import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, g
from dotenv import load_dotenv
from openai import OpenAI

# Import workout parser
try:
    from workout_parser import WorkoutParser
    parser = WorkoutParser()
except ImportError:
    parser = None

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')
DATABASE = 'workouts.db'

# ==================== DATABASE ====================

def get_db():
    """Get database connection"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Close database connection"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database with simple schema"""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Simple workouts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                intervals TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        db.commit()

def parse_intervals(text: str):
    """Parse workout text into intervals"""
    if parser:
        return parser.parse_chatgpt_workout(text)
    return []

# ==================== ROUTES ====================

@app.route("/")
def index():
    """Main page"""
    return render_template("index.html")

@app.route("/static/manifest.json")
def manifest():
    """PWA manifest"""
    return app.send_static_file("manifest.json")

@app.route("/parse", methods=["POST"])
def parse():
    """Parse workout text into intervals"""
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
    """Save a workout to the database"""
    data = request.get_json() or {}
    description = (data.get("description") or "").strip()
    intervals = data.get("intervals")
    
    if not description or not intervals:
        return jsonify(success=False, error="Description and intervals required"), 400
    
    try:
        intervals_json = json.dumps(intervals)
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO workouts (description, intervals) VALUES (?, ?)",
            (description, intervals_json)
        )
        db.commit()
        return jsonify(success=True, workout_id=cursor.lastrowid)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/workouts")
def get_workouts():
    """Get all saved workouts"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, description, intervals, created_at FROM workouts ORDER BY created_at DESC")
    rows = cursor.fetchall()
    
    workouts = []
    for row in rows:
        workouts.append({
            "id": row["id"],
            "description": row["description"],
            "intervals": json.loads(row["intervals"]),
            "created_at": row["created_at"]
        })
    return jsonify(workouts)

@app.route("/load_workout/<int:workout_id>")
def load_workout(workout_id):
    """Load a specific workout"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, description, intervals FROM workouts WHERE id = ?", (workout_id,))
    row = cursor.fetchone()
    
    if not row:
        return jsonify(success=False, error="Workout not found"), 404
    
    return jsonify(
        success=True,
        workout={
            "id": row["id"],
            "description": row["description"],
            "intervals": json.loads(row["intervals"])
        }
    )

@app.route("/generate_workout", methods=["POST"])
def generate_workout():
    """Generate a workout using OpenAI"""
    data = request.get_json() or {}
    prompt = (data.get("prompt") or "").strip()
    
    if not prompt:
        return jsonify(success=False, error="Prompt required"), 400
    
    # Check if OpenAI API key is available
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return jsonify(
            success=False,
            error="OpenAI API key not configured"
        ), 500
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Build system message
        system_message = """You are a treadmill running coach. Create structured workout plans.

Return workouts in this format:

**Warm-Up – 5 minutes**
* 5 min @ 4.0 mph (easy pace)

**Main Set – 20 minutes**
* 3 min @ 6.5 mph (tempo)
* 2 min @ 5.0 mph (recovery)
* 3 min @ 7.0 mph (hard)
* 2 min @ 5.0 mph (recovery)

**Cool-Down – 5 minutes**
* 5 min @ 4.0 mph (easy)

Use realistic treadmill speeds (4.0-9.0 mph). Include warm-up and cool-down."""
        
        # Call OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        workout_text = response.choices[0].message.content
        
        # Parse the generated workout
        intervals = parse_intervals(workout_text)
        
        return jsonify(
            success=True,
            workout_text=workout_text,
            intervals=intervals
        )
        
    except Exception as e:
        return jsonify(
            success=False,
            error=f"Error generating workout: {str(e)}"
        ), 500

# ==================== MAIN ====================

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)

# Ensure database is initialized
with app.app_context():
    init_db()
