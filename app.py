import os
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__, static_folder='static', template_folder='templates')

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
    # This could also be AI-assisted, but keeping local parse
    return jsonify(success=True, intervals=[])

@app.route("/generate_workout", methods=["POST"])
def generate_workout():
    data = request.get_json() or {}
    req = (data.get("request") or "").strip()
    if not req:
        return jsonify(success=False, error="Please describe the workout"), 400

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
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)