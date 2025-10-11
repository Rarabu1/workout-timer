// Orientation Detection Module
// Reliable orientation detection for iOS Safari + Android Chrome

class OrientationDetector {
  constructor() {
    this.listeners = [];
    this.isLandscape = false;
    this.isPortrait = true;
    this.orientationType = 'portrait-primary';
    this.initialized = false;
    
    // Debounce resize events
    this.debounceTimer = null;
    this.debounceDelay = 150;
  }
  
  init() {
    if (this.initialized) return;
    this.initialized = true;
    
    // Initial detection
    this.detect();
    
    // Listen to orientation changes (multiple methods for cross-browser support)
    window.addEventListener('orientationchange', () => this.handleChange());
    window.addEventListener('resize', () => this.handleChange());
    
    // Modern Screen Orientation API
    if (window.screen?.orientation) {
      window.screen.orientation.addEventListener('change', () => this.handleChange());
    }
  }
  
  handleChange() {
    // Debounce to avoid multiple rapid calls
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => {
      const prevLandscape = this.isLandscape;
      this.detect();
      
      // Only notify if changed
      if (prevLandscape !== this.isLandscape) {
        this.notifyListeners();
      }
    }, this.debounceDelay);
  }
  
  detect() {
    // Method 1: Screen Orientation API (most reliable)
    if (window.screen?.orientation?.type) {
      this.orientationType = window.screen.orientation.type;
      this.isLandscape = this.orientationType.includes('landscape');
      this.isPortrait = !this.isLandscape;
      return;
    }
    
    // Method 2: window.orientation (iOS Safari fallback)
    if (typeof window.orientation !== 'undefined') {
      const angle = window.orientation;
      this.isLandscape = Math.abs(angle) === 90;
      this.isPortrait = !this.isLandscape;
      this.orientationType = this.isLandscape ? 'landscape-primary' : 'portrait-primary';
      return;
    }
    
    // Method 3: window dimensions (final fallback)
    this.isLandscape = window.innerWidth > window.innerHeight;
    this.isPortrait = !this.isLandscape;
    this.orientationType = this.isLandscape ? 'landscape-primary' : 'portrait-primary';
  }
  
  onChange(callback) {
    this.listeners.push(callback);
    // Return unsubscribe function
    return () => {
      this.listeners = this.listeners.filter(cb => cb !== callback);
    };
  }
  
  notifyListeners() {
    this.listeners.forEach(callback => {
      callback({
        isLandscape: this.isLandscape,
        isPortrait: this.isPortrait,
        orientationType: this.orientationType
      });
    });
  }
  
  getState() {
    return {
      isLandscape: this.isLandscape,
      isPortrait: this.isPortrait,
      orientationType: this.orientationType
    };
  }
}

// Export singleton instance
const orientationDetector = new OrientationDetector();

// SSR-safe initialization
if (typeof window !== 'undefined') {
  orientationDetector.init();
}

export default orientationDetector;

