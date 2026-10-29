/**
 * Section 9: Issues & Recommendations
 * Displays prioritized problems (High, Medium, Low) with actionable engineering suggestions.
 */

export default function IssuesSection({ issues }) {
  if (!issues || issues.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-2">
          9. Priority Issues & Actionable Recommendations
        </h3>
        <p className="text-xs text-emerald-600 dark:text-emerald-400">
          ✓ No critical issues found. All evaluation thresholds were satisfied cleanly.
        </p>
      </div>
    );
  }

  const severityStyles = {
    High: {
      border: "border-red-200 dark:border-red-900/60",
      bg: "bg-red-50/50 dark:bg-red-950/20",
      badge: "bg-red-100 text-red-800 dark:bg-red-900/60 dark:text-red-300",
      icon: "🔴",
    },
    Medium: {
      border: "border-amber-200 dark:border-amber-900/60",
      bg: "bg-amber-50/50 dark:bg-amber-950/20",
      badge: "bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-300",
      icon: "🟡",
    },
    Low: {
      border: "border-blue-200 dark:border-blue-900/60",
      bg: "bg-blue-50/50 dark:bg-blue-950/20",
      badge: "bg-blue-100 text-blue-800 dark:bg-blue-900/60 dark:text-blue-300",
      icon: "🟢",
    },
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="border-b border-slate-100 pb-3 dark:border-slate-800 mb-4">
        <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
          9. Priority Issues & Actionable Recommendations
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Ranked by severity with concrete prompt and engineering fixes
        </p>
      </div>

      <div className="space-y-3">
        {issues.map((issue, idx) => {
          const style = severityStyles[issue.severity] || severityStyles.Medium;
          return (
            <div
              key={idx}
              className={`rounded-lg border p-4 text-xs transition ${style.border} ${style.bg}`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-1.5 font-bold text-slate-900 dark:text-slate-100 text-sm">
                  <span>{style.icon}</span>
                  <span>{issue.title}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${style.badge}`}>
                    {issue.severity} Priority
                  </span>
                  {issue.category && (
                    <span className="rounded bg-slate-200/80 px-2 py-0.5 text-[10px] font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-300">
                      {issue.category}
                    </span>
                  )}
                </div>
              </div>

              <p className="text-slate-700 dark:text-slate-300 leading-relaxed mb-2.5">
                {issue.description}
              </p>

              <div className="rounded-md bg-white/80 p-2.5 border border-slate-200/60 dark:bg-slate-900/70 dark:border-slate-800">
                <span className="font-bold text-slate-800 dark:text-slate-200">💡 Recommended Action: </span>
                <span className="text-slate-700 dark:text-slate-300">{issue.suggestion}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
