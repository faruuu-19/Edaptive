/** Alarm for an armed, open demo tab. No notification or microphone permission. */
export class LocalAlarm {
  private context = new AudioContext();
  private timer: ReturnType<typeof setInterval> | null = null;
  private tones = new Set<OscillatorNode>();
  async unlock() { await this.context.resume(); }
  ring() {
    if (this.timer) return;
    const chime = () => {
      [440, 660].forEach((frequency, i) => {
        const tone = this.context.createOscillator(); const gain = this.context.createGain();
        const at = this.context.currentTime + i * 0.23;
        tone.frequency.value = frequency; tone.connect(gain); gain.connect(this.context.destination);
        gain.gain.setValueAtTime(0, at); gain.gain.linearRampToValueAtTime(0.06, at + 0.015);
        gain.gain.exponentialRampToValueAtTime(0.001, at + 0.18);
        tone.start(at); tone.stop(at + 0.2); this.tones.add(tone);
        tone.onended = () => { this.tones.delete(tone); tone.disconnect(); gain.disconnect(); };
      });
    };
    chime(); this.timer = setInterval(chime, 2000);
  }
  stop() {
    if (this.timer) clearInterval(this.timer); this.timer = null;
    for (const tone of this.tones) { tone.onended = null; tone.stop(); tone.disconnect(); }
    this.tones.clear();
  }
  close() { this.stop(); void this.context.close(); }
}
