// Column 3: response times, call stats, tool calls (with async behaviour), cost, errors, raw log.

import { useEffect, useState } from "react";
import { Panel, formatMs } from "./ui";
import TurnBar from "./TurnBar";

function Stat({ label, value, sub }) {
  return (
    <div className="rounded-lg bg-slate-50 p-2 dark:bg-slate-950">
      <div className="text-[11px] text-slate-500">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-slate-500">{sub}</div>}
    </div>
  );
}

function useElapsed(startIso, running) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!running) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [running]);
  if (!startIso) return null;
  const start = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(startIso) ? startIso : `${startIso}Z`).getTime();
  return Math.max(0, (now - start) / 1000);
}

const pct = (v) => (v === null || v === undefined ? "-" : `${Math.round(v * 100)}%`);

const SCHEDULING_STYLE = {
  SILENT: "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200",
  WHEN_IDLE: "bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-200",
  INTERRUPT: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
};

export default function MetricsPanel({ events, report, settings, active }) {
  const m = report?.metrics;
  const turns = Object.values(events.turns).sort((a, b) => a.turn_index - b.turn_index);
  const scaleMs = Math.max(0, ...turns.map((t) => t.total_ms ?? 0));
  const elapsed = useElapsed(report?.call?.started_at, active);
  const duration = active ? elapsed : m?.duration_s;
  const interruptions = Math.max(events.counters.interruptions ?? 0, m?.interruptions ?? 0);
  const reconnects = Math.max(events.counters.reconnects ?? 0, m?.reconnects ?? 0);
  const callModel = report?.settings?.model ?? settings.model;

  if (!report && turns.length === 0) {
    return (
      <Panel title="3 · Test Metrics & Logs">
        <p className="text-sm text-slate-500">Metrics appear once a call starts.</p>
      </Panel>
    );
  }

  return (
    <Panel title="3 · Test Metrics & Logs">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Stat label="Avg response" value={formatMs(m?.avg_response_ms)} sub="caller stops → agent audio" />
        <Stat label="Max response" value={formatMs(m?.max_response_ms)} />
        <Stat label="Turns" value={m?.turns ?? "-"} sub="caller turns" />
        <Stat label="Interruptions" value={interruptions} sub="barge-ins" />
        <Stat label="Reconnects" value={reconnects} sub="resumed sessions" />
        <Stat label="Call duration" value={duration != null ? `${Math.round(duration)} s` : "-"} />
        <Stat label="Avg tool time" value={formatMs(m?.avg_tool_ms)} sub="call → our response" />
        <Stat label="Tools while speaking" value={m ? `${m.tool_calls_while_speaking}/${m.tool_calls}` : "-"} sub="async: agent kept talking" />
        <Stat label="Tool timeouts" value={m?.tool_timeouts ?? 0} sub={m ? `${m.tool_retries} retries` : ""} />
        <Stat label="Accuracy" value={pct(m?.accuracy)} sub={m ? `${m.correct_fields}/${m.reviewed_fields} reviewed correct` : ""} />
        <Stat label="Completion" value={pct(m?.completion)} sub={m ? `${m.required_filled}/${m.required_total} required filled` : ""} />
      </div>
      <p className="mt-1 text-[11px] text-slate-500">Model: {callModel}</p>

      <h3 className="mt-4 mb-1 text-sm font-semibold">Response time per turn</h3>
      <p className="text-[11px] text-slate-500">
        From the last loud mic chunk to Gemini's first audio, measured in our backend. Includes Gemini's VAD silence
        window ({report?.settings?.vad_silence_ms ?? settings.vad_silence_ms} ms). Browser playback buffering (~50 ms) is not included.
      </p>
      <div className="mt-1 max-h-72 overflow-y-auto pr-1">
        {turns.length === 0 && <p className="text-sm text-slate-500">No turns yet.</p>}
        {turns.map((t) => (
          <TurnBar key={t.turn_index} turn={t} scaleMs={scaleMs} />
        ))}
      </div>

      {m && (
        <>
          <h3 className="mt-4 mb-1 text-sm font-semibold">Estimated cost</h3>
          <div className="grid grid-cols-3 gap-2 text-sm tabular-nums">
            <Stat label="Input" value={`$${m.cost.input_usd.toFixed(4)}`}
              sub={`${m.audio_input_tokens} audio / ${m.text_input_tokens} text tok`} />
            <Stat label="Output" value={`$${m.cost.output_usd.toFixed(4)}`}
              sub={`${m.audio_output_tokens} audio / ${m.text_output_tokens} text tok`} />
            <Stat label="Total" value={`₹${m.cost.total.toFixed(2)}`} sub={`$${m.cost.total_usd.toFixed(4)}`} />
          </div>
        </>
      )}

      <h3 className="mt-4 mb-1 text-sm font-semibold">
        Tool calls ({events.toolCalls.length}
        {m ? `, ${m.tool_calls_failed} failed` : ""})
      </h3>
      <ul className="max-h-72 space-y-1 overflow-y-auto pr-1 text-xs">
        {events.toolCalls.map((tc, i) => (
          <li key={i} className="rounded border border-slate-200 p-1.5 dark:border-slate-800">
            <div className="flex flex-wrap items-center justify-between gap-1">
              <span className="font-mono font-medium">
                <span className={tc.success ? "text-emerald-600" : "text-red-600"}>{tc.success ? "✓" : "✗"}</span>{" "}
                {tc.name}
              </span>
              <span className="flex flex-wrap items-center gap-1">
                <span className={`rounded px-1 text-[10px] font-medium ${SCHEDULING_STYLE[tc.scheduling] ?? "bg-slate-100 text-slate-500 dark:bg-slate-800"}`}
                  title="FunctionResponse scheduling sent to Gemini">
                  {tc.scheduling ?? "no scheduling"}
                </span>
                {tc.timed_out && <span className="rounded bg-red-100 px-1 text-[10px] text-red-700 dark:bg-red-950 dark:text-red-300">timeout</span>}
                {tc.retries > 0 && <span className="text-[10px] text-slate-500">{tc.retries} retry</span>}
                {tc.cancelled && <span className="text-[10px] text-amber-600">cancelled</span>}
                <span className="tabular-nums text-slate-500">{formatMs(tc.duration_ms)}</span>
              </span>
            </div>
            <div className="truncate font-mono text-slate-500" title={JSON.stringify(tc.arguments)}>
              {typeof tc.arguments === "string" ? tc.arguments : JSON.stringify(tc.arguments)}
            </div>
            <div className="text-[11px] text-slate-500">
              {tc.agent_speaking_at_call || tc.audio_chunks_during_tool > 0
                ? `agent kept talking (${tc.audio_chunks_during_tool ?? 0} audio chunks during the call)`
                : "agent was silent during the call"}
            </div>
            {!tc.success && tc.result?.error && <div className="text-red-600">{tc.result.error}</div>}
          </li>
        ))}
      </ul>

      {events.errors.length > 0 && (
        <>
          <h3 className="mt-4 mb-1 text-sm font-semibold text-red-600">Errors</h3>
          <ul className="space-y-1 text-xs text-red-600">
            {events.errors.map((e, i) => (
              <li key={i} className="rounded bg-red-50 p-1.5 dark:bg-red-950">{e.message}</li>
            ))}
          </ul>
        </>
      )}

      <details className="mt-4 text-xs">
        <summary className="cursor-pointer font-semibold">Raw event log ({events.log.length})</summary>
        <pre className="mt-1 max-h-72 overflow-auto rounded bg-slate-950 p-2 text-[11px] leading-snug text-slate-200">
          {events.log
            .map((e) => `${e.ts?.slice(11, 23) ?? ""} ${e.type} ${JSON.stringify(e.data)}`)
            .join("\n")}
        </pre>
      </details>
    </Panel>
  );
}
