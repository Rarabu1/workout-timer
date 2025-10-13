// Main Timer Controller
// Handles workout timer logic for portrait mode

class MainTimerController {
  constructor() {
    this.intervals = [];
    this.currentIntervalIndex = 0;
    this.secondsRemaining = 0;
    this.timerInterval = null;
    this.isPaused = false;
    this.currentWorkoutText = '';
    
    this.initializeElements();
    this.attachEventListeners();
  }
  
  initializeElements() {
    // Timer elements
    this.timerEl = document.getElementById('timer');
    this.currentSpeedEl = document.getElementById('current-speed');
    this.currentInclineEl = document.getElementById('current-incline');
    this.intervalNumEl = document.getElementById('interval-num');
    this.currentDescriptionEl = document.getElementById('current-description');
    this.intervalsListEl = document.getElementById('intervals-list');
    
    // Button elements
    this.btnStart = document.getElementById('btn-start');
    this.btnPause = document.getElementById('btn-pause');
    this.btnResume = document.getElementById('btn-resume');
    this.btnPrev = document.getElementById('btn-prev');
    this.btnSkip = document.getElementById('btn-skip');
    this.btnStop = document.getElementById('btn-stop');
    this.btnSaveWorkout = document.getElementById('btn-save-workout');
    
    // Section elements
    this.timerSection = document.getElementById('timer-section');
    this.btnSaveContainer = document.getElementById('btn-save-workout-container');
  }
  
  attachEventListeners() {
    this.btnStart.addEventListener('click', () => this.start());
    this.btnPause.addEventListener('click', () => this.pause());
    this.btnResume.addEventListener('click', () => this.resume());
    this.btnPrev.addEventListener('click', () => this.previous());
    this.btnSkip.addEventListener('click', () => this.skip());
    this.btnStop.addEventListener('click', () => this.stop());
    this.btnSaveWorkout.addEventListener('click', () => this.saveWorkout());
  }
  
  loadWorkout(intervals) {
    this.intervals = intervals;
    this.currentIntervalIndex = 0;
    
    // Show timer section
    this.timerSection.classList.remove('hidden');
    
    // Render intervals list
    this.renderIntervalsList();
    
    // Load first interval
    this.loadInterval(0);
    
    // Show start button
    this.btnStart.classList.remove('hidden');
    this.btnPause.classList.add('hidden');
    this.btnResume.classList.add('hidden');
    
    // Scroll to timer
    this.timerSection.scrollIntoView({ behavior: 'smooth' });
  }
  
  renderIntervalsList() {
    this.intervalsListEl.innerHTML = this.intervals.map((interval, i) => `
      <div class="interval-item ${i === this.currentIntervalIndex ? 'current' : ''}" data-index="${i}">
        <span>${interval.duration_min} min @ ${interval.speed_mph} mph</span>
        <span>${interval.description || interval.section || ''}</span>
      </div>
    `).join('');
    
    // Make intervals clickable (when not running)
    this.intervalsListEl.querySelectorAll('.interval-item').forEach(item => {
      item.addEventListener('click', () => {
        if (!this.timerInterval) {
          const index = parseInt(item.dataset.index);
          this.loadInterval(index);
        }
      });
    });
  }
  
  loadInterval(index) {
    if (index < 0 || index >= this.intervals.length) return;
    
    this.currentIntervalIndex = index;
    const interval = this.intervals[index];
    
    this.secondsRemaining = interval.duration_min * 60;
    
    this.currentSpeedEl.textContent = interval.speed_mph;
    this.currentInclineEl.textContent = interval.incline || 0;
    this.intervalNumEl.textContent = `${index + 1}/${this.intervals.length}`;
    this.currentDescriptionEl.textContent = 
      interval.description || interval.section || 'Interval ' + (index + 1);
    
    this.updateTimerDisplay();
    this.renderIntervalsList();
  }
  
  updateTimerDisplay() {
    const minutes = Math.floor(this.secondsRemaining / 60);
    const seconds = this.secondsRemaining % 60;
    this.timerEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }
  
  start() {
    this.startTimer();
    this.btnStart.classList.add('hidden');
    this.btnPause.classList.remove('hidden');
  }
  
  pause() {
    this.pauseTimer();
    this.btnPause.classList.add('hidden');
    this.btnResume.classList.remove('hidden');
  }
  
  resume() {
    this.startTimer();
    this.btnResume.classList.add('hidden');
    this.btnPause.classList.remove('hidden');
  }
  
  previous() {
    if (this.currentIntervalIndex > 0) {
      this.stopTimer();
      this.loadInterval(this.currentIntervalIndex - 1);
    }
  }
  
  skip() {
    if (this.currentIntervalIndex < this.intervals.length - 1) {
      this.stopTimer();
      this.loadInterval(this.currentIntervalIndex + 1);
    }
  }
  
  stop() {
    if (confirm('Stop workout?')) {
      this.stopTimer();
      this.btnSaveContainer.classList.remove('hidden');
    }
  }
  
  startTimer() {
    if (this.timerInterval) clearInterval(this.timerInterval);
    
    this.timerInterval = setInterval(() => {
      this.secondsRemaining--;
      this.updateTimerDisplay();
      
      if (this.secondsRemaining <= 0) {
        // Move to next interval
        if (this.currentIntervalIndex < this.intervals.length - 1) {
          this.loadInterval(this.currentIntervalIndex + 1);
        } else {
          // Workout complete
          this.stopTimer();
          alert('Workout complete! 🎉');
          this.btnSaveContainer.classList.remove('hidden');
        }
      }
    }, 1000);
  }
  
  pauseTimer() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
  }
  
  stopTimer() {
    this.pauseTimer();
    this.btnStart.classList.remove('hidden');
    this.btnPause.classList.add('hidden');
    this.btnResume.classList.add('hidden');
  }
  
  async saveWorkout() {
    const description = prompt('Name this workout:');
    if (!description) return;
    
    try {
      const response = await fetch('/save_workout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description,
          intervals: this.intervals
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        alert('Workout saved!');
        this.btnSaveContainer.classList.add('hidden');
      } else {
        alert('Error saving: ' + data.error);
      }
    } catch (error) {
      alert('Failed to save: ' + error.message);
    }
  }
  
  // Public API
  getState() {
    return {
      intervals: this.intervals,
      currentIntervalIndex: this.currentIntervalIndex,
      secondsRemaining: this.secondsRemaining,
      isRunning: !!this.timerInterval
    };
  }
  
  setState(state) {
    this.intervals = state.intervals;
    this.currentIntervalIndex = state.currentIntervalIndex;
    this.secondsRemaining = state.secondsRemaining;
    this.loadInterval(this.currentIntervalIndex);
  }
}

export default MainTimerController;

