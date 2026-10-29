// AudioWorklet: microphone samples -> 16 kHz, 16-bit PCM chunks for the backend.
//
// The AudioContext runs at the device rate (often 48 kHz). Gemini Live wants
// 16 kHz, so we resample here: each output sample is the average of the input
// samples it covers (a simple low-pass that avoids most aliasing).
// Every 40 ms of output (640 samples) is posted to the page as an ArrayBuffer.

class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.outRate = options.processorOptions?.targetRate ?? 16000;
    this.step = sampleRate / this.outRate; // input samples per output sample
    this.chunk = new Int16Array(640);
    this.filled = 0;
    this.acc = 0; // running sum for the current output sample
    this.count = 0; // input samples summed so far
    this.pos = 0; // input position within the current output sample
  }

  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;
    for (let i = 0; i < input.length; i++) {
      this.acc += input[i];
      this.count += 1;
      this.pos += 1;
      if (this.pos >= this.step) {
        this.pos -= this.step;
        const s = Math.max(-1, Math.min(1, this.acc / this.count));
        this.chunk[this.filled++] = s < 0 ? s * 0x8000 : s * 0x7fff;
        this.acc = 0;
        this.count = 0;
        if (this.filled === this.chunk.length) {
          this.port.postMessage(this.chunk.buffer, [this.chunk.buffer]);
          this.chunk = new Int16Array(640);
          this.filled = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("pcm-capture", PcmCaptureProcessor);
