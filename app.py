import os
import sqlite3
import json
import logging
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, g
from dotenv import load_dotenv
from openai import OpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import workout parser
try:
    from workout_parser import WorkoutParser
    parser = WorkoutParser()
except ImportError:
    parser = None
    logger.warning("WorkoutParser not available")

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')
DATABASE = 'workouts.db'

# Configuration
MAX_DESCRIPTION_LENGTH = 200
MAX_INTERVALS = 50
MAX_PROMPT_LENGTH = 500

# ==================== VALIDATION ====================

def validate_workout_data(data):
    """Validate workout data structure"""
    if not isinstance(data, dict):
        return False, "Invalid data format"
    
    description = data.get('description', '').strip()
    intervals = data.get('intervals')
    
    if not description:
        return False, "Description is required"
    
    if len(description) > MAX_DESCRIPTION_LENGTH:
        return False, f"Description too long (max {MAX_DESCRIPTION_LENGTH} characters)"
    
    if not intervals or not isinstance(intervals, list):
        return False, "Intervals must be a non-empty list"
    
    if len(intervals) > MAX_INTERVALS:
        return False, f"Too many intervals (max {MAX_INTERVALS})"
    
    # Validate each interval
    for i, interval in enumerate(intervals):
        if not isinstance(interval, dict):
            return False, f"Interval {i} has invalid format"
        
        if 'duration_min' not in interval or 'speed_mph' not in interval:
            return False, f"Interval {i} missing required fields"
        
        try:
            duration = float(interval['duration_min'])
            speed = float(interval['speed_mph'])
            
            if duration <= 0 or duration > 120:
                return False, f"Interval {i} duration out of range (0-120 min)"
            
            if speed < 0 or speed > 15:
                return False, f"Interval {i} speed out of range (0-15 mph)"
        except (ValueError, TypeError):
            return False, f"Interval {i} has invalid numeric values"
    
    return True, None

def require_json(f):
    """Decorator to require JSON content type"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify(success=False, error="Content-Type must be application/json"), 400
        return f(*args, **kwargs)
    return decorated_function

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
        
        # Add index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_created_at 
            ON workouts(created_at DESC)
        ''')
        
        db.commit()
        logger.info("Database initialized successfully")

def parse_intervals(text: str):
    """Parse workout text into intervals"""
    if parser:
        return parser.parse_chatgpt_workout(text)
    return []

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify(success=False, error="Resource not found"), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal error: {error}")
    return jsonify(success=False, error="Internal server error"), 500

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
@require_json
def parse():
    """Parse workout text into intervals"""
    data = request.get_json()
    txt = (data.get("text") or "").strip()
    
    if not txt:
        return jsonify(success=False, error="No text provided"), 400
    
    if len(txt) > 5000:
        return jsonify(success=False, error="Text too long (max 5000 characters)"), 400
    
    try:
        intervals = parse_intervals(txt)
        
        if not intervals:
            return jsonify(
                success=False, 
                error="No intervals found. Check your format."
            ), 400
        
        return jsonify(success=True, intervals=intervals)
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return jsonify(success=False, error="Failed to parse workout"), 500

@app.route("/save_workout", methods=["POST"])
@require_json
def save_workout():
    """Save a workout to the database"""
    data = request.get_json()
    
    # Validate input
    is_valid, error_msg = validate_workout_data(data)
    if not is_valid:
        return jsonify(success=False, error=error_msg), 400
    
    description = data['description'].strip()
    intervals = data['intervals']
    
    try:
        intervals_json = json.dumps(intervals)
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO workouts (description, intervals) VALUES (?, ?)",
            (description, intervals_json)
        )
        db.commit()
        
        workout_id = cursor.lastrowid
        logger.info(f"Saved workout {workout_id}: {description}")
        
        return jsonify(success=True, workout_id=workout_id)
    except sqlite3.Error as e:
        logger.error(f"Database error saving workout: {e}")
        return jsonify(success=False, error="Database error"), 500
    except Exception as e:
        logger.error(f"Unexpected error saving workout: {e}")
        return jsonify(success=False, error="Failed to save workout"), 500

@app.route("/workouts")
def get_workouts():
    """Get all saved workouts"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT id, description, intervals, created_at "
            "FROM workouts ORDER BY created_at DESC LIMIT 100"
        )
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
    except Exception as e:
        logger.error(f"Error fetching workouts: {e}")
        return jsonify(success=False, error="Failed to fetch workouts"), 500

@app.route("/load_workout/<int:workout_id>")
def load_workout(workout_id):
    """Load a specific workout"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT id, description, intervals FROM workouts WHERE id = ?", 
            (workout_id,)
        )
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
    except Exception as e:
        logger.error(f"Error loading workout {workout_id}: {e}")
        return jsonify(success=False, error="Failed to load workout"), 500

@app.route("/generate_workout", methods=["POST"])
@require_json
def generate_workout():
    """Generate a workout using OpenAI"""
    data = request.get_json()
    prompt = (data.get("prompt") or "").strip()
    
    if not prompt:
        return jsonify(success=False, error="Prompt required"), 400
    
    if len(prompt) > MAX_PROMPT_LENGTH:
        return jsonify(
            success=False, 
            error=f"Prompt too long (max {MAX_PROMPT_LENGTH} characters)"
        ), 400
    
    # Check if OpenAI API key is available
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OpenAI API key not configured")
        return jsonify(
            success=False,
            error="AI workout generation not available"
        ), 503
    
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
        
        # Call OpenAI with timeout
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000,
            timeout=30  # 30 second timeout
        )
        
        workout_text = response.choices[0].message.content
        
        # Parse the generated workout
        intervals = parse_intervals(workout_text)
        
        if not intervals:
            logger.warning("OpenAI generated unparseable workout")
            return jsonify(
                success=False,
                error="Generated workout could not be parsed"
            ), 500
        
        logger.info(f"Generated workout for prompt: {prompt[:50]}...")
        
        return jsonify(
            success=True,
            workout_text=workout_text,
            intervals=intervals
        )
        
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return jsonify(
            success=False,
            error="Failed to generate workout. Please try again."
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
