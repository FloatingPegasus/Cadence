export class LofiEngine {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private rainGain: GainNode | null = null;
  private timers: number[] = [];
  private playing = false;

  get isPlaying() {
    return this.playing;
  }

  async start() {
    if (this.playing) return;
    const ctx = new AudioContext();
    await ctx.resume();
    const master = ctx.createGain();
    master.gain.value = 0.22;
    master.connect(ctx.destination);

    const rainGain = ctx.createGain();
    rainGain.gain.value = 0.08;
    rainGain.connect(master);

    this.ctx = ctx;
    this.master = master;
    this.rainGain = rainGain;
    this.playing = true;
    this.crackle(ctx, master);
    this.rain(ctx, rainGain);
    this.loopChords(ctx, master);
    this.loopBeat(ctx, master);
  }

  setRain(on: boolean) {
    if (!this.rainGain || !this.ctx) return;
    this.rainGain.gain.setTargetAtTime(
      on ? 0.08 : 0,
      this.ctx.currentTime,
      0.2,
    );
  }

  stop() {
    this.playing = false;
    for (const id of this.timers) window.clearTimeout(id);
    this.timers = [];
    void this.ctx?.close();
    this.ctx = null;
    this.master = null;
    this.rainGain = null;
  }

  private noise(ctx: AudioContext) {
    const buffer = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) {
      data[i] = Math.random() * 2 - 1;
    }
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.loop = true;
    return source;
  }

  private crackle(ctx: AudioContext, dest: AudioNode) {
    const source = this.noise(ctx);
    const filter = ctx.createBiquadFilter();
    filter.type = "highpass";
    filter.frequency.value = 1200;
    const gain = ctx.createGain();
    gain.gain.value = 0.03;
    source.connect(filter);
    filter.connect(gain);
    gain.connect(dest);
    source.start();
  }

  private rain(ctx: AudioContext, dest: AudioNode) {
    const source = this.noise(ctx);
    const filter = ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.value = 900;
    filter.Q.value = 0.4;
    source.connect(filter);
    filter.connect(dest);
    source.start();
  }

  private tone(
    ctx: AudioContext,
    dest: AudioNode,
    frequency: number,
    duration: number,
    type: OscillatorType,
    gainValue: number,
  ) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.value = frequency;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(gainValue, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);
    osc.connect(gain);
    gain.connect(dest);
    osc.start();
    osc.stop(ctx.currentTime + duration + 0.05);
  }

  private loopChords(ctx: AudioContext, dest: AudioNode) {
    const notes = [196, 247, 294, 330, 392];
    const step = () => {
      if (!this.playing || this.ctx !== ctx) return;
      const note = notes[Math.floor(Math.random() * notes.length)];
      this.tone(ctx, dest, note, 1.8, "triangle", 0.05);
      this.tone(ctx, dest, note * 2, 1.2, "sine", 0.02);
      this.timers.push(window.setTimeout(step, 1800 + Math.random() * 700));
    };
    step();
  }

  private loopBeat(ctx: AudioContext, dest: AudioNode) {
    let tick = 0;
    const step = () => {
      if (!this.playing || this.ctx !== ctx) return;
      if (tick % 2 === 0) {
        this.tone(ctx, dest, 70, 0.18, "sine", 0.07);
      } else {
        this.tone(ctx, dest, 180, 0.08, "square", 0.015);
      }
      tick += 1;
      this.timers.push(window.setTimeout(step, 520));
    };
    step();
  }
}
