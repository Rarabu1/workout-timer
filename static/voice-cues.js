// Voice Cues Module - Text-to-Speech announcements

class VoiceCues {
  constructor() {
    this.enabled = false;
    this.synth = window.speechSynthesis;
    this.voice = null;
    this.volume = 0.8;
    this.rate = 1.0;
    this.pitch = 1.0;
    
    // Initialize voice
    this.initVoice();
  }
  
  initVoice() {
    if (!this.synth) {
      console.warn('Speech synthesis not supported');
      return;
    }
    
    // Wait for voices to load
    if (this.synth.getVoices().length === 0) {
      this.synth.addEventListener('voiceschanged', () => {
        this.selectVoice();
      });
    } else {
      this.selectVoice();
    }
  }
  
  selectVoice() {
    const voices = this.synth.getVoices();
    // Prefer English voices
    this.voice = voices.find(v => v.lang.startsWith('en')) || voices[0];
  }
  
  enable() {
    this.enabled = true;
  }
  
  disable() {
    this.enabled = false;
    this.cancel();
  }
  
  toggle() {
    this.enabled = !this.enabled;
    if (!this.enabled) {
      this.cancel();
    }
    return this.enabled;
  }
  
  speak(text) {
    if (!this.enabled || !this.synth) return;
    
    // Cancel any ongoing speech
    this.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.voice = this.voice;
    utterance.volume = this.volume;
    utterance.rate = this.rate;
    utterance.pitch = this.pitch;
    
    this.synth.speak(utterance);
  }
  
  cancel() {
    if (this.synth) {
      this.synth.cancel();
    }
  }
  
  // Preset announcements
  announceInterval(speed, duration, description = '') {
    const text = `${duration} minutes at ${speed} miles per hour${description ? '. ' + description : ''}`;
    this.speak(text);
  }
  
  announceCountdown(number) {
    this.speak(number.toString());
  }
  
  announceStart() {
    this.speak('Begin');
  }
  
  announceComplete() {
    this.speak('Workout complete');
  }
  
  announceWarning(secondsLeft) {
    this.speak(`${secondsLeft} seconds`);
  }
  
  announcePause() {
    this.speak('Paused');
  }
  
  announceResume() {
    this.speak('Resumed');
  }
}

export default VoiceCues;

