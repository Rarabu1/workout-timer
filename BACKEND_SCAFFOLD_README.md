# Treadmill Run Coach Backend Scaffold

This is a FastAPI-based backend scaffold that addresses three key issues in the current workout timer:

1. **Continuous Timer**: Timer runs continuously across intervals (no reset until workout ends)
2. **Varied Workout Generation**: Workouts vary with inputs (duration, goals, constraints) instead of producing the same plan each time
3. **Regeneration**: Regeneration is possible after selecting a workout without overwriting history

## Features

### Domain Model

- **WorkoutTemplate**: Complete workout definition with segments and metadata
- **IntervalSegment**: Individual workout segments with speed, incline, and duration
- **RunSession**: Active workout session with server-authoritative timer state

### Timer Rules

- `elapsed_s` counts total run time across all intervals (minus pauses)
- `segment_elapsed_s` resets only on segment changes
- Segments advance when `segment_elapsed_s >= duration_s`
- On last segment completion, session is "completed"
- Uses monotonic clock for accuracy with server as source of truth

### API Endpoints

#### Workouts
- `POST /workouts/generate` → Create new workout template
- `GET /workouts/{id}` → Get workout template
- `POST /workouts/{id}/regenerate` → Create new template with same inputs, new seed

#### Sessions
- `POST /sessions` → Create new run session
- `POST /sessions/{id}/start` → Start session
- `POST /sessions/{id}/pause` → Pause session
- `POST /sessions/{id}/resume` → Resume session
- `POST /sessions/{id}/skip` → Skip to next segment
- `POST /sessions/{id}/back` → Go back to previous segment
- `GET /sessions/{id}` → Get authoritative timer state

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Backend

```bash
# Option 1: Using the run script
python run_backend_scaffold.py

# Option 2: Using uvicorn directly
uvicorn backend_scaffold:app --reload --port 8080
```

### 3. Access API Documentation

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

## Usage Examples

### Generate a Workout

```bash
curl -X POST "http://localhost:8080/workouts/generate" \
     -H "Content-Type: application/json" \
     -d '{"duration_min": 30, "seed": 12345}'
```

### Create and Start a Session

```bash
# Create session
curl -X POST "http://localhost:8080/sessions?workout_id=YOUR_WORKOUT_ID"

# Start session
curl -X POST "http://localhost:8080/sessions/YOUR_SESSION_ID/start"
```

### Get Session State

```bash
curl -X GET "http://localhost:8080/sessions/YOUR_SESSION_ID"
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest test_backend_scaffold.py -v

# Run specific test class
pytest test_backend_scaffold.py::TestTimerBehavior -v

# Run with coverage
pytest test_backend_scaffold.py --cov=backend_scaffold --cov-report=html
```

### Test Coverage

The test suite validates all acceptance criteria:

- ✅ Timer never resets to zero mid-run; only `segment_elapsed_s` resets
- ✅ Different input durations produce different workouts
- ✅ Same inputs + seed → identical plan; same inputs + different seed → different plan
- ✅ Regeneration after selection returns a new workout id; history remains

## Integration with Existing Flask App

This scaffold can run side-by-side with your existing Flask app during migration:

### Option 1: Reverse Proxy
```nginx
# nginx.conf
location /api/v2/ {
    proxy_pass http://localhost:8080/;
}
```

### Option 2: Mount in Flask
```python
# In your Flask app
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware

fastapi_app = FastAPI()
fastapi_app.mount("/api/v2", WSGIMiddleware(flask_app))
```

## Data Storage

Currently uses in-memory storage for simplicity. To persist data:

### SQLite Integration
```python
# Replace _WORKOUTS and _SESSIONS with SQLite operations
import sqlite3

def save_workout(workout: WorkoutTemplate):
    conn = sqlite3.connect('workouts.db')
    # ... SQL operations
```

### PostgreSQL Integration
```python
# Use SQLAlchemy or asyncpg for PostgreSQL
from sqlalchemy import create_engine
engine = create_engine('postgresql://user:pass@localhost/workouts')
```

## Development

### Adding New Features

1. **New Segment Types**: Add to `IntervalSegment.label` Literal type
2. **Enhanced Generation**: Modify `_generate_segments()` function
3. **Additional Endpoints**: Add new FastAPI route handlers

### Performance Considerations

- **Timer Accuracy**: Uses `time.monotonic()` for precise timing
- **Memory Usage**: In-memory storage suitable for development, consider persistence for production
- **Concurrency**: FastAPI handles concurrent requests efficiently

## Deployment

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "backend_scaffold:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Environment Variables
- `PORT`: Server port (default: 8080)
- `HOST`: Server host (default: 0.0.0.0)
- `RELOAD`: Enable auto-reload (default: true)

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
2. **Port Conflicts**: Change port in `run_backend_scaffold.py`
3. **Timer Drift**: Verify system clock and consider NTP synchronization

### Debug Mode

```bash
# Enable debug logging
RELOAD=true uvicorn backend_scaffold:app --log-level debug
```

## Contributing

1. Add tests for new features
2. Ensure all acceptance criteria pass
3. Update documentation for API changes
4. Follow FastAPI best practices

## License

Same as the main project.
