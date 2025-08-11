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
        
        # Enhanced workouts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                intervals TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                workout_type TEXT DEFAULT 'manual',
                difficulty_rating INTEGER DEFAULT 3,
                estimated_calories INTEGER,
                tags TEXT
            )
        ''')
        
        # New workout sessions table for tracking actual performance
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workout_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_id INTEGER,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                total_duration_minutes REAL,
                completed_intervals INTEGER DEFAULT 0,
                skipped_intervals INTEGER DEFAULT 0,
                notes TEXT,
                performance_rating INTEGER,
                actual_calories INTEGER,
                whoop_screenshot_path TEXT,
                FOREIGN KEY (workout_id) REFERENCES workouts (id)
            )
        ''')
        
        # Performance metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                interval_index INTEGER,
                planned_duration_min INTEGER,
                actual_duration_min REAL,
                planned_speed_mph REAL,
                actual_speed_mph REAL,
                planned_incline REAL,
                actual_incline REAL,
                heart_rate_avg INTEGER,
                heart_rate_max INTEGER,
                perceived_exertion INTEGER,
                FOREIGN KEY (session_id) REFERENCES workout_sessions (id)
            )
        ''')
        
        # Progress tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS progress_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE DEFAULT CURRENT_DATE,
                total_workouts INTEGER DEFAULT 0,
                total_duration_minutes REAL DEFAULT 0,
                total_distance_miles REAL DEFAULT 0,
                avg_heart_rate INTEGER,
                recovery_score REAL,
                sleep_score REAL,
                stress_score REAL,
                notes TEXT
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

@app.route("/start_session", methods=["POST"])
def start_session():
    """Start a new workout session"""
    try:
        data = request.get_json() or {}
        workout_id = data.get("workout_id")
        
        if not workout_id:
            return jsonify(success=False, error="Workout ID required"), 400
            
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO workout_sessions (workout_id) VALUES (?)",
            (workout_id,)
        )
        session_id = cursor.lastrowid
        db.commit()
        
        return jsonify(success=True, session_id=session_id)
        
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/complete_session", methods=["POST"])
def complete_session():
    """Complete a workout session with performance data"""
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id")
        performance_data = data.get("performance", {})
        
        if not session_id:
            return jsonify(success=False, error="Session ID required"), 400
            
        db = get_db()
        cursor = db.cursor()
        
        # Update session completion
        cursor.execute("""
            UPDATE workout_sessions 
            SET completed_at = CURRENT_TIMESTAMP,
                total_duration_minutes = ?,
                completed_intervals = ?,
                skipped_intervals = ?,
                notes = ?,
                performance_rating = ?,
                actual_calories = ?
            WHERE id = ?
        """, (
            performance_data.get("total_duration_minutes", 0),
            performance_data.get("completed_intervals", 0),
            performance_data.get("skipped_intervals", 0),
            performance_data.get("notes", ""),
            performance_data.get("performance_rating"),
            performance_data.get("actual_calories")
        ))
        
        # Save interval performance metrics
        interval_metrics = performance_data.get("interval_metrics", [])
        for metric in interval_metrics:
            cursor.execute("""
                INSERT INTO performance_metrics 
                (session_id, interval_index, planned_duration_min, actual_duration_min,
                 planned_speed_mph, actual_speed_mph, planned_incline, actual_incline,
                 heart_rate_avg, heart_rate_max, perceived_exertion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                metric.get("interval_index"),
                metric.get("planned_duration_min"),
                metric.get("actual_duration_min"),
                metric.get("planned_speed_mph"),
                metric.get("actual_speed_mph"),
                metric.get("planned_incline"),
                metric.get("actual_incline"),
                metric.get("heart_rate_avg"),
                metric.get("heart_rate_max"),
                metric.get("perceived_exertion")
            ))
        
        db.commit()
        return jsonify(success=True)
        
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/upload_whoop_screenshot", methods=["POST"])
def upload_whoop_screenshot():
    """Upload WHOOP screenshot for a session"""
    try:
        session_id = request.form.get("session_id")
        if not session_id:
            return jsonify(success=False, error="Session ID required"), 400
            
        if "screenshot" not in request.files:
            return jsonify(success=False, error="No screenshot uploaded"), 400
            
        file = request.files["screenshot"]
        if file.filename == "":
            return jsonify(success=False, error="No file selected"), 400
            
        # Save file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"whoop_screenshot_{session_id}_{timestamp}.png"
        filepath = os.path.join("static", "whoop_screenshots", filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)
        
        # Update database
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "UPDATE workout_sessions SET whoop_screenshot_path = ? WHERE id = ?",
            (f"/static/whoop_screenshots/{filename}", session_id)
        )
        db.commit()
        
        return jsonify(success=True, filepath=f"/static/whoop_screenshots/{filename}")
        
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/progress_report")
def get_progress_report():
    """Generate progress report for WHOOP integration"""
    try:
        days = int(request.args.get("days", 30))
        
        db = get_db()
        cursor = db.cursor()
        
        # Get workout statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_workouts,
                SUM(total_duration_minutes) as total_duration,
                AVG(performance_rating) as avg_performance,
                COUNT(DISTINCT DATE(started_at)) as active_days
            FROM workout_sessions 
            WHERE started_at >= DATE('now', '-{} days')
        """.format(days))
        
        stats = cursor.fetchone()
        
        # Get recent sessions
        cursor.execute("""
            SELECT 
                ws.id,
                w.description,
                ws.started_at,
                ws.total_duration_minutes,
                ws.performance_rating,
                ws.whoop_screenshot_path
            FROM workout_sessions ws
            JOIN workouts w ON ws.workout_id = w.id
            WHERE ws.started_at >= DATE('now', '-{} days')
            ORDER BY ws.started_at DESC
        """.format(days))
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                "id": row["id"],
                "description": row["description"],
                "started_at": row["started_at"],
                "duration_minutes": row["total_duration_minutes"],
                "performance_rating": row["performance_rating"],
                "whoop_screenshot": row["whoop_screenshot_path"]
            })
        
        return jsonify({
            "success": True,
            "period_days": days,
            "statistics": {
                "total_workouts": stats["total_workouts"] or 0,
                "total_duration_minutes": stats["total_duration"] or 0,
                "avg_performance_rating": stats["avg_performance"] or 0,
                "active_days": stats["active_days"] or 0
            },
            "recent_sessions": sessions
        })
        
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/generate_whoop_summary", methods=["POST"])
def generate_whoop_summary():
    """Generate AI summary for WHOOP integration"""
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id")
        
        if not session_id:
            return jsonify(success=False, error="Session ID required"), 400
            
        # Get session data
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT 
                ws.*,
                w.description,
                w.intervals
            FROM workout_sessions ws
            JOIN workouts w ON ws.workout_id = w.id
            WHERE ws.id = ?
        """, (session_id,))
        
        session = cursor.fetchone()
        if not session:
            return jsonify(success=False, error="Session not found"), 404
            
        # Get performance metrics
        cursor.execute("""
            SELECT * FROM performance_metrics 
            WHERE session_id = ? 
            ORDER BY interval_index
        """, (session_id,))
        
        metrics = cursor.fetchall()
        
        # Generate AI summary
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return jsonify(success=False, error="OpenAI API key not configured"), 500
            
        client = OpenAI(api_key=api_key)
        
        summary_prompt = f"""
        Generate a concise workout summary for WHOOP integration based on this treadmill session:
        
        Workout: {session['description']}
        Duration: {session['total_duration_minutes']} minutes
        Completed intervals: {session['completed_intervals']}
        Performance rating: {session['performance_rating']}/10
        Notes: {session['notes'] or 'None'}
        
        Performance metrics: {len(metrics)} intervals tracked
        
        Please provide:
        1. Brief workout summary (2-3 sentences)
        2. Key performance insights
        3. Recommendations for next session
        4. Recovery suggestions
        
        Format as JSON with keys: summary, insights, recommendations, recovery
        """
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.7,
            max_tokens=300
        )
        
        summary_text = completion.choices[0].message.content or ""
        
        return jsonify({
            "success": True,
            "summary": summary_text,
            "session_data": {
                "id": session["id"],
                "description": session["description"],
                "duration": session["total_duration_minutes"],
                "performance_rating": session["performance_rating"]
            }
        })
        
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)