// UI Controller
// Handles tabs, workout generation, and saved workouts

import MainTimerController from './main-timer.js';

class UIController {
  constructor(timerController) {
    this.timer = timerController;
    this.currentWorkoutText = '';
    
    this.initializeTabs();
    this.initializeWorkoutGeneration();
    this.initializeSavedWorkouts();
  }
  
  initializeTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const tabName = tab.dataset.tab;
        
        // Update active tab
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        
        // Update active content
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.getElementById(`${tabName}-tab`).classList.add('active');
        
        // Load saved workouts if that tab is selected
        if (tabName === 'saved') {
          this.loadSavedWorkouts();
        }
      });
    });
  }
  
  initializeWorkoutGeneration() {
    // Random workout generator
    document.getElementById('btn-random').addEventListener('click', async () => {
      await this.generateRandomWorkout();
    });
    
    // AI workout generator
    document.getElementById('btn-generate').addEventListener('click', async () => {
      await this.generateAIWorkout();
    });
    
    // Use generated workout
    document.getElementById('btn-use-generated').addEventListener('click', () => {
      const intervals = this.timer.intervals;
      if (intervals.length > 0) {
        this.timer.loadWorkout(intervals);
      }
    });
  }
  
  initializeSavedWorkouts() {
    // Load saved workouts on startup
    this.loadSavedWorkouts();
  }
  
  async generateRandomWorkout() {
    const btn = document.getElementById('btn-random');
    btn.disabled = true;
    const originalText = btn.textContent;
    btn.textContent = '🎲 Generating...';
    
    try {
      const workoutText = this.createRandomWorkout();
      
      // Parse it
      const response = await fetch('/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: workoutText })
      });
      
      const data = await response.json();
      
      if (data.success && data.intervals.length > 0) {
        this.currentWorkoutText = workoutText;
        this.timer.intervals = data.intervals;
        
        document.getElementById('generated-text').textContent = workoutText;
        document.getElementById('generated-output').classList.remove('hidden');
      } else {
        alert('Error: ' + (data.error || 'No intervals generated'));
      }
    } catch (error) {
      alert('Failed to generate random workout: ' + error.message);
    } finally {
      btn.disabled = false;
      btn.textContent = originalText;
    }
  }
  
  createRandomWorkout() {
    const durations = [20, 25, 30, 35, 40, 45];
    const duration = durations[Math.floor(Math.random() * durations.length)];
    
    const workoutTypes = [
      { name: 'Tempo Run', warmup: 5, cooldown: 5, intervals: [[5, 6.5], [3, 5.5], [5, 6.8], [3, 5.5], [4, 7.0]] },
      { name: 'Progressive Run', warmup: 5, cooldown: 5, intervals: [[5, 5.5], [5, 6.0], [5, 6.5], [5, 7.0]] },
      { name: 'Interval Training', warmup: 5, cooldown: 5, intervals: [[2, 7.5], [2, 5.0], [2, 7.5], [2, 5.0], [2, 7.5], [2, 5.0]] },
      { name: 'Endurance Base', warmup: 5, cooldown: 5, intervals: [[10, 5.8], [5, 6.2], [10, 5.8]] },
      { name: 'Hill Workout', warmup: 5, cooldown: 5, intervals: [[3, 5.5, 3], [2, 5.0, 0], [3, 5.5, 4], [2, 5.0, 0], [3, 5.5, 5]] }
    ];
    
    const workout = workoutTypes[Math.floor(Math.random() * workoutTypes.length)];
    
    // Build workout text
    let text = `**${workout.name} – ${duration} minutes**\n\n`;
    text += `**Warm-Up – ${workout.warmup} minutes**\n`;
    text += `* ${workout.warmup} min @ 4.0 mph (easy pace)\n\n`;
    text += `**Main Set – ${duration - workout.warmup - workout.cooldown} minutes**\n`;
    
    workout.intervals.forEach(([mins, speed, incline]) => {
      text += `* ${mins} min @ ${speed} mph`;
      if (incline) text += ` (${incline}% incline)`;
      text += '\n';
    });
    
    text += `\n**Cool-Down – ${workout.cooldown} minutes**\n`;
    text += `* ${workout.cooldown} min @ 4.0 mph (easy recovery)\n`;
    
    return text;
  }
  
  async generateAIWorkout() {
    const prompt = document.getElementById('workout-prompt').value.trim();
    if (!prompt) {
      alert('Please enter a workout description');
      return;
    }
    
    const btn = document.getElementById('btn-generate');
    btn.disabled = true;
    btn.textContent = 'Generating...';
    
    try {
      const response = await fetch('/generate_workout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt })
      });
      
      const data = await response.json();
      
      if (data.success) {
        this.currentWorkoutText = data.workout_text;
        this.timer.intervals = data.intervals;
        
        document.getElementById('generated-text').textContent = data.workout_text;
        document.getElementById('generated-output').classList.remove('hidden');
      } else {
        alert('Error: ' + data.error);
      }
    } catch (error) {
      alert('Failed to generate workout: ' + error.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Generate Workout';
    }
  }
  
  async loadSavedWorkouts() {
    const container = document.getElementById('saved-workouts-list');
    container.innerHTML = '<div class="loading">Loading...</div>';
    
    try {
      const response = await fetch('/workouts');
      const workouts = await response.json();
      
      if (workouts.length === 0) {
        container.innerHTML = '<div class="loading">No saved workouts yet</div>';
        return;
      }
      
      container.innerHTML = workouts.map(workout => `
        <div class="workout-item" data-id="${workout.id}">
          <h3>${workout.description}</h3>
          <p>${workout.intervals.length} intervals • ${workout.created_at}</p>
        </div>
      `).join('');
      
      // Make workouts clickable
      container.querySelectorAll('.workout-item').forEach(item => {
        item.addEventListener('click', async () => {
          const id = item.dataset.id;
          try {
            const response = await fetch(`/load_workout/${id}`);
            const data = await response.json();
            
            if (data.success) {
              this.timer.loadWorkout(data.workout.intervals);
              // Switch to generate tab to show the workout
              document.querySelector('.tab[data-tab="generate"]').click();
            }
          } catch (error) {
            alert('Error loading workout: ' + error.message);
          }
        });
      });
    } catch (error) {
      container.innerHTML = '<div class="loading">Error loading workouts</div>';
    }
  }
}

// Manual workout parser
class ManualWorkoutParser {
  constructor(timerController) {
    this.timer = timerController;
    this.initializeParser();
  }
  
  initializeParser() {
    document.getElementById('btn-parse').addEventListener('click', async () => {
      const text = document.getElementById('workout-text').value.trim();
      if (!text) {
        alert('Please enter a workout');
        return;
      }
      
      try {
        const response = await fetch('/parse', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        
        const data = await response.json();
        
        if (data.success && data.intervals.length > 0) {
          this.timer.loadWorkout(data.intervals);
        } else {
          alert('No intervals found. Check your format.');
        }
      } catch (error) {
        alert('Error parsing workout: ' + error.message);
      }
    });
  }
}

export { UIController, ManualWorkoutParser };

