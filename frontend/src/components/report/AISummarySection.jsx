/**
 * Section 10: AI-Written Executive Summary
 * Displays grounded plain-English summary with required disclaimer notice.
 */

export default function AISummarySection({ aiSummary, onRegenerate, isRegenerating }) {
  if (!aiSummary || !aiSummary.text) return null;

  return (
    <div className="rounded-xl border border-indigo-200 bg-gradient-to-r from-indigo-50/50 via-white to-purple-50/40 p-4 shadow-sm dark:border-indigo-900/60 dark:bg-slate-900/90 dark:from-slate-900 dark:to-indigo-950/20">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-indigo-100/80 pb-2.5 dark:border-indigo-900/40">
        <div className="flex items-center gap-2">
          <span className="text-base">✨</span>
          <h3 className="text-sm font-bold text-indigo-950 dark:text-indigo-200">
            Executive AI Summary
          </h3>
          <span className="rounded bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold text-indigo-700 dark:bg-indigo-900/60 dark:text-indigo-300">
            {aiSummary.generated_by || "Verified Grounded"}
          </span>
        </div>
        {onRegenerate && (
          <button
            onClick={onRegenerate}
            disabled={isRegenerating}
            className="text-xs font-medium text-indigo-600 hover:text-indigo-800 disabled:opacity-50 dark:text-indigo-400 dark:hover:text-indigo-300 flex items-center gap-1"
          >
            {isRegenerating ? "Generating..." : "↻ Regenerate Summary"}
          </button>
        )}
      </div>

      <div className="mt-3 text-xs leading-relaxed text-slate-700 dark:text-slate-300 whitespace-pre-line">
        {aiSummary.text}
      </div>

      <div className="mt-3 flex items-center gap-1.5 text-[11px] font-medium text-amber-700 dark:text-amber-400">
        <span>⚠️</span>
        <span>{aiSummary.disclaimer || "AI-generated summary - review before sharing."}</span>
      </div>
    </div>
  );
}
