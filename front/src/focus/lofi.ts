export class LofiEngine {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private music: GainNode | null = null;
  private rainGain: GainNode | null = null;
  private timer: number | null = null;
  private voices: AudioScheduledSourceNode[] = [];
  private playing = false;
  private nextTime = 0;
  private step = 0;

  private static readonly BPM = 78;
  private static readonly SIXTEENTH = 60 / LofiEngine.BPM / 4;
  private static readonly CHORDS = [
    [174.61, 220.0, 261.63, 329.63],
    [146.83, 174.61, 220.0, 293.66],
    [130.81, 164.81, 196.0, 246.94],
    [196.0, 246.94, 293.66, 392.0],
  ];
  private static readonly BASS = [87.31, 73.42, 65.41, 98.0];
  private static readonly MELODY = [329.63, 392.0, 440.0, 523.25, 587.33];

  get isPlaying() {
    return this.playing;
  }

  async start() {
    if (this.playing) return;
    const ctx = new AudioContext();
    this.ctx = ctx;
    await ctx.resume();

    const master = ctx.createGain();
    master.gain.value = 0.55;
    const compressor = ctx.createDynamicsCompressor();
    compressor.threshold.value = -16;
    compressor.knee.value = 10;
    compressor.ratio.value = 2.8;
    compressor.attack.value = 0.02;
    compressor.release.value = 0.25;
    compressor.connect(master);
    master.connect(ctx.destination);

    const music = ctx.createGain();
    music.gain.value = 1;
    music.connect(compressor);
    this.connectDelay(ctx, music, master);

    const rainGain = ctx.createGain();
    rainGain.gain.value = 0;
    rainGain.connect(master);

    this.master = master;
    this.music = music;
    this.rainGain = rainGain;
    this.playing = true;
    this.step = 0;
    this.nextTime = ctx.currentTime + 0.06;

    this.vinyl(ctx, master);
    this.rainBed(ctx, rainGain);
    this.schedule();
  }

  setRain(on: boolean) {
    if (!this.rainGain || !this.ctx) return;
    this.rainGain.gain.setTargetAtTime(
      on ? 0.03 : 0,
      this.ctx.currentTime,
      0.25,
    );
  }

  stop() {
    this.playing = false;
    if (this.timer != null) {
      window.clearTimeout(this.timer);
      this.timer = null;
    }
    for (const voice of this.voices) {
      try {
        voice.stop();
      } catch {
        // already stopped
      }
    }
    this.voices = [];
    this.master?.disconnect();
    this.master = null;
    this.music = null;
    this.rainGain = null;
    const ctx = this.ctx;
    this.ctx = null;
    if (ctx && ctx.state !== "closed") {
      void ctx.close();
    }
  }

  private connectDelay(ctx: AudioContext, source: AudioNode, dest: AudioNode) {
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 1800;
    const delay = ctx.createDelay();
    delay.delayTime.value = 0.29;
    const wet = ctx.createGain();
    wet.gain.value = 0.16;
    const feedback = ctx.createGain();
    feedback.gain.value = 0.22;
    source.connect(filter);
    filter.connect(delay);
    delay.connect(wet);
    delay.connect(feedback);
    feedback.connect(delay);
    wet.connect(dest);
  }

  private schedule() {
    const ctx = this.ctx;
    const dest = this.music;
    if (!this.playing || !ctx || !dest) return;
    while (this.nextTime < ctx.currentTime + 0.18) {
      this.playStep(ctx, dest, this.step, this.nextTime);
      const swung =
        this.step % 2 === 1
          ? LofiEngine.SIXTEENTH * 1.18
          : LofiEngine.SIXTEENTH * 0.82;
      this.nextTime += swung;
      this.step += 1;
    }
    this.timer = window.setTimeout(() => this.schedule(), 40);
  }

  private playStep(
    ctx: AudioContext,
    dest: AudioNode,
    step: number,
    time: number,
  ) {
    const bar = Math.floor(step / 16) % LofiEngine.CHORDS.length;
    const beat = step % 16;
    const chord = LofiEngine.CHORDS[bar];
    const root = LofiEngine.BASS[bar];

    if (beat === 0) {
      this.epiano(ctx, dest, chord, time, LofiEngine.SIXTEENTH * 15);
      this.bass(ctx, dest, root, time, 0.42);
      this.kick(ctx, dest, time);
    }
    if (beat === 8) {
      this.kick(ctx, dest, time);
      this.bass(ctx, dest, root * 1.5, time, 0.22);
    }
    if (beat === 4 || beat === 12) {
      this.snare(ctx, dest, time);
    }
    if (beat === 6) {
      this.bass(ctx, dest, root * 1.25, time, 0.18);
    }
    if (beat === 11 && bar % 2 === 1) {
      this.kick(ctx, dest, time, 0.16);
    }
    if (beat % 2 === 0) {
      this.hat(ctx, dest, time, beat % 4 === 0 ? 0.035 : 0.02);
    }
    if (beat === 10 || beat === 14) {
      const note =
        LofiEngine.MELODY[(bar * 2 + (beat === 14 ? 1 : 0)) % LofiEngine.MELODY.length];
      this.lead(ctx, dest, note, time, beat === 14 ? 0.55 : 0.28);
    }
  }

  private track<T extends AudioScheduledSourceNode>(source: T): T {
    this.voices.push(source);
    return source;
  }

  private noiseBuffer(ctx: AudioContext, seconds: number, pink: boolean) {
    const buffer = ctx.createBuffer(
      1,
      Math.floor(ctx.sampleRate * seconds),
      ctx.sampleRate,
    );
    const data = buffer.getChannelData(0);
    let b0 = 0;
    let b1 = 0;
    let b2 = 0;
    for (let i = 0; i < data.length; i += 1) {
      const white = Math.random() * 2 - 1;
      if (!pink) {
        data[i] = white;
        continue;
      }
      b0 = 0.99765 * b0 + white * 0.099046;
      b1 = 0.963 * b1 + white * 0.2965164;
      b2 = 0.57 * b2 + white * 1.0526913;
      data[i] = (b0 + b1 + b2 + white * 0.1848) * 0.18;
    }
    return buffer;
  }

  private burst(
    ctx: AudioContext,
    dest: AudioNode,
    time: number,
    duration: number,
    type: BiquadFilterType,
    frequency: number,
    q: number,
    gainValue: number,
    pink = false,
  ) {
    const source = ctx.createBufferSource();
    source.buffer = this.noiseBuffer(ctx, Math.max(duration, 0.05), pink);
    const filter = ctx.createBiquadFilter();
    filter.type = type;
    filter.frequency.value = frequency;
    filter.Q.value = q;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.0001, time);
    gain.gain.exponentialRampToValueAtTime(gainValue, time + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, time + duration);
    source.connect(filter);
    filter.connect(gain);
    gain.connect(dest);
    source.start(time);
    source.stop(time + duration + 0.02);
  }

  private osc(
    ctx: AudioContext,
    dest: AudioNode,
    time: number,
    frequency: number,
    duration: number,
    type: OscillatorType,
    peak: number,
    attack = 0.02,
    detune = 0,
  ) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(frequency, time);
    osc.detune.setValueAtTime(detune, time);
    gain.gain.setValueAtTime(0.0001, time);
    gain.gain.exponentialRampToValueAtTime(peak, time + attack);
    gain.gain.exponentialRampToValueAtTime(0.0001, time + duration);
    osc.connect(gain);
    gain.connect(dest);
    osc.start(time);
    osc.stop(time + duration + 0.04);
  }

  private epiano(
    ctx: AudioContext,
    dest: AudioNode,
    freqs: number[],
    time: number,
    duration: number,
  ) {
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.Q.value = 0.7;
    filter.frequency.setValueAtTime(480, time);
    filter.frequency.exponentialRampToValueAtTime(1700, time + 0.09);
    filter.frequency.exponentialRampToValueAtTime(820, time + duration * 0.55);
    const bus = ctx.createGain();
    bus.connect(filter);
    filter.connect(dest);
    for (const freq of freqs) {
      this.osc(ctx, bus, time, freq, duration, "sine", 0.07, 0.035, -8);
      this.osc(ctx, bus, time, freq, duration, "triangle", 0.045, 0.04, 7);
    }
  }

  private bass(
    ctx: AudioContext,
    dest: AudioNode,
    frequency: number,
    time: number,
    duration: number,
  ) {
    this.osc(ctx, dest, time, frequency, duration, "sine", 0.2, 0.015);
    this.osc(ctx, dest, time, frequency * 2, duration * 0.7, "sine", 0.04, 0.02);
  }

  private lead(
    ctx: AudioContext,
    dest: AudioNode,
    frequency: number,
    time: number,
    duration: number,
  ) {
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.setValueAtTime(2200, time);
    filter.frequency.exponentialRampToValueAtTime(900, time + duration);
    const gain = ctx.createGain();
    gain.connect(dest);
    filter.connect(gain);
    this.osc(ctx, filter, time, frequency, duration, "sine", 0.055, 0.03, 4);
    this.osc(
      ctx,
      filter,
      time,
      frequency * 2,
      duration * 0.6,
      "triangle",
      0.012,
      0.04,
    );
  }

  private kick(ctx: AudioContext, dest: AudioNode, time: number, peak = 0.32) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(148, time);
    osc.frequency.exponentialRampToValueAtTime(42, time + 0.11);
    gain.gain.setValueAtTime(0.0001, time);
    gain.gain.exponentialRampToValueAtTime(peak, time + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, time + 0.28);
    osc.connect(gain);
    gain.connect(dest);
    osc.start(time);
    osc.stop(time + 0.32);
  }

  private snare(ctx: AudioContext, dest: AudioNode, time: number) {
    this.osc(ctx, dest, time, 196, 0.12, "triangle", 0.06, 0.005);
    this.burst(ctx, dest, time, 0.14, "bandpass", 1800, 0.9, 0.14);
  }

  private hat(
    ctx: AudioContext,
    dest: AudioNode,
    time: number,
    gainValue: number,
  ) {
    this.burst(ctx, dest, time, 0.045, "highpass", 9000, 0.7, gainValue);
  }

  private vinyl(ctx: AudioContext, dest: AudioNode) {
    const source = this.track(ctx.createBufferSource());
    source.buffer = this.noiseBuffer(ctx, 2, true);
    source.loop = true;
    const filter = ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.value = 900;
    filter.Q.value = 0.6;
    const gain = ctx.createGain();
    gain.gain.value = 0.012;
    source.connect(filter);
    filter.connect(gain);
    gain.connect(dest);
    source.start();
  }

  private rainBed(ctx: AudioContext, dest: AudioNode) {
    const source = this.track(ctx.createBufferSource());
    source.buffer = this.noiseBuffer(ctx, 2, true);
    source.loop = true;
    const high = ctx.createBiquadFilter();
    high.type = "highpass";
    high.frequency.value = 5000;
    const low = ctx.createBiquadFilter();
    low.type = "lowpass";
    low.frequency.value = 11000;
    source.connect(high);
    high.connect(low);
    low.connect(dest);
    source.start();
  }
}
