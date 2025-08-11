import os
import sqlite3
import json
import traceback 
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, g, redirect, url_for, session
from dotenv import load_dotenv
from openai import OpenAI
import math

# Optional WHOOP integration
try:
    import requests
    WHOOP_AVAILABLE = True
except ImportError:
    WHOOP_AVAILABLE = False
    print("Warning: requests module not available. WHOOP integration will be disabled.")

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
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')
DATABASE = 'workouts.db'

# WHOOP API Configuration
WHOOP_CLIENT_ID = os.getenv('WHOOP_CLIENT_ID')
WHOOP_CLIENT_SECRET = os.getenv('WHOOP_CLIENT_SECRET', '43d8c7a606083d063e422454bd593104fd66e1716b3900ff86d8752e87769db0')
WHOOP_REDIRECT_URI = os.getenv('WHOOP_REDIRECT_URI', 'https://workout-timer-dskb.onrender.com/whoop/callback')
WHOOP_API_BASE = 'https://api.prod.whoop.com'
WHOOP_API_BASE_V1 = 'https://api.prod.whoop.com/developer/v1'

# Debug: Print the actual values being used
print(f"=== WHOOP CONFIG DEBUG ===")
print(f"WHOOP_CLIENT_ID: {WHOOP_CLIENT_ID}")
print(f"WHOOP_CLIENT_SECRET: {WHOOP_CLIENT_SECRET}")
print(f"WHOOP_REDIRECT_URI: {WHOOP_REDIRECT_URI}")
print(f"Client Secret Length: {len(WHOOP_CLIENT_SECRET) if WHOOP_CLIENT_SECRET else 0}")
print(f"Expected Length: 64")
print(f"=== END WHOOP CONFIG DEBUG ===")

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

@app.route("/privacy")
def privacy_policy():
    return render_template("privacy_policy.html")

@app.route("/workout_suggestions")
def workout_suggestions():
    import random
    from datetime import datetime
    
    # Get query parameters for category and duration
    category = request.args.get('category', 'endurance')
    duration = request.args.get('duration', '30')
    
    # Category-specific suggestions that work with any duration
    category_suggestions = {
        'endurance': [
            "endurance run with steady pacing",
            "aerobic base building session",
            "progressive endurance workout",
            "long distance preparation",
            "steady state cardio session",
            "endurance with short surges",
            "aerobic threshold work",
            "endurance base maintenance"
        ],
        'speed': [
            "VO2 max intervals",
            "tempo + sprint intervals",
            "speed ladder workout",
            "interval training session",
            "anaerobic threshold work",
            "speed endurance training",
            "high-intensity intervals",
            "sprint and recovery cycles"
        ],
        'hills': [
            "hill repeats and inclines",
            "rolling hills endurance",
            "hill sprint intervals",
            "incline strength work",
            "mountain simulation",
            "hill climb training",
            "incline intervals",
            "elevation gain focus"
        ],
        'recovery': [
            "recovery run, low impact",
            "easy jog with strides",
            "walk-jog recovery mix",
            "active recovery session",
            "gentle cardio workout",
            "recovery-focused training",
            "easy pace maintenance",
            "recovery and mobility"
        ],
        'race': [
            "race-pace preparation",
            "tempo with race intervals",
            "marathon pace work",
            "5K race simulation",
            "10K tempo training",
            "half-marathon prep",
            "race-specific intervals",
            "competitive pace work"
        ],
        'fartlek': [
            "fartlek with varied speeds",
            "fartlek with random surges",
            "fartlek pyramid intervals",
            "speed play training",
            "fartlek with tempo sections",
            "mixed intensity fartlek",
            "fartlek with hill elements",
            "creative speed variations"
        ]
    }
    
    # Get suggestions for the current category
    base_suggestions = category_suggestions.get(category, category_suggestions['endurance'])
    
    # Add dynamic elements based on time
    current_hour = datetime.now().hour
    
    # Time-based intensity focus
    if 6 <= current_hour < 12:
        time_focus = "morning energy"
    elif 12 <= current_hour < 17:
        time_focus = "afternoon power"
    elif 17 <= current_hour < 21:
        time_focus = "evening strength"
    else:
        time_focus = "late night recovery"
    
    # Create enhanced suggestions
    enhanced_suggestions = []
    
    # Add base suggestions with time context
    for suggestion in base_suggestions:
        enhanced_suggestions.append(f"{duration} minute {suggestion}")
        enhanced_suggestions.append(f"{duration} minute {suggestion} ({time_focus} focus)")
    
    # Add random modifiers for variety
    modifiers = [
        "with breathing focus",
        "incorporating cadence work",
        "with mental toughness elements",
        "focusing on form",
        "with visualization techniques",
        "with progressive overload",
        "incorporating recovery periods",
        "with threshold work"
    ]
    
    # Add some suggestions with modifiers
    for suggestion in base_suggestions[:4]:  # Take first 4 for variety
        if random.random() < 0.4:  # 40% chance to add modifier
            modifier = random.choice(modifiers)
            enhanced_suggestions.append(f"{duration} minute {suggestion} {modifier}")
    
    # Shuffle and return unique suggestions
    all_suggestions = list(set(enhanced_suggestions))
    random.shuffle(all_suggestions)
    
    # Return 8-12 suggestions for variety
    return jsonify(all_suggestions[:random.randint(8, 12)])

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
    """Generate structured workout using athlete profile, constraints, and JSON schema."""
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

        # Call OpenAI with structured approach
        try:
            import random
            from datetime import datetime
            
            # Initialize OpenAI client with minimal parameters to avoid proxy issues
            try:
                client = OpenAI(api_key=api_key)
            except Exception as client_error:
                print(f"OpenAI client init error: {client_error}")
                # Try alternative initialization
                client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")
            
            # Athlete Profile (personalized for the user)
            athlete_profile = """
            ATHLETE PROFILE:
            - Device: Treadmill, speed in mph, show segment lengths
            - Pace anchors (0-1% incline):
              * 3.9 mph = brisk walk
              * 5.5 mph = very easy jog (recovery)
              * 6.1 mph = easy-moderate (steady)
              * 6.5 mph = challenging but doable
              * 7.0 mph = comfortable sprint
            - HR zones (WHOOP): Z2 140-152, Z3 153-164, Z4 165-177
            - Preferences: variety but structured; keep mostly Z3 with controlled Z4 surges; use mild inclines
            - Duration defaults: 30, 40, or 45 min
            """

            # Constraints & Difficulty Knobs
            constraints = """
            CONSTRAINTS & DIFFICULTY KNOBS:
            - Target intensity mix: 60-75% Z3, 10-20% Z4, remainder Z1-Z2
            - Speed bounds: steady 5.8-6.3 mph; surges 6.7-7.2 mph; cap max at 8.0 mph; recoveries 4.5-5.3 mph
            - Incline rules: recoveries 0-1%; steadies 0-1%; surges up to 3-4%; no hills on sprints if using 7.0+ mph
            - Work:recovery ratios: 1:1 for surges ≤60s, 2:1 for steadies; minimum interval length 1:00
            - Progression: if prior run felt ≤7/10 RPE or Z3 time <60%, add +0.1-0.2 mph to steady sections next time; otherwise keep speeds and add +1 min total time
            - Output language: mph only; print by segment length
            """

            # Strict JSON Schema
            json_schema = """
            STRICT OUTPUT SCHEMA - Return ONLY valid JSON that matches this format:
            {
              "title": "Workout title with duration and focus",
              "total_time_min": <total_duration>,
              "rules": {
                "speeds": {
                  "walk_brisk": 3.9,
                  "recovery": [4.5, 5.3],
                  "steady": [5.8, 6.3],
                  "surge": [6.7, 7.2],
                  "max_sprint": [7.3, 8.0]
                },
                "incline_pct": {
                  "recovery": [0, 1],
                  "steady": [0, 1],
                  "surge": [0, 4],
                  "max_sprint": [0, 2]
                },
                "zones": {
                  "Z2": [140, 152],
                  "Z3": [153, 164],
                  "Z4": [165, 177],
                  "Z5": [178, 999]
                },
                "time_in_zones_target_pct": {
                  "Z3": <60-75>,
                  "Z4": <10-20>,
                  "other": <remainder>
                },
                "segment_min_sec": 60,
                "max_segments_above_7mph": 3,
                "max_duration_above_7mph_sec": 60,
                "min_recovery_after_7mph_sec": 90
              },
              "segments": [
                {
                  "order": <segment_number>,
                  "duration_sec": <duration_in_seconds>,
                  "speed_mph": <speed>,
                  "incline_pct": <incline>,
                  "intent": "<warmup|steady|surge|recovery|max_sprint|cooldown>",
                  "target_hr_zone": "<Z2|Z3|Z4|Z5>"
                }
              ],
              "summary": {
                "target_mix": {"Z3_pct": <percentage>, "Z4_pct": <percentage>},
                "avg_speed_mph": <average_speed>
              },
              "printable": [
                "<duration> min @ <speed> mph — <description>"
              ]
            }
            """

            # Determine workout duration from user request
            duration = 30  # default
            if "30" in user_request or "thirty" in user_request.lower():
                duration = 30
            elif "40" in user_request or "forty" in user_request.lower():
                duration = 40
            elif "45" in user_request or "forty-five" in user_request.lower():
                duration = 45
            elif "20" in user_request or "twenty" in user_request.lower():
                duration = 20
            elif "60" in user_request or "sixty" in user_request.lower():
                duration = 60

            # Create structured prompt
            structured_prompt = f"""
            {athlete_profile}
            
            {constraints}
            
            {json_schema}
            
            USER REQUEST: {user_request}
            TARGET DURATION: {duration} minutes
            
            Generate a structured treadmill workout that matches the user's request and follows all constraints. 
            Return ONLY the JSON object, no additional text or explanations.
            """

            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert running coach who creates structured, personalized treadmill workouts. You always return valid JSON that matches the exact schema provided."
                    },
                    {"role": "user", "content": structured_prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
            )
            
            # Parse the JSON response
            response_text = (completion.choices[0].message.content or "").strip()
            
            # Try to extract JSON from the response
            import json
            import re
            
            # Look for JSON in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                workout_json = json.loads(json_match.group())
                
                # Convert JSON to printable format
                workout_text = "\n".join(workout_json.get("printable", []))
                
                # Store the structured data for future use
                workout_json["raw_request"] = user_request
                workout_json["generated_at"] = datetime.now().isoformat()
                
                # You could save this structured data to database here
                print(f"Generated structured workout: {workout_json.get('title', 'Unknown')}")
                
            else:
                # Fallback to plain text if JSON parsing fails
                workout_text = response_text
        except Exception as openai_error:
            print(f"OpenAI error: {openai_error}")
            # Enhanced fallback workouts with variety based on user request
            user_request_lower = user_request.lower()
            
            # Determine workout type from user request
            if any(word in user_request_lower for word in ['endurance', 'steady', 'aerobic', 'long']):
                workout_type = 'endurance'
            elif any(word in user_request_lower for word in ['speed', 'interval', 'tempo', 'sprint', 'fast']):
                workout_type = 'speed'
            elif any(word in user_request_lower for word in ['hill', 'incline', 'mountain']):
                workout_type = 'hills'
            elif any(word in user_request_lower for word in ['recovery', 'easy', 'low', 'gentle']):
                workout_type = 'recovery'
            elif any(word in user_request_lower for word in ['race', 'marathon', '5k', '10k']):
                workout_type = 'race'
            elif any(word in user_request_lower for word in ['fartlek', 'varied', 'mixed']):
                workout_type = 'fartlek'
            else:
                workout_type = 'endurance'  # default
            
            # Category-specific fallback workouts
            fallback_workouts = {
                'endurance': [
                    """5 min @ 4.0 mph (warm up)
20 min @ 5.5 mph (steady pace)
5 min @ 4.0 mph (cool down)""",
                    
                    """3 min @ 4.0 mph (easy warm up)
10 min @ 5.0 mph (build pace)
12 min @ 5.5 mph (steady state)
5 min @ 4.0 mph (cool down)""",
                    
                    """5 min @ 4.5 mph (warm up)
15 min @ 5.5 mph (endurance pace)
5 min @ 4.5 mph (cool down)"""
                ],
                'speed': [
                    """5 min @ 4.0 mph (warm up)
3 min @ 6.0 mph (speed interval)
2 min @ 4.5 mph (recovery)
3 min @ 6.5 mph (speed interval)
2 min @ 4.5 mph (recovery)
3 min @ 7.0 mph (speed interval)
2 min @ 4.5 mph (recovery)
5 min @ 4.0 mph (cool down)""",
                    
                    """5 min @ 4.5 mph (warm up)
5 min @ 6.0 mph (tempo)
3 min @ 4.5 mph (recovery)
5 min @ 6.5 mph (tempo)
3 min @ 4.5 mph (recovery)
4 min @ 4.0 mph (cool down)"""
                ],
                'hills': [
                    """5 min @ 4.0 mph (warm up)
5 min @ 5.0 mph, incline 2 (hill climb)
3 min @ 4.5 mph, incline 0 (recovery)
5 min @ 5.5 mph, incline 3 (hill climb)
3 min @ 4.5 mph, incline 0 (recovery)
4 min @ 4.0 mph (cool down)""",
                    
                    """3 min @ 4.0 mph (warm up)
8 min @ 5.0 mph, incline 2 (rolling hills)
4 min @ 4.5 mph, incline 0 (recovery)
8 min @ 5.5 mph, incline 3 (rolling hills)
2 min @ 4.0 mph (cool down)"""
                ],
                'recovery': [
                    """5 min @ 3.5 mph (easy warm up)
15 min @ 4.0 mph (recovery pace)
5 min @ 3.5 mph (cool down)""",
                    
                    """3 min @ 3.0 mph (walk warm up)
12 min @ 4.0 mph (easy jog)
5 min @ 3.5 mph (walk cool down)"""
                ],
                'race': [
                    """5 min @ 4.0 mph (warm up)
5 min @ 6.0 mph (race pace)
3 min @ 4.5 mph (recovery)
5 min @ 6.5 mph (race pace)
3 min @ 4.5 mph (recovery)
4 min @ 4.0 mph (cool down)""",
                    
                    """3 min @ 4.0 mph (warm up)
8 min @ 6.0 mph (tempo pace)
4 min @ 4.5 mph (recovery)
8 min @ 6.5 mph (tempo pace)
2 min @ 4.0 mph (cool down)"""
                ],
                'fartlek': [
                    """5 min @ 4.0 mph (warm up)
2 min @ 6.0 mph (speed)
3 min @ 4.5 mph (recovery)
2 min @ 6.5 mph (speed)
3 min @ 4.5 mph (recovery)
2 min @ 7.0 mph (speed)
3 min @ 4.5 mph (recovery)
5 min @ 4.0 mph (cool down)""",
                    
                    """3 min @ 4.0 mph (warm up)
3 min @ 5.5 mph (steady)
2 min @ 6.5 mph (surge)
3 min @ 5.0 mph (steady)
2 min @ 7.0 mph (surge)
3 min @ 5.0 mph (steady)
3 min @ 4.0 mph (cool down)"""
                ]
            }
            
            # Get appropriate fallback workout
            category_workouts = fallback_workouts.get(workout_type, fallback_workouts['endurance'])
            workout_text = random.choice(category_workouts)

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

@app.route("/generate_structured_workout", methods=["POST"])
def generate_structured_workout():
    """Generate structured workout with athlete profile, constraints, and JSON schema."""
    try:
        # Check API key
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return jsonify(success=False, error="OpenAI API key not configured"), 500

        # Validate input
        body = request.get_json() or {}
        user_request = (body.get("request") or "").strip()
        if not user_request:
            return jsonify(success=False, error="Please describe the workout"), 400

        # Get WHOOP data if available for personalized zones
        whoop_zones = body.get("whoop_zones", {
            "Z2": [140, 152],
            "Z3": [153, 164], 
            "Z4": [165, 177],
            "Z5": [178, 999]
        })

        try:
            import random
            from datetime import datetime
            
            # Initialize OpenAI client
            try:
                client = OpenAI(api_key=api_key)
            except Exception as client_error:
                print(f"OpenAI client init error: {client_error}")
                client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")

            # Personalized Athlete Profile
            athlete_profile = f"""
            ATHLETE PROFILE:
            - Device: Treadmill, speed in mph, show segment lengths
            - Pace anchors (0-1% incline):
              * 3.9 mph = brisk walk
              * 5.5 mph = very easy jog (recovery)
              * 6.1 mph = easy-moderate (steady)
              * 6.5 mph = challenging but doable
              * 7.0 mph = comfortable sprint
            - HR zones (WHOOP): Z2 {whoop_zones['Z2'][0]}-{whoop_zones['Z2'][1]}, Z3 {whoop_zones['Z3'][0]}-{whoop_zones['Z3'][1]}, Z4 {whoop_zones['Z4'][0]}-{whoop_zones['Z4'][1]}
            - Preferences: variety but structured; keep mostly Z3 with controlled Z4 surges; use mild inclines
            - Duration defaults: 30, 40, or 45 min
            """

            # Smart Constraints
            constraints = """
            CONSTRAINTS & DIFFICULTY KNOBS:
            - Target intensity mix: 60-75% Z3, 10-20% Z4, remainder Z1-Z2
            - Speed bounds: steady 5.8-6.3 mph; surges 6.7-7.2 mph; cap max at 8.0 mph; recoveries 4.5-5.3 mph
            - Incline rules: recoveries 0-1%; steadies 0-1%; surges up to 3-4%; no hills on sprints if using 7.0+ mph
            - Work:recovery ratios: 1:1 for surges ≤60s, 2:1 for steadies; minimum interval length 1:00
            - Progression: if prior run felt ≤7/10 RPE or Z3 time <60%, add +0.1-0.2 mph to steady sections next time; otherwise keep speeds and add +1 min total time
            - Output language: mph only; print by segment length
            """

            # Strict JSON Schema
            json_schema = f"""
            STRICT OUTPUT SCHEMA - Return ONLY valid JSON that matches this format:
            {{
              "title": "Workout title with duration and focus",
              "total_time_min": <total_duration>,
              "rules": {{
                "speeds": {{
                  "walk_brisk": 3.9,
                  "recovery": [4.5, 5.3],
                  "steady": [5.8, 6.3],
                  "surge": [6.7, 7.2],
                  "max_sprint": [7.3, 8.0]
                }},
                "incline_pct": {{
                  "recovery": [0, 1],
                  "steady": [0, 1],
                  "surge": [0, 4],
                  "max_sprint": [0, 2]
                }},
                "zones": {{
                  "Z2": [{whoop_zones['Z2'][0]}, {whoop_zones['Z2'][1]}],
                  "Z3": [{whoop_zones['Z3'][0]}, {whoop_zones['Z3'][1]}],
                  "Z4": [{whoop_zones['Z4'][0]}, {whoop_zones['Z4'][1]}],
                  "Z5": [{whoop_zones['Z5'][0]}, {whoop_zones['Z5'][1]}]
                }},
                "time_in_zones_target_pct": {{
                  "Z3": <60-75>,
                  "Z4": <10-20>,
                  "other": <remainder>
                }},
                "segment_min_sec": 60,
                "max_segments_above_7mph": 3,
                "max_duration_above_7mph_sec": 60,
                "min_recovery_after_7mph_sec": 90
              }},
              "segments": [
                {{
                  "order": <segment_number>,
                  "duration_sec": <duration_in_seconds>,
                  "speed_mph": <speed>,
                  "incline_pct": <incline>,
                  "intent": "<warmup|steady|surge|recovery|max_sprint|cooldown>",
                  "target_hr_zone": "<Z2|Z3|Z4|Z5>"
                }}
              ],
              "summary": {{
                "target_mix": {{"Z3_pct": <percentage>, "Z4_pct": <percentage>}},
                "avg_speed_mph": <average_speed>
              }},
              "printable": [
                "<duration> min @ <speed> mph — <description>"
              ]
            }}
            """

            # Determine workout duration from user request
            duration = 30  # default
            if "30" in user_request or "thirty" in user_request.lower():
                duration = 30
            elif "40" in user_request or "forty" in user_request.lower():
                duration = 40
            elif "45" in user_request or "forty-five" in user_request.lower():
                duration = 45
            elif "20" in user_request or "twenty" in user_request.lower():
                duration = 20
            elif "60" in user_request or "sixty" in user_request.lower():
                duration = 60

            # Create structured prompt
            structured_prompt = f"""
            {athlete_profile}
            
            {constraints}
            
            {json_schema}
            
            USER REQUEST: {user_request}
            TARGET DURATION: {duration} minutes
            
            Generate a structured treadmill workout that matches the user's request and follows all constraints. 
            Return ONLY the JSON object, no additional text or explanations.
            """

            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert running coach who creates structured, personalized treadmill workouts. You always return valid JSON that matches the exact schema provided."
                    },
                    {"role": "user", "content": structured_prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
            )
            
            # Parse the JSON response
            response_text = (completion.choices[0].message.content or "").strip()
            
            # Try to extract JSON from the response
            import json
            import re
            
            # Look for JSON in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                workout_json = json.loads(json_match.group())
                
                # Add metadata
                workout_json["raw_request"] = user_request
                workout_json["generated_at"] = datetime.now().isoformat()
                workout_json["whoop_zones"] = whoop_zones
                
                print(f"Generated structured workout: {workout_json.get('title', 'Unknown')}")
                
                return jsonify(success=True, workout=workout_json)
                
            else:
                return jsonify(success=False, error="Failed to generate structured workout"), 500
                
        except Exception as openai_error:
            print(f"OpenAI error: {openai_error}")
            return jsonify(success=False, error="Failed to generate workout"), 500
            
    except Exception as e:
        print(f"Error in generate_structured_workout: {e}")
        return jsonify(success=False, error=str(e)), 500

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

# Advanced ML Recommendation Functions
def analyze_performance_patterns(user_id=None, days=30):
    """Analyze user performance patterns for ML recommendations"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Check if workout_sessions table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='workout_sessions'
        """)
        
        if not cursor.fetchone():
            return {
                "success": False,
                "message": "No workout sessions data available yet. Complete a few workouts to see insights."
            }
        
        # Get recent sessions with performance data
        cursor.execute("""
            SELECT 
                ws.*,
                w.description,
                w.workout_type,
                w.difficulty_rating,
                DATE(ws.started_at) as workout_date,
                CASE 
                    WHEN ws.performance_rating >= 8 THEN 'excellent'
                    WHEN ws.performance_rating >= 6 THEN 'good'
                    WHEN ws.performance_rating >= 4 THEN 'fair'
                    ELSE 'poor'
                END as performance_category
            FROM workout_sessions ws
            JOIN workouts w ON ws.workout_id = w.id
            WHERE ws.started_at >= DATE('now', '-{} days')
            AND ws.performance_rating IS NOT NULL
            ORDER BY ws.started_at DESC
        """.format(days))
        
        sessions = cursor.fetchall()
        
        if not sessions:
            return {
                "success": False,
                "message": "Insufficient data for analysis"
            }
        
        # Calculate performance metrics
        total_sessions = len(sessions)
        avg_performance = sum(s['performance_rating'] for s in sessions) / total_sessions
        completion_rate = sum(1 for s in sessions if s['completed_intervals'] > 0) / total_sessions
        
        # Analyze workout type preferences
        workout_types = {}
        for session in sessions:
            wtype = session['workout_type'] or 'manual'
            if wtype not in workout_types:
                workout_types[wtype] = {'count': 0, 'avg_rating': 0, 'ratings': []}
            workout_types[wtype]['count'] += 1
            workout_types[wtype]['ratings'].append(session['performance_rating'])
        
        # Calculate average ratings per workout type
        for wtype in workout_types:
            ratings = workout_types[wtype]['ratings']
            workout_types[wtype]['avg_rating'] = sum(ratings) / len(ratings)
        
        # Analyze difficulty progression
        difficulty_trend = []
        for session in sessions:
            difficulty_trend.append({
                'date': session['workout_date'],
                'difficulty': session['difficulty_rating'] or 3,
                'performance': session['performance_rating']
            })
        
        # Calculate recovery patterns (if WHOOP data available)
        recovery_patterns = analyze_recovery_patterns(sessions)
        
        return {
            "success": True,
            "analysis": {
                "total_sessions": total_sessions,
                "avg_performance": round(avg_performance, 2),
                "completion_rate": round(completion_rate * 100, 1),
                "workout_type_preferences": workout_types,
                "difficulty_trend": difficulty_trend,
                "recovery_patterns": recovery_patterns,
                "performance_distribution": {
                    "excellent": len([s for s in sessions if s['performance_rating'] >= 8]),
                    "good": len([s for s in sessions if 6 <= s['performance_rating'] < 8]),
                    "fair": len([s for s in sessions if 4 <= s['performance_rating'] < 6]),
                    "poor": len([s for s in sessions if s['performance_rating'] < 4])
                }
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def analyze_recovery_patterns(sessions):
    """Analyze recovery patterns from WHOOP data"""
    try:
        # This would integrate with WHOOP API in the future
        # For now, we'll analyze workout frequency and performance correlation
        
        recovery_insights = {
            "optimal_rest_days": 1,  # Default recommendation
            "performance_after_rest": "improved",
            "overtraining_risk": "low"
        }
        
        # Analyze performance based on days since last workout
        if len(sessions) >= 2:
            recent_sessions = sorted(sessions, key=lambda x: x['started_at'])[-5:]
            
            # Simple analysis: check if performance improves with rest
            rest_performance = []
            for i in range(1, len(recent_sessions)):
                days_between = (recent_sessions[i]['started_at'] - recent_sessions[i-1]['started_at']).days
                performance_diff = recent_sessions[i]['performance_rating'] - recent_sessions[i-1]['performance_rating']
                rest_performance.append({
                    'days_rest': days_between,
                    'performance_change': performance_diff
                })
            
            if rest_performance:
                avg_rest_days = sum(r['days_rest'] for r in rest_performance) / len(rest_performance)
                avg_performance_change = sum(r['performance_change'] for r in rest_performance) / len(rest_performance)
                
                recovery_insights.update({
                    "optimal_rest_days": round(avg_rest_days, 1),
                    "performance_after_rest": "improved" if avg_performance_change > 0 else "declined",
                    "avg_performance_change": round(avg_performance_change, 2)
                })
        
        return recovery_insights
        
    except Exception as e:
        return {"error": str(e)}

def generate_personalized_workout(analysis_data, user_preferences=None):
    """Generate personalized workout based on ML analysis"""
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return {"success": False, "error": "OpenAI API key not configured"}
        
        client = OpenAI(api_key=api_key)
        
        # Prepare analysis summary for AI
        analysis_summary = f"""
        User Performance Analysis:
        - Total sessions: {analysis_data['total_sessions']}
        - Average performance: {analysis_data['avg_performance']}/10
        - Completion rate: {analysis_data['completion_rate']}%
        - Performance distribution: {analysis_data['performance_distribution']}
        
        Workout Type Preferences:
        {json.dumps(analysis_data['workout_type_preferences'], indent=2)}
        
        Recovery Patterns:
        {json.dumps(analysis_data['recovery_patterns'], indent=2)}
        
        User Preferences: {user_preferences or 'None specified'}
        """
        
        # Generate personalized workout prompt
        workout_prompt = f"""
        Based on this user's performance analysis, generate a personalized treadmill workout:
        
        {analysis_summary}
        
        Requirements:
        1. Consider their performance patterns and preferences
        2. Adjust difficulty based on their recent performance trend
        3. Choose workout type based on their success rates
        4. Account for recovery patterns and rest needs
        5. Include progressive overload if they're improving
        6. Keep total duration appropriate for their completion rate
        
        Generate a workout in this exact format:
        ```
        **Warm-Up – 5 minutes**
        * 5 min @ 5.0 mph (easy warm-up)
        
        **Main Workout**
        * 10 min @ 6.0 mph (steady pace)
        * 5 min @ 7.0 mph (tempo)
        * 10 min @ 6.0 mph (steady pace)
        
        **Cool-Down – 5 minutes**
        * 5 min @ 5.0 mph (easy cool-down)
        ```
        
        Also provide:
        - Recommended difficulty rating (1-10)
        - Expected performance rating (1-10)
        - Recovery recommendations
        - Next workout suggestions
        """
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": workout_prompt}],
            temperature=0.7,
            max_tokens=500
        )
        
        workout_text = completion.choices[0].message.content or ""
        
        # Parse the generated workout
        intervals = parse_intervals(workout_text)
        
        return {
            "success": True,
            "workout_text": workout_text,
            "intervals": intervals,
            "analysis_based_on": analysis_data,
            "recommendations": {
                "difficulty_rating": 5,  # Would be extracted from AI response
                "expected_performance": 7,
                "recovery_notes": "Based on your patterns, consider 1-2 days rest",
                "next_workout_suggestion": "Try a recovery run if performance drops"
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route("/ml_analysis", methods=["GET"])
def get_ml_analysis():
    """Get ML analysis of user performance patterns"""
    try:
        days = int(request.args.get("days", 30))
        analysis = analyze_performance_patterns(days=days)
        
        if analysis["success"]:
            return jsonify(analysis)
        else:
            return jsonify(analysis), 400
            
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/personalized_workout", methods=["POST"])
def get_personalized_workout():
    """Generate personalized workout based on ML analysis"""
    try:
        data = request.get_json() or {}
        user_preferences = data.get("preferences", {})
        
        # Get performance analysis
        analysis = analyze_performance_patterns(days=30)
        
        if not analysis["success"]:
            return jsonify(analysis), 400
        
        # Generate personalized workout
        workout_result = generate_personalized_workout(
            analysis["analysis"], 
            user_preferences
        )
        
        if workout_result["success"]:
            return jsonify(workout_result)
        else:
            return jsonify(workout_result), 500
            
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/performance_insights", methods=["GET"])
def get_performance_insights():
    """Get detailed performance insights and recommendations"""
    try:
        days = int(request.args.get("days", 30))
        analysis = analyze_performance_patterns(days=days)
        
        if not analysis["success"]:
            return jsonify(analysis), 400
        
        # Generate insights based on analysis
        insights = generate_performance_insights(analysis["analysis"])
        
        return jsonify({
            "success": True,
            "analysis": analysis["analysis"],
            "insights": insights
        })
        
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

def generate_performance_insights(analysis_data):
    """Generate actionable insights from performance analysis"""
    insights = {
        "strengths": [],
        "areas_for_improvement": [],
        "recommendations": [],
        "trends": []
    }
    
    # Analyze strengths
    if analysis_data["avg_performance"] >= 7:
        insights["strengths"].append("Consistently high performance - you're in great shape!")
    
    if analysis_data["completion_rate"] >= 0.8:
        insights["strengths"].append("Excellent workout completion rate")
    
    # Analyze areas for improvement
    if analysis_data["avg_performance"] < 6:
        insights["areas_for_improvement"].append("Consider reducing workout intensity to improve consistency")
    
    if analysis_data["completion_rate"] < 0.7:
        insights["areas_for_improvement"].append("Try shorter workouts to improve completion rate")
    
    # Generate recommendations
    if analysis_data["performance_distribution"]["poor"] > analysis_data["performance_distribution"]["excellent"]:
        insights["recommendations"].append("Focus on recovery - consider more rest days between intense sessions")
    
    # Analyze trends
    if len(analysis_data["difficulty_trend"]) >= 3:
        recent_trend = analysis_data["difficulty_trend"][-3:]
        avg_performance = sum(t["performance"] for t in recent_trend) / 3
        if avg_performance >= 7:
            insights["trends"].append("Recent performance is strong - ready for increased challenge")
        elif avg_performance < 5:
            insights["trends"].append("Recent performance declining - consider recovery week")
    
    return insights

# WHOOP API Integration Functions
def get_whoop_auth_url():
    """Generate WHOOP OAuth authorization URL"""
    if not WHOOP_AVAILABLE:
        return None
    
    import secrets
    
    # Generate a random 8-character state parameter
    state = secrets.token_urlsafe(6)[:8]  # Generate 8 characters
    
    params = {
        'client_id': WHOOP_CLIENT_ID,
        'redirect_uri': WHOOP_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'read:recovery read:workout read:profile read:cycles read:sleep',
        'state': state
    }
    auth_url = f"{WHOOP_API_BASE}/oauth/oauth2/auth"
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    return f"{auth_url}?{query_string}"

def exchange_whoop_code_for_token(code):
    """Exchange authorization code for access token"""
    if not WHOOP_AVAILABLE:
        return None
    
    try:
        # Check if credentials are configured
        if not WHOOP_CLIENT_ID or not WHOOP_CLIENT_SECRET:
            print("Error: WHOOP credentials not configured")
            return None
            
        print(f"Exchanging code for token...")
        print(f"Client ID present: {bool(WHOOP_CLIENT_ID)}")
        print(f"Client Secret present: {bool(WHOOP_CLIENT_SECRET)}")
        print(f"Redirect URI: {WHOOP_REDIRECT_URI}")
        
        token_url = f"{WHOOP_API_BASE}/oauth/oauth2/token"
        
        # Use client_secret_post method (WHOOP's preferred method)
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': WHOOP_CLIENT_ID,
            'client_secret': WHOOP_CLIENT_SECRET,
            'redirect_uri': WHOOP_REDIRECT_URI
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        print(f"Request data: {token_data}")
        print(f"Client secret length: {len(WHOOP_CLIENT_SECRET) if WHOOP_CLIENT_SECRET else 0}")
        print(f"Full client ID: {WHOOP_CLIENT_ID}")
        print(f"Full client secret: {WHOOP_CLIENT_SECRET}")
        print(f"Using client_secret_post method")
        
        response = requests.post(token_url, data=token_data, headers=headers)
        
        print(f"Token response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Token exchange failed: {response.text}")
            return None
            
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Error exchanging code for token: {e}")
        if hasattr(e, 'response'):
            print(f"Response: {e.response.text}")
        return None

def get_whoop_user_profile(access_token):
    """Get WHOOP user profile"""
    if not WHOOP_AVAILABLE:
        return None
    
    try:
        headers = {'Authorization': f'Bearer {access_token}'}
        # Try the v1 endpoint
        response = requests.get(f"{WHOOP_API_BASE_V1}/user/profile/basic", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting WHOOP profile: {e}")
        # Try alternative endpoint
        try:
            response = requests.get(f"{WHOOP_API_BASE_V1}/user", headers=headers)
            response.raise_for_status()
            return response.json()
        except:
            pass
        return None

def get_whoop_recovery_data(access_token, date=None):
    """Get WHOOP recovery data for a specific date"""
    if not WHOOP_AVAILABLE:
        return None
    
    try:
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        headers = {'Authorization': f'Bearer {access_token}'}
        # Try without date parameters first (get latest)
        response = requests.get(
            f"{WHOOP_API_BASE_V1}/recovery",
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        
        # If we have records, find the one for today's date
        if data.get('records'):
            for record in data['records']:
                record_date = record.get('created_at', '')[:10]  # Get YYYY-MM-DD part
                if record_date == date:
                    return record
            # If no exact match, return the first record
            return data['records'][0]
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error getting WHOOP recovery: {e}")
        return None

def get_whoop_workouts(access_token, start_date=None, end_date=None):
    """Get WHOOP workouts for a date range"""
    try:
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        headers = {'Authorization': f'Bearer {access_token}'}
        params = {'start': start_date, 'end': end_date}
        response = requests.get(f"{WHOOP_API_BASE_V1}/workout", headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('records', [])
    except requests.exceptions.RequestException as e:
        print(f"Error getting WHOOP workouts: {e}")
        return None

def get_whoop_heart_rate_data(access_token, workout_id):
    """Get heart rate data for a specific workout"""
    try:
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(f"{WHOOP_API_BASE_V1}/workout/{workout_id}/heart_rate", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting WHOOP heart rate data: {e}")
        return None

def analyze_whoop_performance(whoop_data):
    """Analyze WHOOP performance data for workout recommendations"""
    try:
        if not whoop_data:
            return None
        
        analysis = {
            'recovery_score': whoop_data.get('recovery', {}).get('score', {}).get('recovery_score', 0),
            'sleep_score': whoop_data.get('sleep', {}).get('score', {}).get('sleep_performance', 0),
            'strain_score': whoop_data.get('strain', {}).get('score', {}).get('strain', 0),
            'hrv': whoop_data.get('recovery', {}).get('metrics', {}).get('hrv_rmssd', 0),
            'resting_heart_rate': whoop_data.get('recovery', {}).get('metrics', {}).get('resting_heart_rate', 0),
            'recommendations': []
        }
        
        # Generate recommendations based on WHOOP data
        if analysis['recovery_score'] < 30:
            analysis['recommendations'].append("Low recovery - consider a light recovery workout or rest day")
        elif analysis['recovery_score'] > 70:
            analysis['recommendations'].append("High recovery - good day for intense training")
        
        if analysis['sleep_score'] < 50:
            analysis['recommendations'].append("Poor sleep - focus on recovery and avoid high-intensity workouts")
        
        if analysis['strain_score'] > 15:
            analysis['recommendations'].append("High strain - consider reducing workout intensity")
        
        return analysis
    except Exception as e:
        print(f"Error analyzing WHOOP data: {e}")
        return None

# WHOOP API Routes
@app.route("/whoop/auth")
def whoop_auth():
    """Initiate WHOOP OAuth flow"""
    auth_url = get_whoop_auth_url()
    return redirect(auth_url)

@app.route("/whoop/callback")
def whoop_callback():
    """Handle WHOOP OAuth callback"""
    try:
        # Debug: Log all request parameters
        print(f"WHOOP Callback - All args: {dict(request.args)}")
        print(f"WHOOP Callback - URL: {request.url}")
        
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        error_description = request.args.get('error_description')
        
        print(f"WHOOP Callback - Code: {code[:10] if code else 'None'}...")
        print(f"WHOOP Callback - State: {state}")
        
        if error:
            error_msg = f"WHOOP OAuth Error: {error}"
            if error_description:
                error_msg += f" - {error_description}"
            print(f"WHOOP OAuth Error: {error} - {error_description}")
            return f"""
            <html>
            <body style="font-family: sans-serif; padding: 20px;">
                <h2>WHOOP Connection Failed</h2>
                <p style="color: red;">{error_msg}</p>
                <a href="/">Return to app</a>
            </body>
            </html>
            """, 400
            
        if not code:
            print("No authorization code received from WHOOP")
            return """
            <html>
            <body style="font-family: sans-serif; padding: 20px;">
                <h2>WHOOP Connection Failed</h2>
                <p style="color: red;">No authorization code received</p>
                <a href="/">Return to app</a>
            </body>
            </html>
            """, 400
        
        # Exchange code for token
        print(f"About to exchange code: {code[:20]}...")
        token_data = exchange_whoop_code_for_token(code)
        if not token_data:
            print("Token exchange returned None - checking logs above")
            return """
            <html>
            <body style="font-family: sans-serif; padding: 20px;">
                <h2>WHOOP Connection Failed</h2>
                <p style="color: red;">Failed to exchange code for token. Please check your WHOOP app configuration.</p>
                <p style="color: gray; font-size: 12px;">Check the server logs for detailed debugging information.</p>
                <a href="/">Return to app</a>
            </body>
            </html>
            """, 400
        
        # Store token in session
        session['whoop_access_token'] = token_data.get('access_token')
        session['whoop_refresh_token'] = token_data.get('refresh_token')
        session['whoop_expires_at'] = datetime.now().timestamp() + token_data.get('expires_in', 3600)
        
        # Get user profile
        profile = get_whoop_user_profile(token_data.get('access_token'))
        if profile:
            session['whoop_user_id'] = profile.get('id')
            session['whoop_user_email'] = profile.get('email')
        
        # Success - redirect to app
        return redirect(url_for('index') + '#whoop')
        
    except Exception as e:
        print(f"Error in whoop_callback: {e}")
        return f"""
        <html>
        <body style="font-family: sans-serif; padding: 20px;">
            <h2>WHOOP Connection Error</h2>
            <p style="color: red;">An unexpected error occurred: {str(e)}</p>
            <a href="/">Return to app</a>
        </body>
        </html>
        """, 500

@app.route("/whoop/recovery")
def get_whoop_recovery():
    """Get current WHOOP recovery data"""
    try:
        access_token = session.get('whoop_access_token')
        if not access_token:
            return jsonify(success=False, error="Not authenticated with WHOOP"), 401
        
        recovery_data = get_whoop_recovery_data(access_token)
        if not recovery_data:
            return jsonify(success=False, error="Failed to get recovery data"), 400
        
        # Try to get additional data from other endpoints
        try:
            # Get sleep data - according to WHOOP API docs
            sleep_response = requests.get(
                f"{WHOOP_API_BASE_V1}/sleep",
                headers={'Authorization': f'Bearer {access_token}'}
            )
            if sleep_response.status_code == 200:
                sleep_data = sleep_response.json()
                if sleep_data.get('records'):
                    # Get the most recent sleep record
                    latest_sleep = sleep_data['records'][0]
                    recovery_data['sleep_data'] = latest_sleep
                    print(f"Sleep data found: {latest_sleep.get('score', {}).get('sleep_performance_percentage', 'N/A')}")
        except Exception as e:
            print(f"Error fetching sleep data: {e}")
        
        try:
            # Get strain data from cycle endpoint - according to WHOOP API docs
            cycle_response = requests.get(
                f"{WHOOP_API_BASE_V1}/cycle",
                headers={'Authorization': f'Bearer {access_token}'}
            )
            if cycle_response.status_code == 200:
                cycle_data = cycle_response.json()
                if cycle_data.get('records'):
                    # Get the most recent cycle record
                    latest_cycle = cycle_data['records'][0]
                    recovery_data['strain_data'] = latest_cycle
                    print(f"Strain data found: {latest_cycle.get('score', {}).get('strain', 'N/A')}")
        except Exception as e:
            print(f"Error fetching strain data: {e}")
        
        # Analyze the data
        analysis = analyze_whoop_performance(recovery_data)
        
        return jsonify({
            "success": True,
            "recovery_data": recovery_data,
            "analysis": analysis
        })
        
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/whoop/workouts")
def get_whoop_workouts_route():
    """Get WHOOP workouts"""
    try:
        access_token = session.get('whoop_access_token')
        if not access_token:
            return jsonify(success=False, error="Not authenticated with WHOOP"), 401
        
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        workouts_data = get_whoop_workouts(access_token, start_date, end_date)
        if not workouts_data:
            return jsonify(success=False, error="Failed to get workouts data"), 400
        
        return jsonify({
            "success": True,
            "workouts": workouts_data
        })
        
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/whoop/test")
def test_whoop_api():
    """Test WHOOP API endpoints"""
    access_token = session.get('whoop_access_token')
    if not access_token:
        return jsonify(success=False, error="Not authenticated with WHOOP"), 401
    
    results = {}
    headers = {'Authorization': f'Bearer {access_token}'}
    
    # Test different endpoints
    endpoints = [
        f"{WHOOP_API_BASE_V1}/user/profile/basic",
        f"{WHOOP_API_BASE_V1}/user",
        f"{WHOOP_API_BASE_V1}/recovery",
        f"{WHOOP_API_BASE_V1}/workout",
        f"{WHOOP_API_BASE_V1}/cycle",
        f"{WHOOP_API_BASE_V1}/sleep",
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, headers=headers)
            results[endpoint] = {
                'status': response.status_code,
                'success': response.status_code == 200
            }
            if response.status_code == 200:
                results[endpoint]['sample'] = str(response.json())[:200]
        except Exception as e:
            results[endpoint] = {'error': str(e)}
    
    return jsonify(results)

@app.route("/whoop/recommendations")
def get_whoop_recommendations():
    """Get workout recommendations based on WHOOP data"""
    try:
        access_token = session.get('whoop_access_token')
        if not access_token:
            return jsonify(success=False, error="Not authenticated with WHOOP"), 401
        
        # Get recovery data
        recovery_data = get_whoop_recovery_data(access_token)
        if not recovery_data:
            return jsonify(success=False, error="Failed to get recovery data"), 400
        
        # Analyze and generate recommendations
        analysis = analyze_whoop_performance(recovery_data)
        if not analysis:
            return jsonify(success=False, error="Failed to analyze WHOOP data"), 400
        
        # Generate workout recommendation based on recovery
        recovery_score = analysis.get('recovery_score', 50)
        
        if recovery_score < 30:
            workout_type = "recovery"
            intensity = "low"
            duration = "20-30 minutes"
            recommendation = "Light recovery run or walk"
        elif recovery_score < 60:
            workout_type = "moderate"
            intensity = "medium"
            duration = "30-45 minutes"
            recommendation = "Moderate endurance or tempo run"
        else:
            workout_type = "intense"
            intensity = "high"
            duration = "45-60 minutes"
            recommendation = "High-intensity intervals or long run"
        
        return jsonify({
            "success": True,
            "analysis": analysis,
            "recommendation": {
                "workout_type": workout_type,
                "intensity": intensity,
                "duration": duration,
                "description": recommendation,
                "recovery_score": recovery_score
            }
        })
        
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

# Add new calibration functions after the existing functions
def calculate_fitness_profile(assessment_data):
    """Calculate personalized fitness profile from assessment data."""
    
    # Extract assessment data
    fitness_level = assessment_data.get('fitness_level', 'beginner')  # beginner, intermediate, advanced
    recent_5k_time = assessment_data.get('recent_5k_time', None)  # in minutes
    weekly_miles = assessment_data.get('weekly_miles', 10)
    running_frequency = assessment_data.get('running_frequency', 3)  # days per week
    comfortable_pace = assessment_data.get('comfortable_pace', 6.0)  # mph
    
    # Calculate base fitness score (0-100)
    fitness_score = 0
    
    # Fitness level multiplier
    level_multipliers = {
        'beginner': 0.6,
        'intermediate': 0.8,
        'advanced': 1.0,
        'elite': 1.2
    }
    
    # Base score from fitness level
    fitness_score += 30 * level_multipliers.get(fitness_level, 0.8)
    
    # Adjust based on 5K time if available
    if recent_5k_time:
        # Convert 5K time to fitness score (lower time = higher score)
        if recent_5k_time <= 20:  # Elite
            fitness_score += 40
        elif recent_5k_time <= 25:  # Advanced
            fitness_score += 30
        elif recent_5k_time <= 30:  # Intermediate
            fitness_score += 20
        elif recent_5k_time <= 35:  # Beginner
            fitness_score += 10
        else:  # Very beginner
            fitness_score += 5
    
    # Adjust based on weekly mileage
    fitness_score += min(weekly_miles * 0.5, 20)
    
    # Adjust based on running frequency
    fitness_score += min(running_frequency * 2, 10)
    
    # Cap at 100
    fitness_score = min(fitness_score, 100)
    
    # Calculate personalized pace anchors
    base_pace = comfortable_pace
    
    # Adjust paces based on fitness score
    pace_multiplier = 0.8 + (fitness_score / 100) * 0.4  # 0.8 to 1.2
    
    pace_anchors = {
        'walk_brisk': round(3.5 * pace_multiplier, 1),
        'recovery': round(4.5 * pace_multiplier, 1),
        'steady': round(5.5 * pace_multiplier, 1),
        'tempo': round(6.5 * pace_multiplier, 1),
        'sprint': round(7.5 * pace_multiplier, 1)
    }
    
    # Calculate heart rate zones (estimated if no WHOOP data)
    max_hr_estimate = 220 - 30  # Assuming average age, adjust as needed
    hr_zones = {
        'Z1': [max_hr_estimate * 0.5, max_hr_estimate * 0.6],
        'Z2': [max_hr_estimate * 0.6, max_hr_estimate * 0.7],
        'Z3': [max_hr_estimate * 0.7, max_hr_estimate * 0.8],
        'Z4': [max_hr_estimate * 0.8, max_hr_estimate * 0.9],
        'Z5': [max_hr_estimate * 0.9, max_hr_estimate]
    }
    
    # Calculate workout constraints based on fitness level
    if fitness_score < 30:  # Beginner
        constraints = {
            'max_duration': 30,
            'max_speed': 6.5,
            'max_incline': 2,
            'recovery_ratio': 1.5,  # More recovery
            'z3_target': 50,  # Lower intensity
            'z4_target': 5   # Minimal high intensity
        }
    elif fitness_score < 60:  # Intermediate
        constraints = {
            'max_duration': 45,
            'max_speed': 7.5,
            'max_incline': 4,
            'recovery_ratio': 1.0,
            'z3_target': 65,
            'z4_target': 15
        }
    else:  # Advanced
        constraints = {
            'max_duration': 60,
            'max_speed': 8.5,
            'max_incline': 6,
            'recovery_ratio': 0.8,
            'z3_target': 70,
            'z4_target': 20
        }
    
    return {
        'fitness_score': fitness_score,
        'fitness_level': fitness_level,
        'pace_anchors': pace_anchors,
        'hr_zones': hr_zones,
        'constraints': constraints,
        'assessment_data': assessment_data
    }

def generate_personalized_athlete_profile(fitness_profile):
    """Generate personalized athlete profile for workout generation."""
    
    pace_anchors = fitness_profile['pace_anchors']
    hr_zones = fitness_profile['hr_zones']
    constraints = fitness_profile['constraints']
    
    profile = f"""
    ATHLETE PROFILE:
    - Device: Treadmill, speed in mph, show segment lengths
    - Fitness Level: {fitness_profile['fitness_level'].title()} (Score: {fitness_profile['fitness_score']}/100)
    - Pace anchors (0-1% incline):
      * {pace_anchors['walk_brisk']} mph = brisk walk
      * {pace_anchors['recovery']} mph = very easy jog (recovery)
      * {pace_anchors['steady']} mph = easy-moderate (steady)
      * {pace_anchors['tempo']} mph = challenging but doable
      * {pace_anchors['sprint']} mph = comfortable sprint
    - HR zones: Z2 {int(hr_zones['Z2'][0])}-{int(hr_zones['Z2'][1])}, Z3 {int(hr_zones['Z3'][0])}-{int(hr_zones['Z3'][1])}, Z4 {int(hr_zones['Z4'][0])}-{int(hr_zones['Z4'][1])}
    - Preferences: variety but structured; keep mostly Z3 with controlled Z4 surges; use mild inclines
    - Duration defaults: {constraints['max_duration']} min max
    """
    
    return profile

def generate_personalized_constraints(fitness_profile):
    """Generate personalized constraints for workout generation."""
    
    pace_anchors = fitness_profile['pace_anchors']
    constraints = fitness_profile['constraints']
    
    # Calculate speed bounds based on pace anchors
    steady_min = pace_anchors['steady'] - 0.5
    steady_max = pace_anchors['steady'] + 0.5
    surge_min = pace_anchors['tempo'] - 0.3
    surge_max = pace_anchors['tempo'] + 0.7
    recovery_min = pace_anchors['recovery'] - 0.5
    recovery_max = pace_anchors['recovery'] + 0.3
    
    constraints_text = f"""
    CONSTRAINTS & DIFFICULTY KNOBS:
    - Target intensity mix: {constraints['z3_target']}-75% Z3, {constraints['z4_target']}-20% Z4, remainder Z1-Z2
    - Speed bounds: steady {steady_min:.1f}-{steady_max:.1f} mph; surges {surge_min:.1f}-{surge_max:.1f} mph; cap max at {constraints['max_speed']} mph; recoveries {recovery_min:.1f}-{recovery_max:.1f} mph
    - Incline rules: recoveries 0-1%; steadies 0-1%; surges up to {constraints['max_incline']}%; no hills on sprints if using {pace_anchors['sprint']}+ mph
    - Work:recovery ratios: 1:{constraints['recovery_ratio']} for surges ≤60s, 2:1 for steadies; minimum interval length 1:00
    - Progression: if prior run felt ≤7/10 RPE or Z3 time <60%, add +0.1-0.2 mph to steady sections next time; otherwise keep speeds and add +1 min total time
    - Output language: mph only; print by segment length
    """
    
    return constraints_text

# Add new calibration endpoints
@app.route("/calibrate", methods=["POST"])
def calibrate_user():
    """Calibrate user fitness level through assessment."""
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ['fitness_level', 'weekly_miles', 'running_frequency']
        for field in required_fields:
            if field not in data:
                return jsonify(success=False, error=f"Missing required field: {field}"), 400
        
        # Calculate fitness profile
        fitness_profile = calculate_fitness_profile(data)
        
        # Store calibration data (you could save to database)
        # For now, we'll return it in the response
        calibration_data = {
            'fitness_profile': fitness_profile,
            'calibrated_at': datetime.now().isoformat(),
            'user_id': data.get('user_id', 'anonymous')
        }
        
        return jsonify(success=True, calibration=calibration_data)
        
    except Exception as e:
        print(f"Error in calibrate_user: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route("/generate_personalized_workout", methods=["POST"])
def generate_personalized_workout():
    """Generate workout using personalized fitness profile."""
    try:
        # Check API key
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return jsonify(success=False, error="OpenAI API key not configured"), 500

        # Validate input
        body = request.get_json() or {}
        user_request = (body.get("request") or "").strip()
        calibration_data = body.get("calibration", {})
        
        if not user_request:
            return jsonify(success=False, error="Please describe the workout"), 400
        
        if not calibration_data:
            return jsonify(success=False, error="Please provide calibration data"), 400

        try:
            import random
            from datetime import datetime
            
            # Initialize OpenAI client
            try:
                client = OpenAI(api_key=api_key)
            except Exception as client_error:
                print(f"OpenAI client init error: {client_error}")
                client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")

            # Get fitness profile
            fitness_profile = calibration_data.get('fitness_profile', {})
            
            # Generate personalized athlete profile
            athlete_profile = generate_personalized_athlete_profile(fitness_profile)
            
            # Generate personalized constraints
            constraints = generate_personalized_constraints(fitness_profile)
            
            # Get WHOOP zones if available, otherwise use calculated zones
            whoop_zones = body.get("whoop_zones")
            if not whoop_zones:
                hr_zones = fitness_profile.get('hr_zones', {})
                whoop_zones = {
                    "Z2": [int(hr_zones['Z2'][0]), int(hr_zones['Z2'][1])],
                    "Z3": [int(hr_zones['Z3'][0]), int(hr_zones['Z3'][1])],
                    "Z4": [int(hr_zones['Z4'][0]), int(hr_zones['Z4'][1])],
                    "Z5": [int(hr_zones['Z5'][0]), int(hr_zones['Z5'][1])]
                }

            # Strict JSON Schema with personalized data
            pace_anchors = fitness_profile.get('pace_anchors', {})
            constraints_data = fitness_profile.get('constraints', {})
            
            json_schema = f"""
            STRICT OUTPUT SCHEMA - Return ONLY valid JSON that matches this format:
            {{
              "title": "Workout title with duration and focus",
              "total_time_min": <total_duration>,
              "rules": {{
                "speeds": {{
                  "walk_brisk": {pace_anchors.get('walk_brisk', 3.9)},
                  "recovery": [{pace_anchors.get('recovery', 4.5) - 0.5}, {pace_anchors.get('recovery', 4.5) + 0.3}],
                  "steady": [{pace_anchors.get('steady', 5.8) - 0.5}, {pace_anchors.get('steady', 5.8) + 0.5}],
                  "surge": [{pace_anchors.get('tempo', 6.7) - 0.3}, {pace_anchors.get('tempo', 6.7) + 0.7}],
                  "max_sprint": [{pace_anchors.get('sprint', 7.3)}, {constraints_data.get('max_speed', 8.0)}]
                }},
                "incline_pct": {{
                  "recovery": [0, 1],
                  "steady": [0, 1],
                  "surge": [0, {constraints_data.get('max_incline', 4)}],
                  "max_sprint": [0, 2]
                }},
                "zones": {{
                  "Z2": [{whoop_zones['Z2'][0]}, {whoop_zones['Z2'][1]}],
                  "Z3": [{whoop_zones['Z3'][0]}, {whoop_zones['Z3'][1]}],
                  "Z4": [{whoop_zones['Z4'][0]}, {whoop_zones['Z4'][1]}],
                  "Z5": [{whoop_zones['Z5'][0]}, {whoop_zones['Z5'][1]}]
                }},
                "time_in_zones_target_pct": {{
                  "Z3": {constraints_data.get('z3_target', 60)},
                  "Z4": {constraints_data.get('z4_target', 15)},
                  "other": {100 - constraints_data.get('z3_target', 60) - constraints_data.get('z4_target', 15)}
                }},
                "segment_min_sec": 60,
                "max_segments_above_7mph": 3,
                "max_duration_above_7mph_sec": 60,
                "min_recovery_after_7mph_sec": 90
              }},
              "segments": [
                {{
                  "order": <segment_number>,
                  "duration_sec": <duration_in_seconds>,
                  "speed_mph": <speed>,
                  "incline_pct": <incline>,
                  "intent": "<warmup|steady|surge|recovery|max_sprint|cooldown>",
                  "target_hr_zone": "<Z2|Z3|Z4|Z5>"
                }}
              ],
              "summary": {{
                "target_mix": {{"Z3_pct": <percentage>, "Z4_pct": <percentage>}},
                "avg_speed_mph": <average_speed>
              }},
              "printable": [
                "<duration> min @ <speed> mph — <description>"
              ]
            }}
            """

            # Determine workout duration from user request
            max_duration = constraints_data.get('max_duration', 30)
            duration = min(max_duration, 30)  # default
            
            if "30" in user_request or "thirty" in user_request.lower():
                duration = min(30, max_duration)
            elif "40" in user_request or "forty" in user_request.lower():
                duration = min(40, max_duration)
            elif "45" in user_request or "forty-five" in user_request.lower():
                duration = min(45, max_duration)
            elif "20" in user_request or "twenty" in user_request.lower():
                duration = min(20, max_duration)
            elif "60" in user_request or "sixty" in user_request.lower():
                duration = min(60, max_duration)

            # Create structured prompt
            structured_prompt = f"""
            {athlete_profile}
            
            {constraints}
            
            {json_schema}
            
            USER REQUEST: {user_request}
            TARGET DURATION: {duration} minutes
            FITNESS LEVEL: {fitness_profile.get('fitness_level', 'intermediate')}
            
            Generate a structured treadmill workout that matches the user's request and follows all constraints. 
            Return ONLY the JSON object, no additional text or explanations.
            """

            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert running coach who creates structured, personalized treadmill workouts. You always return valid JSON that matches the exact schema provided."
                    },
                    {"role": "user", "content": structured_prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
            )
            
            # Parse the JSON response
            response_text = (completion.choices[0].message.content or "").strip()
            
            # Try to extract JSON from the response
            import json
            import re
            
            # Look for JSON in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                workout_json = json.loads(json_match.group())
                
                # Add metadata
                workout_json["raw_request"] = user_request
                workout_json["generated_at"] = datetime.now().isoformat()
                workout_json["fitness_profile"] = fitness_profile
                workout_json["whoop_zones"] = whoop_zones
                
                print(f"Generated personalized workout: {workout_json.get('title', 'Unknown')} for {fitness_profile.get('fitness_level', 'unknown')} level")
                
                return jsonify(success=True, workout=workout_json)
                
            else:
                return jsonify(success=False, error="Failed to generate structured workout"), 500
                
        except Exception as openai_error:
            print(f"OpenAI error: {openai_error}")
            return jsonify(success=False, error="Failed to generate workout"), 500
            
    except Exception as e:
        print(f"Error in generate_personalized_workout: {e}")
        return jsonify(success=False, error=str(e)), 500

# Add after the existing calibration functions
def create_athlete_profile_from_data(profile_data):
    """Create athlete profile from specific user data."""
    
    # Extract profile data
    demographics = profile_data.get('demographics', {})
    pace_anchors = profile_data.get('pace_anchors', {})
    hr_zones = profile_data.get('hr_zones', {})
    goals = profile_data.get('goals', {})
    constraints = profile_data.get('constraints', {})
    
    # Create personalized athlete profile
    athlete_profile = f"""
    ATHLETE PROFILE:
    - Demographics: {demographics.get('gender', 'unknown')}, {demographics.get('age', 'unknown')}, {demographics.get('height', 'unknown')}, {demographics.get('weight', 'unknown')}
    - Device: Treadmill, speed in mph, show segment lengths
    - Pace anchors (0-1% incline):
      * {pace_anchors.get('walk', 3.9)} mph = brisk walk
      * {pace_anchors.get('very_easy', 5.5)} mph = very easy jog (recovery)
      * {pace_anchors.get('easy_moderate', 6.1)} mph = easy-moderate (steady)
      * {pace_anchors.get('challenging', 6.5)} mph = challenging but doable
      * {pace_anchors.get('comfortable_sprint', 7.0)} mph = comfortable sprint
    - HR zones: Z2 {hr_zones.get('Z2', [140, 152])[0]}-{hr_zones.get('Z2', [140, 152])[1]}, Z3 {hr_zones.get('Z3', [153, 164])[0]}-{hr_zones.get('Z3', [153, 164])[1]}, Z4 {hr_zones.get('Z4', [165, 177])[0]}-{hr_zones.get('Z4', [165, 177])[1]}
    - Goals: {goals.get('description', 'general fitness')}
    - Preferences: variety but structured; keep mostly Z3 with controlled Z4 surges; use mild inclines
    """
    
    return athlete_profile

def create_constraints_from_data(constraints_data):
    """Create constraints from specific user data."""
    
    constraints_text = f"""
    CONSTRAINTS & DIFFICULTY KNOBS:
    - Target intensity mix: {constraints_data.get('z3_target', 65)}% Z3, {constraints_data.get('z4_target', 15)}% Z4, remainder Z1-Z2
    - Speed bounds: steady {constraints_data.get('steady_min', 5.8)}-{constraints_data.get('steady_max', 6.3)} mph; surges {constraints_data.get('surge_min', 6.7)}-{constraints_data.get('surge_max', 7.2)} mph; cap max at {constraints_data.get('max_speed', 8.0)} mph; recoveries {constraints_data.get('recovery_min', 4.5)}-{constraints_data.get('recovery_max', 5.3)} mph
    - Incline rules: recoveries 0-{constraints_data.get('recovery_incline_max', 1)}%; steadies 0-{constraints_data.get('steady_incline_max', 1)}%; surges up to {constraints_data.get('surge_incline_max', 4)}%; no hills on sprints if using {constraints_data.get('sprint_no_hill_threshold', 7.0)}+ mph
    - Work:recovery ratios: 1:{constraints_data.get('surge_recovery_ratio', 1)} for surges ≤{constraints_data.get('max_surge_duration', 60)}s, {constraints_data.get('steady_recovery_ratio', 2)}:1 for steadies; minimum interval length {constraints_data.get('min_interval_seconds', 60)}:00
    - Cooldown: {constraints_data.get('cooldown_duration', 3)}:00 at {constraints_data.get('cooldown_speed', 4.0)} mph
    - Output language: mph only; print by segment length
    """
    
    return constraints_text

@app.route("/generate_from_profile", methods=["POST"])
def generate_from_profile():
    """Generate workout using specific athlete profile data."""
    try:
        # Check API key
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return jsonify(success=False, error="OpenAI API key not configured"), 500

        # Validate input
        body = request.get_json() or {}
        user_request = (body.get("request") or "").strip()
        profile_data = body.get("profile", {})
        
        if not user_request:
            return jsonify(success=False, error="Please describe the workout"), 400
        
        if not profile_data:
            return jsonify(success=False, error="Please provide athlete profile data"), 400

        try:
            from datetime import datetime
            
            # Initialize OpenAI client
            try:
                client = OpenAI(api_key=api_key)
            except Exception as client_error:
                print(f"OpenAI client init error: {client_error}")
                client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")

            # Create personalized athlete profile
            athlete_profile = create_athlete_profile_from_data(profile_data)
            
            # Create personalized constraints
            constraints = create_constraints_from_data(profile_data.get('constraints', {}))
            
            # Get heart rate zones
            hr_zones = profile_data.get('hr_zones', {
                'Z2': [140, 152],
                'Z3': [153, 164],
                'Z4': [165, 177],
                'Z5': [178, 999]
            })
            
            # Get pace anchors
            pace_anchors = profile_data.get('pace_anchors', {
                'walk': 3.9,
                'very_easy': 5.5,
                'easy_moderate': 6.1,
                'challenging': 6.5,
                'comfortable_sprint': 7.0
            })
            
            # Get constraints data
            constraints_data = profile_data.get('constraints', {})
            
            # Strict JSON Schema with personalized data
            json_schema = f"""
            STRICT OUTPUT SCHEMA - Return ONLY valid JSON that matches this format:
            {{
              "title": "Workout title with duration and focus",
              "total_time_min": <total_duration>,
              "rules": {{
                "speeds": {{
                  "walk_brisk": {pace_anchors.get('walk', 3.9)},
                  "recovery": [{constraints_data.get('recovery_min', 4.5)}, {constraints_data.get('recovery_max', 5.3)}],
                  "steady": [{constraints_data.get('steady_min', 5.8)}, {constraints_data.get('steady_max', 6.3)}],
                  "surge": [{constraints_data.get('surge_min', 6.7)}, {constraints_data.get('surge_max', 7.2)}],
                  "max_sprint": [{pace_anchors.get('comfortable_sprint', 7.0)}, {constraints_data.get('max_speed', 8.0)}]
                }},
                "incline_pct": {{
                  "recovery": [0, {constraints_data.get('recovery_incline_max', 1)}],
                  "steady": [0, {constraints_data.get('steady_incline_max', 1)}],
                  "surge": [0, {constraints_data.get('surge_incline_max', 4)}],
                  "max_sprint": [0, 2]
                }},
                "zones": {{
                  "Z2": [{hr_zones['Z2'][0]}, {hr_zones['Z2'][1]}],
                  "Z3": [{hr_zones['Z3'][0]}, {hr_zones['Z3'][1]}],
                  "Z4": [{hr_zones['Z4'][0]}, {hr_zones['Z4'][1]}],
                  "Z5": [{hr_zones['Z5'][0]}, {hr_zones['Z5'][1]}]
                }},
                "time_in_zones_target_pct": {{
                  "Z3": {constraints_data.get('z3_target', 65)},
                  "Z4": {constraints_data.get('z4_target', 15)},
                  "other": {100 - constraints_data.get('z3_target', 65) - constraints_data.get('z4_target', 15)}
                }},
                "segment_min_sec": {constraints_data.get('min_interval_seconds', 60)},
                "max_segments_above_7mph": 3,
                "max_duration_above_7mph_sec": {constraints_data.get('max_surge_duration', 60)},
                "min_recovery_after_7mph_sec": 90
              }},
              "segments": [
                {{
                  "order": <segment_number>,
                  "duration_sec": <duration_in_seconds>,
                  "speed_mph": <speed>,
                  "incline_pct": <incline>,
                  "intent": "<warmup|steady|surge|recovery|max_sprint|cooldown>",
                  "target_hr_zone": "<Z2|Z3|Z4|Z5>"
                }}
              ],
              "summary": {{
                "target_mix": {{"Z3_pct": <percentage>, "Z4_pct": <percentage>}},
                "avg_speed_mph": <average_speed>
              }},
              "printable": [
                "<duration> min @ <speed> mph — <description>"
              ]
            }}
            """

            # Determine workout duration from user request
            duration = 30  # default
            if "30" in user_request or "thirty" in user_request.lower():
                duration = 30
            elif "40" in user_request or "forty" in user_request.lower():
                duration = 40
            elif "45" in user_request or "forty-five" in user_request.lower():
                duration = 45
            elif "20" in user_request or "twenty" in user_request.lower():
                duration = 20
            elif "60" in user_request or "sixty" in user_request.lower():
                duration = 60

            # Create structured prompt
            structured_prompt = f"""
            You are a treadmill run planner. Use the athlete profile below and obey constraints and schema. If any constraint conflicts, adjust speed first, then incline. Return valid JSON only.

            {athlete_profile}
            
            {constraints}
            
            {json_schema}
            
            USER REQUEST: {user_request}
            TARGET DURATION: {duration} minutes
            
            Generate a structured treadmill workout that matches the user's request and follows all constraints. 
            Return ONLY the JSON object, no additional text or explanations.
            """

            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a treadmill run planner. Use the athlete profile below and obey constraints and schema. If any constraint conflicts, adjust speed first, then incline. Return valid JSON only."
                    },
                    {"role": "user", "content": structured_prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
            )
            
            # Parse the JSON response
            response_text = (completion.choices[0].message.content or "").strip()
            
            # Try to extract JSON from the response
            import json
            import re
            
            # Look for JSON in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                workout_json = json.loads(json_match.group())
                
                # Add metadata
                workout_json["raw_request"] = user_request
                workout_json["generated_at"] = datetime.now().isoformat()
                workout_json["athlete_profile"] = profile_data
                
                print(f"Generated profile-based workout: {workout_json.get('title', 'Unknown')}")
                
                return jsonify(success=True, workout=workout_json)
                
            else:
                return jsonify(success=False, error="Failed to generate structured workout"), 500
                
        except Exception as openai_error:
            print(f"OpenAI error: {openai_error}")
            return jsonify(success=False, error="Failed to generate workout"), 500
            
    except Exception as e:
        print(f"Error in generate_from_profile: {e}")
        return jsonify(success=False, error=str(e)), 500

# Example function to create your specific profile
def create_user_profile():
    """Create the user's specific profile based on their data."""
    return {
        "demographics": {
            "gender": "male",
            "age": 40,
            "height": "6'2\"",
            "weight": "212 lb"
        },
        "pace_anchors": {
            "walk": 3.9,
            "very_easy": 5.5,
            "easy_moderate": 6.1,
            "challenging": 6.5,
            "comfortable_sprint": 7.0
        },
        "hr_zones": {
            "Z2": [140, 152],
            "Z3": [153, 164],
            "Z4": [165, 177],
            "Z5": [178, 999]
        },
        "goals": {
            "description": "30-min pace push with Z3 base and brief Z4 surges"
        },
        "constraints": {
            "z3_target": 65,
            "z4_target": 15,
            "steady_min": 5.8,
            "steady_max": 6.3,
            "surge_min": 6.7,
            "surge_max": 7.2,
            "max_speed": 8.0,
            "recovery_min": 4.5,
            "recovery_max": 5.3,
            "recovery_incline_max": 1,
            "steady_incline_max": 1,
            "surge_incline_max": 4,
            "sprint_no_hill_threshold": 7.0,
            "surge_recovery_ratio": 1,
            "max_surge_duration": 60,
            "steady_recovery_ratio": 2,
            "min_interval_seconds": 60,
            "cooldown_duration": 3,
            "cooldown_speed": 4.0
        }
    }

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)

# Ensure database is initialized when app starts
with app.app_context():
    init_db()