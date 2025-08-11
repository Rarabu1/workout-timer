import os
import sqlite3
import json
import traceback 
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, g, redirect, url_for, session
from dotenv import load_dotenv
from openai import OpenAI

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
WHOOP_CLIENT_SECRET = os.getenv('WHOOP_CLIENT_SECRET')
WHOOP_REDIRECT_URI = os.getenv('WHOOP_REDIRECT_URI', 'http://localhost:5000/whoop/callback')
WHOOP_API_BASE = 'https://api.whoop.com'

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
    
    params = {
        'client_id': WHOOP_CLIENT_ID,
        'redirect_uri': WHOOP_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'read:recovery read:workouts read:profile read:cycles read:sleep'
    }
    auth_url = f"{WHOOP_API_BASE}/oauth/authorize"
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    return f"{auth_url}?{query_string}"

def exchange_whoop_code_for_token(code):
    """Exchange authorization code for access token"""
    if not WHOOP_AVAILABLE:
        return None
    
    try:
        response = requests.post(f"{WHOOP_API_BASE}/oauth/token", data={
            'client_id': WHOOP_CLIENT_ID,
            'client_secret': WHOOP_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': WHOOP_REDIRECT_URI
        })
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error exchanging code for token: {e}")
        return None

def get_whoop_user_profile(access_token):
    """Get WHOOP user profile"""
    if not WHOOP_AVAILABLE:
        return None
    
    try:
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(f"{WHOOP_API_BASE}/user/profile", headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting WHOOP profile: {e}")
        return None

def get_whoop_recovery_data(access_token, date=None):
    """Get WHOOP recovery data for a specific date"""
    if not WHOOP_AVAILABLE:
        return None
    
    try:
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(f"{WHOOP_API_BASE}/user/recovery", headers=headers, params={'date': date})
        response.raise_for_status()
        return response.json()
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
        response = requests.get(f"{WHOOP_API_BASE}/user/workouts", headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting WHOOP workouts: {e}")
        return None

def get_whoop_heart_rate_data(access_token, workout_id):
    """Get heart rate data for a specific workout"""
    try:
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(f"{WHOOP_API_BASE}/user/workouts/{workout_id}/heart_rate", headers=headers)
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
        code = request.args.get('code')
        if not code:
            return jsonify(success=False, error="No authorization code received"), 400
        
        # Exchange code for token
        token_data = exchange_whoop_code_for_token(code)
        if not token_data:
            return jsonify(success=False, error="Failed to exchange code for token"), 400
        
        # Store token in session
        session['whoop_access_token'] = token_data.get('access_token')
        session['whoop_refresh_token'] = token_data.get('refresh_token')
        session['whoop_expires_at'] = datetime.now().timestamp() + token_data.get('expires_in', 3600)
        
        # Get user profile
        profile = get_whoop_user_profile(token_data.get('access_token'))
        if profile:
            session['whoop_user_id'] = profile.get('id')
            session['whoop_user_email'] = profile.get('email')
        
        return redirect(url_for('index'))
        
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

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

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)

# Ensure database is initialized when app starts
with app.app_context():
    init_db()