/**
 * Section 2: Transcript
 * Chat bubbles with timestamps, detected languages, and distinct highlight colors:
 * - Red: Mishearings & understanding errors
 * - Orange: Re-asked questions / caller corrections
 * - Blue: Tool execution
 * - Purple: Interruptions / barge-in
 */

export default function TranscriptSection({ transcript }) {
  if (!transcript || transcript.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h3 className="text-sm font-semibold mb-2">2. Conversation Transcript</h3>
        <p className="text-xs text-slate-500">No transcript available for this call.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3 dark:border-slate-800 mb-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            2. Transcript & Turn Breakdown
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {transcript.length} conversation turns with color highlights for anomalies
          </p>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <span className="flex items-center gap-1 rounded bg-red-100 px-2 py-0.5 text-red-700 dark:bg-red-950/60 dark:text-red-300">
            <span className="h-2 w-2 rounded-full bg-red-500" /> Mishearing
          </span>
          <span className="flex items-center gap-1 rounded bg-amber-100 px-2 py-0.5 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300">
            <span className="h-2 w-2 rounded-full bg-amber-500" /> Correction / Re-ask
          </span>
          <span className="flex items-center gap-1 rounded bg-blue-100 px-2 py-0.5 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300">
            <span className="h-2 w-2 rounded-full bg-blue-500" /> Tool Call
          </span>
          <span className="flex items-center gap-1 rounded bg-purple-100 px-2 py-0.5 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300">
            <span className="h-2 w-2 rounded-full bg-purple-500" /> Interruption
          </span>
        </div>
      </div>

      {/* Bubble List */}
      <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
        {transcript.map((turn, i) => {
          const isCaller = turn.role === "caller" || turn.role === "user";
          const isCorrection = turn.is_correction;
          const isInterrupted = turn.interrupted;
          const hasTool = turn.tool_call || turn.tool_ms > 0;
          const isMishearing = turn.is_mishearing;

          // Determine bubble highlight styling
          let bubbleStyle = isCaller
            ? "bg-slate-100 border-slate-200 text-slate-800 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100"
            : "bg-emerald-50/70 border-emerald-200 text-slate-800 dark:bg-emerald-950/30 dark:border-emerald-800 dark:text-slate-100";

          if (isMishearing) {
            bubbleStyle = "bg-red-50 border-red-300 text-red-900 dark:bg-red-950/40 dark:border-red-800 dark:text-red-200";
          } else if (isCorrection) {
            bubbleStyle = "bg-amber-50 border-amber-300 text-amber-900 dark:bg-amber-950/40 dark:border-amber-800 dark:text-amber-200";
          } else if (isInterrupted) {
            bubbleStyle = "bg-purple-50 border-purple-300 text-purple-900 dark:bg-purple-950/40 dark:border-purple-800 dark:text-purple-200";
          } else if (hasTool) {
            bubbleStyle = "bg-blue-50 border-blue-300 text-blue-900 dark:bg-blue-950/40 dark:border-blue-800 dark:text-blue-200";
          }

          return (
            <div
              key={i}
              className={`flex flex-col ${isCaller ? "items-start" : "items-end"}`}
            >
              <div className="flex items-center gap-1.5 mb-1 text-[11px] text-slate-500 dark:text-slate-400">
                <span className="font-semibold uppercase tracking-wider">
                  {isCaller ? "Caller" : "AI Agent"}
                </span>
                <span>·</span>
                <span>{turn.time || "00:00"}</span>
                {isCaller && turn.language && (
                  <span className="rounded bg-slate-200 px-1 py-0.2 text-[10px] font-mono text-slate-700 dark:bg-slate-700 dark:text-slate-300">
                    lang: {turn.language}
                  </span>
                )}
                {isInterrupted && (
                  <span className="rounded bg-purple-200 px-1.5 py-0.2 text-[10px] font-semibold text-purple-800 dark:bg-purple-900 dark:text-purple-200">
                    Interrupted
                  </span>
                )}
                {isCorrection && (
                  <span className="rounded bg-amber-200 px-1.5 py-0.2 text-[10px] font-semibold text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                    Correction
                  </span>
                )}
              </div>

              <div className={`max-w-[85%] rounded-xl border px-3.5 py-2 text-xs leading-relaxed shadow-sm ${bubbleStyle}`}>
                <p>{turn.text}</p>
                {turn.tool_name && (
                  <div className="mt-1.5 rounded bg-blue-100/80 px-2 py-0.5 text-[10px] font-mono text-blue-800 dark:bg-blue-900/60 dark:text-blue-300">
                    tool: {turn.tool_name}()
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
