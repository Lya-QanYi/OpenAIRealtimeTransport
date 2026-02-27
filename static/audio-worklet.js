/**
 * Audio Worklet Processors
 * - CaptureProcessor: 麦克风采集 → PCM16 chunk 发送到主线程
 * - PlaybackProcessor: 主线程 Float32 音频 → 扬声器播放
 *
 * 两个 processor 均会自动处理采样率不匹配的情况（线性插值重采样）。
 */

/* ================================================================
 * CaptureProcessor
 * ================================================================ */
class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    /** @type {number} 目标采样率 (OpenAI Realtime API = 24 kHz) */
    this._targetRate = 24000;
    /** @type {number} AudioContext 实际采样率 */
    this._nativeRate = sampleRate; // AudioWorklet 全局变量
    this._ratio = this._nativeRate / this._targetRate;

    // 20 ms chunk: 480 目标样本
    this._targetChunk = Math.round(this._targetRate * 0.02);
    // 对应需要多少原生样本
    this._nativeChunk = Math.round(this._targetChunk * this._ratio);

    this._buffer = new Float32Array(this._nativeChunk);
    this._writeIdx = 0;
  }

  /**
   * 线性插值重采样
   */
  _resample(input, fromRate, toRate) {
    if (fromRate === toRate) return input;
    const ratio = fromRate / toRate;
    const len = Math.round(input.length / ratio);
    const out = new Float32Array(len);
    for (let i = 0; i < len; i++) {
      const pos = i * ratio;
      const idx = Math.floor(pos);
      const frac = pos - idx;
      out[i] =
        idx + 1 < input.length
          ? input[idx] * (1 - frac) + input[idx + 1] * frac
          : input[idx] || 0;
    }
    return out;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;

    for (let i = 0; i < channel.length; i++) {
      this._buffer[this._writeIdx++] = channel[i];

      if (this._writeIdx >= this._nativeChunk) {
        const resampled = this._resample(
          this._buffer,
          this._nativeRate,
          this._targetRate
        );

        // Float32 → Int16 (PCM16)
        const pcm16 = new Int16Array(resampled.length);
        for (let j = 0; j < resampled.length; j++) {
          const s = Math.max(-1, Math.min(1, resampled[j]));
          pcm16[j] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }

        this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
        this._writeIdx = 0;
      }
    }

    return true;
  }
}

/* ================================================================
 * PlaybackProcessor
 * ================================================================ */
class PlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    /** @type {Float32Array[]} */
    this._queue = [];
    /** @type {Float32Array|null} */
    this._current = null;
    this._offset = 0;

    this.port.onmessage = (e) => {
      if (e.data === 'clear') {
        this._queue = [];
        this._current = null;
        this._offset = 0;
      } else if (e.data instanceof ArrayBuffer) {
        this._queue.push(new Float32Array(e.data));
      }
    };
  }

  process(_inputs, outputs) {
    const channel = outputs[0]?.[0];
    if (!channel) return true;

    let written = 0;

    while (written < channel.length) {
      if (!this._current || this._offset >= this._current.length) {
        this._current = this._queue.shift() || null;
        this._offset = 0;
        if (!this._current) {
          channel.fill(0, written);
          break;
        }
      }

      const avail = this._current.length - this._offset;
      const need = channel.length - written;
      const n = Math.min(avail, need);

      channel.set(
        this._current.subarray(this._offset, this._offset + n),
        written
      );

      this._offset += n;
      written += n;
    }

    return true;
  }
}

registerProcessor('capture-processor', CaptureProcessor);
registerProcessor('playback-processor', PlaybackProcessor);
