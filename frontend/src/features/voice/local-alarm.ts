/** Local class chime. Browser audio is unlocked by a gesture on this device. */
export class LocalAlarm {
  private context: AudioContext | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private tones = new Set<OscillatorNode>();
  private wanted = false;
  get unlocked() { return this.context?.state === 'running'; }
  async unlock() {
    try {
      this.context ??= new AudioContext();
      await this.context.resume();
      if (this.wanted) this.ring();
    } catch { /* A later tap can retry if the browser blocks this one. */ }
    return this.unlocked;
  }
  ring() {
    this.wanted = true;
    if (!this.unlocked || this.timer) return this.unlocked;
    const context = this.context!;
    const chime = () => {
      [440, 660].forEach((frequency, i) => {
        const tone = context.createOscillator(); const gain = context.createGain();
        const at = context.currentTime + i * 0.23;
        tone.frequency.value = frequency; tone.connect(gain); gain.connect(context.destination);
        gain.gain.setValueAtTime(0, at); gain.gain.linearRampToValueAtTime(0.06, at + 0.015);
        gain.gain.exponentialRampToValueAtTime(0.001, at + 0.18);
        tone.start(at); tone.stop(at + 0.2); this.tones.add(tone);
        tone.onended = () => { this.tones.delete(tone); tone.disconnect(); gain.disconnect(); };
      });
    };
    chime(); this.timer = setInterval(chime, 2000);
    return true;
  }
  stop() {
    this.wanted = false;
    if (this.timer) clearInterval(this.timer); this.timer = null;
    for (const tone of this.tones) { tone.onended = null; tone.stop(); tone.disconnect(); }
    this.tones.clear();
  }
  close() { this.stop(); void this.context?.close(); this.context = null; }
}
