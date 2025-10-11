// Focus Timer Module - Precise timing with state machine

import { getIntensityColors, speedToIntensity } from './intensity-colors.js';

class FocusTimer {
  constructor() {
    this.state = 'idle'; // idle, running, paused, segment_done, complete
    this.intervals = [];
    this.currentIntervalIndex = 0;
    this.segmentRemainingSec = 0;
    this.runRemainingSec = 0;
    this.lastTickTime = null;
    this.rafId = null;
    this.listeners = [];
    this.unitSystem = 'mph'; // mph or kph
    
    // Wake Lock API
    this.wakeLock = null;
    this.supportsWakeLock = 'wakeLock' in navigator;
    
    // Haptics
    this.supportsHaptics = 'vibrate' in navigator;
    this.hapticTriggered = false;
  }
  
  load(intervals) {
    this.intervals = intervals.map(interval => ({
      ...interval,
      duration_sec: interval.duration_min * 60,
      intensity: speedToIntensity(interval.speed_mph)
    }));
    
    this.currentIntervalIndex = 0;
    this.calculateRemaining();
    this.state = 'idle';
    this.notifyListeners();
  }
  
  calculateRemaining() {
    if (this.intervals.length === 0) {
      this.segmentRemainingSec = 0;
      this.runRemainingSec = 0;
      return;
    }
    
    this.segmentRemainingSec = this.intervals[this.currentIntervalIndex]?.duration_sec || 0;
    
    // Calculate total remaining time
    this.runRemainingSec = this.segmentRemainingSec;
    for (let i = this.currentIntervalIndex + 1; i < this.intervals.length; i++) {
      this.runRemainingSec += this.intervals[i].duration_sec;
    }
  }
  
  start() {
    if (this.state === 'running') return;
    
    this.state = 'running';
    this.lastTickTime = performance.now();
    this.hapticTriggered = false;
    this.requestWakeLock();
    this.tick();
    this.notifyListeners();
  }
  
  pause() {
    if (this.state !== 'running') return;
    
    this.state = 'paused';
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    this.releaseWakeLock();
    this.notifyListeners();
  }
  
  resume() {
    if (this.state !== 'paused') return;
    this.start();
  }
  
  togglePause() {
    if (this.state === 'running') {
      this.pause();
    } else if (this.state === 'paused') {
      this.resume();
    }
  }
  
  tick() {
    if (this.state !== 'running') return;
    
    const now = performance.now();
    const deltaMs = now - this.lastTickTime;
    const deltaSec = deltaMs / 1000;
    
    this.lastTickTime = now;
    
    // Update remaining time
    this.segmentRemainingSec = Math.max(0, this.segmentRemainingSec - deltaSec);
    this.runRemainingSec = Math.max(0, this.runRemainingSec - deltaSec);
    
    // Haptics in last 5 seconds
    if (this.segmentRemainingSec <= 5 && this.segmentRemainingSec > 0 && !this.hapticTriggered) {
      this.triggerHaptics();
      this.hapticTriggered = true;
    }
    
    // Check if segment is complete
    if (this.segmentRemainingSec <= 0) {
      this.handleSegmentComplete();
      return;
    }
    
    this.notifyListeners();
    this.rafId = requestAnimationFrame(() => this.tick());
  }
  
  handleSegmentComplete() {
    // Move to next interval
    if (this.currentIntervalIndex < this.intervals.length - 1) {
      this.currentIntervalIndex++;
      this.calculateRemaining();
      this.hapticTriggered = false;
      this.state = 'segment_done';
      this.notifyListeners();
      
      // Auto-continue after brief pause
      setTimeout(() => {
        if (this.state === 'segment_done') {
          this.start();
        }
      }, 500);
    } else {
      // Workout complete
      this.state = 'complete';
      this.releaseWakeLock();
      this.notifyListeners();
      this.triggerHaptics('long');
    }
  }
  
  skip() {
    if (this.currentIntervalIndex < this.intervals.length - 1) {
      this.currentIntervalIndex++;
      this.calculateRemaining();
      this.hapticTriggered = false;
      this.notifyListeners();
    }
  }
  
  previous() {
    if (this.currentIntervalIndex > 0) {
      this.currentIntervalIndex--;
      this.calculateRemaining();
      this.hapticTriggered = false;
      this.notifyListeners();
    }
  }
  
  stop() {
    this.state = 'idle';
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    this.releaseWakeLock();
    this.notifyListeners();
  }
  
  setUnitSystem(system) {
    this.unitSystem = system;
    this.notifyListeners();
  }
  
  toggleUnitSystem() {
    this.unitSystem = this.unitSystem === 'mph' ? 'kph' : 'mph';
    this.notifyListeners();
  }
  
  // Wake Lock API
  async requestWakeLock() {
    if (!this.supportsWakeLock) return;
    
    try {
      this.wakeLock = await navigator.wakeLock.request('screen');
      console.log('Wake Lock activated');
    } catch (err) {
      console.warn('Wake Lock failed:', err);
    }
  }
  
  async releaseWakeLock() {
    if (this.wakeLock) {
      try {
        await this.wakeLock.release();
        this.wakeLock = null;
        console.log('Wake Lock released');
      } catch (err) {
        console.warn('Wake Lock release failed:', err);
      }
    }
  }
  
  // Haptics
  triggerHaptics(pattern = 'short') {
    if (!this.supportsHaptics) return;
    
    const patterns = {
      short: [50],
      long: [200],
      double: [50, 100, 50]
    };
    
    try {
      navigator.vibrate(patterns[pattern] || patterns.short);
    } catch (err) {
      console.warn('Haptics failed:', err);
    }
  }
  
  // State getters
  getCurrentInterval() {
    return this.intervals[this.currentIntervalIndex] || null;
  }
  
  getProgressSegment() {
    const interval = this.getCurrentInterval();
    if (!interval) return 0;
    return ((interval.duration_sec - this.segmentRemainingSec) / interval.duration_sec) * 100;
  }
  
  getProgressRun() {
    const totalDuration = this.intervals.reduce((sum, int) => sum + int.duration_sec, 0);
    if (totalDuration === 0) return 0;
    return ((totalDuration - this.runRemainingSec) / totalDuration) * 100;
  }
  
  getSpeed() {
    const interval = this.getCurrentInterval();
    if (!interval) return 0;
    
    if (this.unitSystem === 'kph') {
      return (interval.speed_mph * 1.60934).toFixed(1);
    }
    return interval.speed_mph.toFixed(1);
  }
  
  getIncline() {
    const interval = this.getCurrentInterval();
    return interval?.incline || 0;
  }
  
  getIntensityColors() {
    const interval = this.getCurrentInterval();
    if (!interval) return getIntensityColors(3);
    return getIntensityColors(interval.intensity);
  }
  
  formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }
  
  getState() {
    return {
      state: this.state,
      currentIntervalIndex: this.currentIntervalIndex,
      totalIntervals: this.intervals.length,
      segmentRemainingSec: this.segmentRemainingSec,
      runRemainingSec: this.runRemainingSec,
      progressSegment: this.getProgressSegment(),
      progressRun: this.getProgressRun(),
      speed: this.getSpeed(),
      incline: this.getIncline(),
      unitSystem: this.unitSystem,
      colors: this.getIntensityColors(),
      interval: this.getCurrentInterval()
    };
  }
  
  onChange(callback) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter(cb => cb !== callback);
    };
  }
  
  notifyListeners() {
    const state = this.getState();
    this.listeners.forEach(callback => callback(state));
  }
}

export default FocusTimer;

