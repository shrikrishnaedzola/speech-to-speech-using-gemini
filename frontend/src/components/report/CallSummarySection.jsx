/**
 * Section 1: Call Summary
 * Shows provider metadata, 0-100 overall score with verdict, subscores grid,
 * and 3 key strengths / 3 key problems in simple English.
 */

export default function CallSummarySection({ callInfo, scoring }) {
  if (!callInfo || !scoring) return null;

  const score = scoring.overall_score ?? 0;
  const verdict = scoring.verdict ?? "Evaluated";
  const sub = scoring.subscores ?? {};

  // Color styles based on verdict
  const verdictStyles = {
    Good: "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800",
    "Needs improvement": "bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800",
    Poor: "bg-red-50 text-red-700 border-red-300 dark:bg-red-950/40 dark:text-red-300 dark:border-red-800",
  }[verdict] || "bg-slate-50 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-300";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      {/* Top Details & Overall Score */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b border-slate-100 pb-5 dark:border-slate-800">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              {callInfo.provider?.toUpperCase()} · {callInfo.model}
            </h2>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {callInfo.language}
            </span>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {callInfo.audio_mode}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Call ID: <code className="font-mono">{callInfo.call_id}</code> · Duration: {callInfo.duration_formatted} ({callInfo.duration_seconds}s) · Date: {callInfo.created_date}
          </p>
        </div>

        {/* Score Badge */}
        <div className={`flex items-center gap-3 rounded-xl border px-4 py-2.5 ${verdictStyles}`}>
          <div className="text-center">
            <span className="text-3xl font-extrabold tracking-tight">{score}</span>
            <span className="text-xs font-semibold opacity-75">/100</span>
          </div>
          <div className="border-l border-current/20 pl-3">
            <div className="text-xs font-medium uppercase tracking-wider opacity-75">Verdict</div>
            <div className="text-sm font-bold">{verdict}</div>
          </div>
        </div>
      </div>

      {/* Subscores Grid */}
      <div className="mt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
          Category Performance Breakdown
        </h3>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {[
            { label: "Accuracy (35%)", val: sub.accuracy },
            { label: "Latency (20%)", val: sub.latency },
            { label: "Mishearings (15%)", val: sub.mishearings },
            { label: "Voice Quality (15%)", val: sub.voice_quality },
            { label: "Language (10%)", val: sub.language_support },
            { label: "Cost (5%)", val: sub.cost },
          ].map((item, idx) => {
            const v = item.val ?? 0;
            const barColor = v >= 80 ? "bg-emerald-500" : v >= 60 ? "bg-amber-500" : "bg-red-500";
            return (
              <div key={idx} className="rounded-lg border border-slate-100 bg-slate-50/70 p-2.5 dark:border-slate-800 dark:bg-slate-800/50">
                <div className="text-[11px] font-medium text-slate-600 dark:text-slate-400 truncate">{item.label}</div>
                <div className="mt-1 flex items-baseline justify-between">
                  <span className="text-base font-bold text-slate-800 dark:text-slate-200">{v}</span>
                  <span className="text-[10px] text-slate-400">/100</span>
                </div>
                <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                  <div className={`h-full ${barColor}`} style={{ width: `${Math.min(100, v)}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Key Strengths & Key Problems */}
      <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-emerald-200/80 bg-emerald-50/50 p-3.5 dark:border-emerald-900/60 dark:bg-emerald-950/20">
          <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-800 dark:text-emerald-300 uppercase tracking-wider mb-2">
            <span>✅</span> 3 Key Strengths
          </div>
          <ul className="space-y-1.5 text-xs text-emerald-900 dark:text-emerald-200">
            {scoring.strengths?.map((str, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="text-emerald-600 dark:text-emerald-400">•</span>
                <span>{str}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-lg border border-amber-200/80 bg-amber-50/50 p-3.5 dark:border-amber-900/60 dark:bg-amber-950/20">
          <div className="flex items-center gap-1.5 text-xs font-bold text-amber-800 dark:text-amber-300 uppercase tracking-wider mb-2">
            <span>⚠️</span> 3 Key Problems
          </div>
          <ul className="space-y-1.5 text-xs text-amber-900 dark:text-amber-200">
            {scoring.problems?.map((prob, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="text-amber-600 dark:text-amber-400">•</span>
                <span>{prob}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
