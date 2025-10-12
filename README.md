# 🏃 Treadmill Workout Timer

A simplified, focused treadmill workout timer with AI-powered workout generation and automatic landscape Focus Mode.

## ✨ Features

### Core Features
- **AI Workout Generation**: Generate custom workouts using OpenAI GPT
- **Manual Entry**: Paste or type workouts in natural format
- **Interval Timer**: Precise timing with play/pause/skip controls  
- **Save & Load**: Store your favorite workouts
- **Mobile PWA**: Install on your phone as an app

### 🎯 Focus Timer Mode (NEW!)
Automatic distraction-free mode when device is in landscape:
- **Huge Clock**: Primary focus on time remaining
- **Intensity Colors**: Background changes based on effort level
- **Smart Metrics**: Speed, incline, interval #, total time
- **Voice Cues**: Optional audio announcements (toggle with 🔊)
- **3-2-1 Countdown**: Visual countdown when starting intervals
- **Progress Bars**: See segment and total workout progress
- **Wake Lock**: Prevents screen from dimming
- **Haptics**: Vibration alerts in last 5 seconds
- **Keyboard**: Space = pause/resume, Esc = exit

**Simply rotate your phone to landscape and Focus Mode activates automatically!**

## 🚀 Quick Start

### Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (copy env_template.txt to .env)
FLASK_SECRET_KEY=your_secret_key
OPENAI_API_KEY=your_openai_key

# Run the app
python app.py
```

Visit `http://localhost:5000`

### Deploy to Render

1. Connect your GitHub repo to Render
2. Set environment variables:
   - `OPENAI_API_KEY` - for AI workout generation
   - `FLASK_SECRET_KEY` - any random string
3. Start command: `gunicorn app:app`
4. Deploy!

## 📱 Usage

### Generate a Workout

**Option 1: Random Workout (Fastest!)**
1. Go to **AI Workout** tab
2. Click **🎲 Random Workout** - Done!
3. Click **Use This Workout**
4. Hit **Start** when ready

**Option 2: AI Custom Workout**
1. Go to **AI Workout** tab
2. Enter prompt: "30 minute tempo run with intervals"
3. Click **Generate Workout**
4. Click **Use This Workout**
5. Hit **Start** when ready

### Manual Entry
1. Go to **Manual Entry** tab
2. Paste workout in format:
```
**Warm-Up – 5 minutes**
* 5 min @ 4.0 mph

**Main Set – 20 minutes**
* 3 min @ 6.5 mph (tempo)
* 2 min @ 5.0 mph (recovery)
```
3. Click **Parse & Start**

### Focus Mode
1. Start any workout
2. Rotate phone to landscape
3. **Focus Mode activates automatically!**
4. Tap 🔊 to enable voice cues
5. Rotate back to portrait to exit

## 🎨 Intensity Colors

| Speed | Intensity | Color |
|-------|-----------|-------|
| < 4.5 mph | Recovery | 🟢 Green |
| 4.5-5.5 mph | Easy | 🟢 Light Green |
| 5.5-6.5 mph | Moderate | 🟠 Orange |
| 6.5-7.5 mph | Hard | 🟠 Dark Orange |
| > 7.5 mph | Max | 🔴 Red |

All colors meet WCAG AA accessibility standards.

## 🔧 Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: Vanilla HTML/CSS/JavaScript
- **AI**: OpenAI GPT-4o-mini
- **Database**: SQLite
- **Deployment**: Render + Gunicorn

## 📂 Project Structure

```
workout_timer/
├── app.py                      # Flask backend (227 lines)
├── templates/
│   └── index.html              # Main UI with Focus Mode
├── static/
│   ├── orientation.js          # Orientation detection
│   ├── intensity-colors.js     # Color mapping + contrast
│   ├── focus-timer.js          # Timer state machine
│   ├── voice-cues.js           # Text-to-speech
│   ├── app-icon.svg
│   ├── logo.svg
│   └── manifest.json
├── docs/
│   └── focus-timer.md          # Focus Mode documentation
├── workout_parser.py           # Workout text parser
├── workouts.db                 # SQLite database
├── requirements.txt            # Python dependencies
└── README.md
```

## 🎯 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main app |
| `/parse` | POST | Parse workout text |
| `/save_workout` | POST | Save workout to database |
| `/workouts` | GET | Get all saved workouts |
| `/load_workout/<id>` | GET | Load specific workout |
| `/generate_workout` | POST | Generate AI workout |

## 🔐 Environment Variables

```bash
# Required for AI generation
OPENAI_API_KEY=sk-...

# Required for Flask
FLASK_SECRET_KEY=your-secret-key-here

# Optional
FLASK_DEBUG=0  # Set to 1 for development
PORT=5000      # Default port
```

## 📖 Documentation

- [Focus Timer Mode Documentation](docs/focus-timer.md) - Complete guide to Focus Mode
- [Workout Format Guide](#manual-entry) - How to format workouts
- [API Documentation](#api-endpoints) - Backend API reference

## 🧪 Browser Support

| Browser | Orientation | Wake Lock | Haptics | Voice |
|---------|-------------|-----------|---------|-------|
| iOS Safari 14+ | ✅ | ✅ | ⚠️ | ✅ |
| Android Chrome 80+ | ✅ | ✅ | ✅ | ✅ |
| Firefox Mobile | ✅ | ⚠️ | ✅ | ✅ |
| Desktop Browsers | ✅ | ✅ | ❌ | ✅ |

## 🎨 Features Comparison

**Before (3,198 lines)**:
- ❌ WHOOP integration
- ❌ Socket.IO real-time updates
- ❌ ML/AI analytics
- ❌ Complex progress tracking
- ❌ Security monitoring
- ❌ Test scaffolding

**After (227 lines)**:
- ✅ AI workout generation
- ✅ Interval timer
- ✅ Focus Mode (landscape)
- ✅ Voice cues
- ✅ Save/load workouts
- ✅ Wake Lock
- ✅ Haptics
- ✅ WCAG AA accessibility

**93% smaller, 100% focused!**

## 🚀 Deployment

### Render
1. Push to GitHub
2. Connect to Render
3. Set environment variables
4. Deploy automatically on push

### Other Platforms
Works on any platform that supports:
- Python 3.11+
- Gunicorn
- Environment variables

## 📝 License

See [LICENSE](LICENSE) file for details.

## 🤝 Contributing

This is a simplified, personal workout timer. Fork it and make it your own!

## 💡 Tips

### For Best Experience:
1. Use in landscape for Focus Mode
2. Enable voice cues for hands-free coaching
3. Keep phone plugged in during long workouts
4. Save your favorite workouts for quick access
5. Try different AI prompts for variety

### Workout Prompt Ideas:
- "30 minute progressive tempo run"
- "20 minute hill workout with recovery"
- "45 minute endurance base building"
- "15 minute HIIT sprint intervals"
- "40 minute race pace simulation"

## 🔮 Future Ideas

- Heart rate integration (Apple Watch / WHOOP)
- Spotify integration for music control
- Workout history & analytics
- Custom intensity colors
- Apple Health export
- Workout sharing

---

**Made with ❤️ for treadmill runners**

Simple. Focused. Effective.

