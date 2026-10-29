// Browser side of a live call:
//   mic -> AudioWorklet (16 kHz PCM) -> WebSocket /ws/call -> backend -> Gemini
//   Gemini -> backend -> WebSocket (24 kHz PCM) -> scheduled AudioBuffers -> speaker
//
// If the WebSocket drops, we reconnect with the same call_id; the backend keeps
// the Gemini session (and all saved answers) for 30 seconds.

import { useRef, useState } from "react";
import { callSocketUrl } from "../api";

const OUTPUT_RATE = 24000;
const MAX_RECONNECTS = 5;

export function useLiveCall() {
  const ctxRef = useRef(null);
  const streamRef = useRef(null);
  const workletRef = useRef(null);
  const wsRef = useRef(null);
  const sessionRef = useRef(null);
  const playRef = useRef({ nextTime: 0, sources: new Set() });
  const mutedRef = useRef(false);
  const stoppedRef = useRef(true);
  const [muted, setMuted] = useState(false);
  const [socketState, setSocketState] = useState("idle"); // idle | open | reconnecting | closed

  // --- playback --------------------------------------------------------

  function playChunk(arrayBuffer) {
    const ctx = ctxRef.current;
    if (!ctx) return;
    const pcm = new Int16Array(arrayBuffer);
    const buffer = ctx.createBuffer(1, pcm.length, OUTPUT_RATE);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) data[i] = pcm[i] / 32768;
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    const play = playRef.current;
    // Chunks play back to back; a small lead avoids gaps when the network jitters.
    play.nextTime = Math.max(play.nextTime, ctx.currentTime + 0.05);
    source.start(play.nextTime);
    play.nextTime += buffer.duration;
    play.sources.add(source);
    source.onended = () => play.sources.delete(source);
  }

  function clearPlayback() {
    // Barge-in: stop everything already queued so the caller isn't talked over.
    const play = playRef.current;
    play.sources.forEach((s) => {
      try {
        s.stop();
      } catch {
        /* already stopped */
      }
    });
    play.sources.clear();
    play.nextTime = 0;
  }

  // --- WebSocket ---------------------------------------------------------

  function openSocket(attempt = 0) {
    const ws = new WebSocket(callSocketUrl(sessionRef.current.ws_url));
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;
    ws.onopen = () => {
      setSocketState("open");
      if (mutedRef.current) ws.send(JSON.stringify({ type: "mute", muted: true }));
    };
    ws.onmessage = (msg) => {
      if (msg.data instanceof ArrayBuffer) {
        playChunk(msg.data);
        return;
      }
      const control = JSON.parse(msg.data);
      if (control.type === "clear_audio") clearPlayback();
      if (control.type === "ended") stop();
    };
    ws.onclose = (e) => {
      if (stoppedRef.current) return;
      if (e.code === 4404 || attempt >= MAX_RECONNECTS) {
        setSocketState("closed");
        return;
      }
      setSocketState("reconnecting");
      setTimeout(() => !stoppedRef.current && openSocket(attempt + 1), 1000 * (attempt + 1));
    };
  }

  // --- public API ----------------------------------------------------------

  async function connect(session) {
    stoppedRef.current = false;
    sessionRef.current = session;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    streamRef.current = stream;
    const ctx = new AudioContext();
    ctxRef.current = ctx;
    await ctx.audioWorklet.addModule("/pcm-capture-worklet.js");
    const worklet = new AudioWorkletNode(ctx, "pcm-capture", { processorOptions: { targetRate: 16000 } });
    workletRef.current = worklet;
    worklet.port.onmessage = (e) => {
      const ws = wsRef.current;
      if (!mutedRef.current && ws?.readyState === WebSocket.OPEN) ws.send(e.data);
    };
    ctx.createMediaStreamSource(stream).connect(worklet);
    // Connect to the speakers through a muted gain, so the browser keeps running the worklet.
    const silent = ctx.createGain();
    silent.gain.value = 0;
    worklet.connect(silent).connect(ctx.destination);
    await ctx.resume(); // created after an await, so it may start suspended
    openSocket();
  }

  function stop() {
    stoppedRef.current = true;
    clearPlayback();
    workletRef.current?.disconnect();
    workletRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    ctxRef.current?.close().catch(() => {});
    ctxRef.current = null;
    setSocketState("closed");
    setMuted(false);
    mutedRef.current = false;
  }

  function send(message) {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(message));
  }

  function end() {
    send({ type: "end" });
    stop();
    wsRef.current?.close();
  }

  function toggleMute() {
    mutedRef.current = !mutedRef.current;
    setMuted(mutedRef.current);
    send({ type: "mute", muted: mutedRef.current });
  }

  // Test button: the backend closes its Gemini connection and resumes it.
  const testDrop = () => send({ type: "test_drop" });

  return { connect, end, stop, toggleMute, testDrop, muted, socketState };
}
