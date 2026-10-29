/**
 * Section 3: Mishearings & Understanding Errors
 * Displays total errors, resolution rates, WER/CER, and detailed error log table.
 */

export default function MishearingsSection({ mishearings }) {
  if (!mishearings) return null;

  const total = mishearings.total_mishearings ?? 0;
  const fixed = mishearings.fixed_count ?? 0;
  const unfixed = mishearings.unfixed_count ?? 0;
  const wer = (mishearings.overall_wer ?? 0) * 100;
  const cer = (mishearings.overall_cer ?? 0) * 100;
  const items = mishearings.items ?? [];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3 dark:border-slate-800 mb-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            3. Mishearings & Acoustic Understanding
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Tracking transcription errors, caller corrections, number swaps, and resolution
          </p>
        </div>

        {/* Status Pill */}
        <span
          className={`rounded-full px-3 py-1 text-xs font-semibold ${
            unfixed === 0
              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
              : "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300"
          }`}
        >
          {unfixed === 0 ? "✓ All Misunderstandings Resolved" : `⚠️ ${unfixed} Uncorrected Error(s)`}
        </span>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-4">
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Total Mishearings</div>
          <div className="mt-1 text-xl font-extrabold text-slate-800 dark:text-slate-200">{total}</div>
        </div>
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Fixed Later in Call</div>
          <div className="mt-1 text-xl font-extrabold text-emerald-600 dark:text-emerald-400">{fixed}</div>
        </div>
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Word Error Rate (WER)</div>
          <div className="mt-1 text-xl font-extrabold text-slate-800 dark:text-slate-200">{wer.toFixed(1)}%</div>
        </div>
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Char Error Rate (CER)</div>
          <div className="mt-1 text-xl font-extrabold text-slate-800 dark:text-slate-200">{cer.toFixed(1)}%</div>
        </div>
      </div>

      {/* Mishearings Table */}
      {items.length === 0 ? (
        <div className="rounded-lg border border-slate-100 bg-emerald-50/40 p-4 text-center text-xs text-emerald-800 dark:border-slate-800 dark:bg-emerald-950/20 dark:text-emerald-300">
          ✨ Excellent listening comprehension. No caller corrections or acoustic mishearings logged.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-[11px] font-semibold text-slate-600 dark:bg-slate-800/70 dark:text-slate-400">
              <tr>
                <th className="px-3 py-2">Time</th>
                <th className="px-3 py-2">What Was Said</th>
                <th className="px-3 py-2">What AI Heard</th>
                <th className="px-3 py-2">Field</th>
                <th className="px-3 py-2">Error Type</th>
                <th className="px-3 py-2">Fixed Later?</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {items.map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-[11px] text-slate-500">
                    {item.turn_time || "—"}
                  </td>
                  <td className="px-3 py-2 font-medium text-slate-800 dark:text-slate-200 max-w-[200px] truncate" title={item.what_was_said}>
                    {item.what_was_said}
                  </td>
                  <td className="px-3 py-2 text-red-600 dark:text-red-400 max-w-[200px] truncate" title={item.what_ai_heard}>
                    {item.what_ai_heard}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                    {item.field_affected}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-[11px] text-slate-600 dark:text-slate-400">
                    {item.error_type}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    {item.fixed_later ? (
                      <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                        ✓ Fixed
                      </span>
                    ) : (
                      <span className="rounded bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-800 dark:bg-red-950 dark:text-red-300">
                        ✗ Unfixed
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
