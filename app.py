from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__, template_folder="templates", static_folder="static")

@app.route('/')
def home():
    # Serve index.html from the templates folder
    return render_template("index.html")

@app.route('/workout_suggestions', methods=['GET'])
def workout_suggestions():
    # Simple built‑in ideas so the UI renders even without a DB/API
    suggestions = [
        "20 minute endurance run with steady pacing",
        "30 minute VO2 max intervals (mph only)",
        "40 minute hill repeats (incline work)",
        "45 minute progression run, finish strong",
        "60 minute long run with short surges",
    ]
    return jsonify(suggestions)

@app.route('/generate_workout', methods=['POST'])
def generate_workout():
    data = request.get_json(silent=True) or {}
    req = (data.get('request') or '').strip()

    # Minimal, hardcoded intervals so the timer works on Render
    intervals = [
        {"duration_min": 5,  "speed_mph": 5.5, "incline": 0, "description": "Warm-up"},
        {"duration_min": 3,  "speed_mph": 6.8, "incline": 1, "description": "Work"},
        {"duration_min": 2,  "speed_mph": 5.2, "incline": 0, "description": "Recovery"},
        {"duration_min": 3,  "speed_mph": 7.0, "incline": 1, "description": "Work"},
        {"duration_min": 2,  "speed_mph": 5.2, "incline": 0, "description": "Recovery"},
        {"duration_min": 5,  "speed_mph": 5.0, "incline": 0, "description": "Cool-down"},
    ]

    lines = [f"Auto plan for: {req}"] if req else ["Auto plan:"]
    for i, it in enumerate(intervals, 1):
        desc = it.get('description') or ''
        lines.append(f"{i}. {it['duration_min']} min @ {it['speed_mph']} mph{(' - ' + desc) if desc else ''}")
    workout_text = "\n".join(lines)

    return jsonify(success=True, intervals=intervals, workout_text=workout_text)

@app.route('/parse', methods=['POST'])
def parse_workout():
    # Very light parser: returns a single easy block so the UI proceeds
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify(success=False, error="No workout text provided"), 400

    intervals = [
        {"duration_min": 10, "speed_mph": 5.5, "incline": 0, "description": "Parsed block 1"},
        {"duration_min": 10, "speed_mph": 6.0, "incline": 0, "description": "Parsed block 2"},
    ]
    return jsonify(success=True, intervals=intervals)

@app.route('/saved_workouts', methods=['GET'])
def saved_workouts():
    # No persistence wired yet — return empty list
    return jsonify([])

@app.route('/load_workout/<wid>', methods=['GET'])
def load_workout(wid):
    return jsonify(success=False, error="Loading saved workouts not implemented yet")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
