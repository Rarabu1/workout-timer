"""
Backend Specs & Scaffolding for The Treadmill Run Coach (for Cursor/Claude)

Overview
--------
This module bundles the backend requirements and a runnable scaffold. It addresses three issues:
1) Timer must run continuously across intervals (no reset until workout ends).
2) Workout generation must vary with inputs (duration, goals, constraints) instead of producing the same plan each time).
3) Regeneration must be possible after selecting a workout without overwriting history.

Domain Model
------------
WorkoutTemplate
  - id (uuid)
  - created_at (ts)
  - source ("ai" | "preset")
  - inputs (json) — user profile + duration + goals + constraints
  - seed (int) — deterministic randomness
  - segments (array of IntervalSegment)
  - stats (json) — total_time, etc.

IntervalSegment
  - index (int)
  - duration_s (int)
  - speed_mph (float)
  - incline_pct (float)
  - label (string)

RunSession
  - id (uuid)
  - workout_id (uuid → WorkoutTemplate)
  - status (idle | running | paused | completed | aborted)
  - elapsed_s (int; continuous)
  - segment_elapsed_s (int; resets per segment)
  - current_segment_index (int)

Timer Rules
-----------
- elapsed_s counts total run time across all intervals (minus pauses).
- segment_elapsed_s resets only on segment changes.
- Segments advance when segment_elapsed_s >= duration_s.
- On last segment completion, session is "completed".
- Use a monotonic clock for accuracy. Server is source of truth.

API Endpoints (scaffolded below)
--------------------------------
Workouts
- POST /workouts/generate → new template
- GET  /workouts/{id}
- POST /workouts/{id}/regenerate → new template, same inputs, new seed

Sessions
- POST /sessions → create new run session
- POST /sessions/{id}/start
- POST /sessions/{id}/pause
- POST /sessions/{id}/resume
- POST /sessions/{id}/skip
- POST /sessions/{id}/back
- GET  /sessions/{id} → returns authoritative timer state (tick applied)

Acceptance Criteria
-------------------
- Timer never resets to zero mid-run; only segment_elapsed_s resets.
- Different input durations produce different workouts.
- Same inputs + seed → identical plan; same inputs + different seed → different plan.
- Regeneration after selection returns a new workout id; history remains.

Suggested Tests
---------------
- Timer rollover and pause/resume.
- 30 vs 60 min workouts differ.
- Same inputs + seed → identical plan; same inputs + different seed → different plan.

Integration Notes
-----------------
- This scaffold uses FastAPI with in-memory storage to keep it simple. Swap out the stores for SQLite/Postgres as needed.
- You can keep this running side-by-side with the existing Flask app while migrating endpoints.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal
import uuid, time, random

app = FastAPI(title="Treadmill Run Coach API (Scaffold)")

# -------------------------
# Data Models
# -------------------------
class IntervalSegment(BaseModel):
    index: int
    duration_s: int
    speed_mph: float
    incline_pct: float
    label: Literal["warmup", "steady", "push", "recovery", "cooldown"] = "steady"

class WorkoutTemplate(BaseModel):
    id: str
    created_at: float
    source: Literal["ai", "preset"] = "ai"
    inputs: Dict
    seed: int
    segments: List[IntervalSegment]
    stats: Dict

class SessionState(BaseModel):
    id: str
    workout_id: str
    status: Literal["idle", "running", "paused", "completed", "aborted"] = "idle"
    elapsed_s: float = 0.0  # Use float for more precision
    segment_elapsed_s: float = 0.0  # Use float for more precision
    current_segment_index: int = 0
    last_tick_mono: float = Field(default_factory=time.monotonic)

# -------------------------
# In-memory stores (replace with DB later)
# -------------------------
_WORKOUTS: Dict[str, WorkoutTemplate] = {}
_SESSIONS: Dict[str, SessionState] = {}

# -------------------------
# Utility: generation w/ seed
# -------------------------
STEADY_SPEEDS = [5.8, 6.0, 6.1, 6.3]
PUSH_SPEEDS = [6.7, 6.9, 7.0, 7.1]
INCLINES = [0, 1, 1, 2, 3]

def _generate_segments(total_s: int, seed: int) -> List[IntervalSegment]:
    rnd = random.Random(seed)
    segs: List[IntervalSegment] = []
    idx = 0
    # warmup
    warm = 300 if total_s >= 600 else max(60, total_s // 10)
    segs.append(IntervalSegment(index=idx, duration_s=warm, speed_mph=4.0, incline_pct=0, label="warmup"))
    idx += 1
    remain = max(0, total_s - warm - 300)  # leave room for cooldown if possible
    # alternating steady/push blocks
    while remain > 0:
        d1 = min(remain, rnd.choice([120, 180, 240]))
        segs.append(IntervalSegment(index=idx, duration_s=d1, speed_mph=rnd.choice(STEADY_SPEEDS), incline_pct=rnd.choice(INCLINES), label="steady"))
        idx += 1
        remain -= d1
        if remain <= 0:
            break
        d2 = min(remain, rnd.choice([60, 90, 120]))
        segs.append(IntervalSegment(index=idx, duration_s=d2, speed_mph=rnd.choice(PUSH_SPEEDS), incline_pct=rnd.choice(INCLINES), label="push"))
        idx += 1
        remain -= d2
    # cooldown
    cool = min(300, max(60, total_s - sum(s.duration_s for s in segs)))
    if cool > 0:
        segs.append(IntervalSegment(index=idx, duration_s=cool, speed_mph=4.0, incline_pct=0, label="cooldown"))
    # reindex
    for i, s in enumerate(segs):
        s.index = i
    return segs

# -------------------------
# Workouts API
# -------------------------
@app.post("/workouts/generate", response_model=WorkoutTemplate)
def generate_workout(inputs: Dict):
    duration_min = int(inputs.get("duration_min", 30))
    total_s = duration_min * 60
    seed = int(inputs.get("seed") or random.randint(0, 2**31 - 1))
    segments = _generate_segments(total_s, seed)
    wid = str(uuid.uuid4())
    workout = WorkoutTemplate(
        id=wid,
        created_at=time.time(),
        inputs=inputs,
        seed=seed,
        segments=segments,
        stats={"total_time_s": total_s},
    )
    _WORKOUTS[wid] = workout
    return workout

@app.get("/workouts/{workout_id}", response_model=WorkoutTemplate)
def get_workout(workout_id: str):
    w = _WORKOUTS.get(workout_id)
    if not w:
        raise HTTPException(404, "Workout not found")
    return w

@app.post("/workouts/{workout_id}/regenerate", response_model=WorkoutTemplate)
def regenerate_workout(workout_id: str):
    base = _WORKOUTS.get(workout_id)
    if not base:
        raise HTTPException(404, "Workout not found")
    inputs = dict(base.inputs)
    inputs["seed"] = random.randint(0, 2**31 - 1)
    return generate_workout(inputs)  # type: ignore[arg-type]

# -------------------------
# Sessions API — server-authoritative timer
# -------------------------
@app.post("/sessions", response_model=SessionState)
def create_session(workout_id: str):
    if workout_id not in _WORKOUTS:
        raise HTTPException(404, "Workout not found")
    sid = str(uuid.uuid4())
    s = SessionState(id=sid, workout_id=workout_id)
    _SESSIONS[sid] = s
    return s

@app.post("/sessions/{sid}/start", response_model=SessionState)
def start_session(sid: str):
    s = _SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "Session not found")
    s.status = "running"
    s.last_tick_mono = time.monotonic()  # Set baseline time
    return s

@app.post("/sessions/{sid}/pause", response_model=SessionState)
def pause_session(sid: str):
    s = _SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "Session not found")
    _tick(s)
    s.status = "paused"
    return s

@app.post("/sessions/{sid}/resume", response_model=SessionState)
def resume_session(sid: str):
    s = _SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "Session not found")
    s.status = "running"
    s.last_tick_mono = time.monotonic()  # Set baseline time
    return s

@app.post("/sessions/{sid}/skip", response_model=SessionState)
def skip_segment(sid: str):
    s = _SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "Session not found")
    _tick(s)
    s.current_segment_index += 1
    s.segment_elapsed_s = 0
    return s

@app.post("/sessions/{sid}/back", response_model=SessionState)
def back_segment(sid: str):
    s = _SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "Session not found")
    _tick(s)
    s.current_segment_index = max(0, s.current_segment_index - 1)
    s.segment_elapsed_s = 0
    return s

@app.get("/sessions/{sid}", response_model=SessionState)
def get_state(sid: str):
    s = _SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "Session not found")
    _tick(s)
    return s

# -------------------------
# Timer core — continuous elapsed across intervals
# -------------------------
def _tick(s: SessionState) -> None:
    if s.status != "running":
        return
    now = time.monotonic()
    delta = max(0, now - s.last_tick_mono)
    if delta > 0:
        s.elapsed_s += delta
        s.segment_elapsed_s += delta

        w = _WORKOUTS.get(s.workout_id)
        if w:
            segs = w.segments
            while s.current_segment_index < len(segs) and s.segment_elapsed_s >= segs[s.current_segment_index].duration_s:
                s.segment_elapsed_s -= segs[s.current_segment_index].duration_s
                s.current_segment_index += 1
            if s.current_segment_index >= len(segs):
                # Completed
                s.status = "completed"
                s.segment_elapsed_s = 0
                s.elapsed_s = float(w.stats.get("total_time_s", s.elapsed_s))
        s.last_tick_mono = now

# -------------------------
# Dev helper: run with uvicorn
# -------------------------
# Run with:
#   uvicorn backend_scaffold:app --reload --port 8080
# You can also mount these endpoints behind your existing Flask app via a reverse proxy during migration.
