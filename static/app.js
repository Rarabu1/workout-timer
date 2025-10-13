// Main Application Entry Point
// Ties together all modules

import MainTimerController from './main-timer.js';
import { UIController, ManualWorkoutParser } from './ui-controller.js';
import orientationDetector from './orientation.js';
import FocusTimer from './focus-timer.js';
import VoiceCues from './voice-cues.js';

class WorkoutTimerApp {
  constructor() {
    // Initialize controllers
    this.mainTimer = new MainTimerController();
    this.uiController = new UIController(this.mainTimer);
    this.manualParser = new ManualWorkoutParser(this.mainTimer);
    
    // Initialize Focus Mode
    this.focusTimer = new FocusTimer();
    this.voiceCues = new VoiceCues();
    this.focusModeActive = false;
    this.toastShown = false;
    
    this.initializeFocusMode();
    
    // Expose to window for debugging
    window.app = this;
  }
  
  initializeFocusMode() {
    // Focus Mode DOM elements
    this.focusMode = document.getElementById('focus-mode');
    this.focusClock = document.getElementById('focus-clock');
    this.focusSpeed = document.getElementById('focus-speed');
    this.focusSpeedLabel = document.getElementById('focus-speed-label');
    this.focusIncline = document.getElementById('focus-incline');
    this.focusInterval = document.getElementById('focus-interval');
    this.focusTotal = document.getElementById('focus-total');
    this.focusSegmentProgress = document.getElementById('focus-segment-progress');
    this.focusRunProgress = document.getElementById('focus-run-progress');
    this.focusPauseBtn = document.getElementById('focus-pause-btn');
    this.focusPauseIcon = document.getElementById('focus-pause-icon');
    this.focusExitBtn = document.getElementById('focus-exit-btn');
    this.focusVoiceBtn = document.getElementById('focus-voice-btn');
    this.focusVoiceIcon = document.getElementById('focus-voice-icon');
    this.focusToast = document.getElementById('focus-toast');
    this.focusCountdown = document.getElementById('focus-countdown');
    
    let previousIntervalIndex = -1;
    
    // Update focus mode when timer state changes
    this.focusTimer.onChange(state => {
      if (!this.focusModeActive) return;
      
      this.updateFocusMode(state);
      
      // Detect interval change
      if (state.currentIntervalIndex !== previousIntervalIndex) {
        this.handleIntervalChange(state);
        previousIntervalIndex = state.currentIntervalIndex;
      }
      
      // Voice warning at 10 seconds
      if (state.segmentRemainingSec <= 10 && 
          state.segmentRemainingSec > 9.5 && 
          state.state === 'running') {
        this.voiceCues.announceWarning(10);
      }
    });
    
    // Orientation change handler
    orientationDetector.onChange(({ isLandscape }) => {
      if (isLandscape && this.mainTimer.intervals.length > 0) {
        this.enterFocusMode();
      } else if (!isLandscape && this.focusModeActive) {
        this.exitFocusMode();
      }
    });
    
    // Check initial orientation
    if (orientationDetector.getState().isLandscape && this.mainTimer.intervals.length > 0) {
      this.enterFocusMode();
    }
    
    // Focus Mode Controls
    this.focusPauseBtn.addEventListener('click', () => {
      if (this.focusTimer.state === 'idle') {
        this.focusTimer.start();
      } else {
        this.focusTimer.togglePause();
      }
      this.updateFocusMode(this.focusTimer.getState());
    });
    
    this.focusExitBtn.addEventListener('click', () => {
      this.exitFocusMode();
    });
    
    this.focusVoiceBtn.addEventListener('click', () => {
      const enabled = this.voiceCues.toggle();
      this.focusVoiceIcon.textContent = enabled ? '🔊' : '🔇';
    });
    
    // Keyboard controls
    document.addEventListener('keydown', (e) => {
      if (!this.focusModeActive) return;
      
      if (e.key === ' ' || e.key === 'Spacebar') {
        e.preventDefault();
        this.focusPauseBtn.click();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        this.exitFocusMode();
      }
    });
    
    // Allow clicking on speed to toggle mph/kph
    document.getElementById('focus-speed-metric').addEventListener('click', () => {
      this.focusTimer.toggleUnitSystem();
    });
  }
  
  handleIntervalChange(state) {
    if (this.countdownActive) return;
    
    const interval = state.interval;
    if (!interval) return;
    
    // Announce new interval
    this.voiceCues.announceInterval(
      state.speed,
      interval.duration_min,
      interval.description || ''
    );
    
    // Show 3-2-1 countdown
    this.showCountdown();
  }
  
  showCountdown() {
    if (this.countdownActive) return;
    this.countdownActive = true;
    
    const numbers = [3, 2, 1, 'GO!'];
    let index = 0;
    
    const showNext = () => {
      if (index >= numbers.length) {
        this.focusCountdown.classList.add('hidden');
        this.countdownActive = false;
        return;
      }
      
      const num = numbers[index];
      this.focusCountdown.textContent = num;
      this.focusCountdown.classList.remove('hidden');
      
      // Voice announcement
      if (typeof num === 'number') {
        this.voiceCues.announceCountdown(num);
      } else {
        this.voiceCues.announceStart();
      }
      
      // Trigger animation by forcing reflow
      this.focusCountdown.style.animation = 'none';
      setTimeout(() => {
        this.focusCountdown.style.animation = '';
      }, 10);
      
      index++;
      setTimeout(showNext, 1000);
    };
    
    showNext();
  }
  
  updateFocusMode(state) {
    // Update clock
    this.focusClock.textContent = this.focusTimer.formatTime(state.segmentRemainingSec);
    
    // Update metrics
    this.focusSpeed.textContent = state.speed;
    this.focusSpeedLabel.textContent = state.unitSystem.toUpperCase();
    this.focusIncline.textContent = state.incline;
    this.focusInterval.textContent = `${state.currentIntervalIndex + 1}/${state.totalIntervals}`;
    this.focusTotal.textContent = this.focusTimer.formatTime(state.runRemainingSec);
    
    // Update progress bars
    this.focusSegmentProgress.style.width = `${state.progressSegment}%`;
    this.focusRunProgress.style.width = `${state.progressRun}%`;
    
    // Update background color based on intensity
    const colors = state.colors;
    this.focusMode.style.backgroundColor = colors.bg;
    this.focusMode.style.color = colors.fg;
    
    // Update metric cards
    const metrics = document.querySelectorAll('.focus-metric');
    metrics.forEach(metric => {
      metric.style.backgroundColor = colors.subtle;
      metric.style.color = colors.fg;
    });
    
    // Update buttons
    const buttons = document.querySelectorAll('.focus-btn');
    buttons.forEach(btn => {
      btn.style.backgroundColor = colors.subtle;
      btn.style.color = colors.fg;
    });
    
    // Update toast
    this.focusToast.style.backgroundColor = colors.subtle;
    this.focusToast.style.color = colors.fg;
    
    // Update pause icon
    if (state.state === 'idle') {
      this.focusPauseIcon.textContent = '▶️';
      this.focusPauseBtn.title = 'Start (Space)';
    } else if (state.state === 'running') {
      this.focusPauseIcon.textContent = '⏸';
      this.focusPauseBtn.title = 'Pause (Space)';
    } else {
      this.focusPauseIcon.textContent = '▶️';
      this.focusPauseBtn.title = 'Resume (Space)';
    }
  }
  
  enterFocusMode() {
    if (this.focusModeActive || this.mainTimer.intervals.length === 0) return;
    
    this.focusModeActive = true;
    this.focusMode.classList.add('active');
    
    // Sync focus timer with main timer state
    const state = this.mainTimer.getState();
    this.focusTimer.load(state.intervals);
    this.focusTimer.currentIntervalIndex = state.currentIntervalIndex;
    this.focusTimer.segmentRemainingSec = state.secondsRemaining;
    this.focusTimer.calculateRemaining();
    
    // Show toast on first time
    if (!this.toastShown) {
      this.focusToast.classList.remove('hidden');
      setTimeout(() => this.focusToast.classList.add('hidden'), 3000);
      this.toastShown = true;
    }
    
    // Update display
    this.updateFocusMode(this.focusTimer.getState());
    
    // Auto-start if main timer is running
    if (state.isRunning) {
      this.mainTimer.pauseTimer();
      this.focusTimer.start();
    }
  }
  
  exitFocusMode() {
    if (!this.focusModeActive) return;
    
    this.focusModeActive = false;
    this.focusMode.classList.add('hidden');
    
    // Sync main timer with focus timer state
    const state = this.focusTimer.getState();
    this.mainTimer.setState({
      intervals: state.interval ? this.focusTimer.intervals : this.mainTimer.intervals,
      currentIntervalIndex: state.currentIntervalIndex,
      secondsRemaining: Math.ceil(state.segmentRemainingSec)
    });
    
    // Transfer control back to main timer if running
    if (state.state === 'running') {
      this.focusTimer.pause();
      this.mainTimer.start();
    }
    
    // Hide focus mode after transition
    setTimeout(() => {
      this.focusMode.classList.remove('active');
    }, 300);
  }
}

// Initialize app when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    new WorkoutTimerApp();
  });
} else {
  new WorkoutTimerApp();
}

