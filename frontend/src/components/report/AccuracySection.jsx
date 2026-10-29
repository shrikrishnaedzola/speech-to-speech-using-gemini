/**
 * Section 7: Form Data Accuracy & Tool Calls
 * Displays accuracy metrics, completion rates, tool call status,
 * and the complete field comparison table (Expected vs Saved).
 */

export default function AccuracySection({ accuracy }) {
  if (!accuracy) return null;

  const fieldAcc = accuracy.field_accuracy_percent ?? 100;
  const comp = accuracy.completion_percent ?? 100;
  const tStats = accuracy.tool_call_stats || {};
  const rec = accuracy.error_recovery || {};
  const fieldRows = accuracy.field_table || [];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="border-b border-slate-100 pb-3 dark:border-slate-800 mb-4">
        <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
          7. Form Data Accuracy & Tool Calls
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Verification against expected values, required field completion, and tool execution
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-4">
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Field Accuracy</div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-xl font-extrabold text-emerald-600 dark:text-emerald-400">{fieldAcc}%</span>
          </div>
          <div className="text-[10px] text-slate-400">
            {accuracy.correct_fields_count} of {accuracy.filled_fields_count} filled fields correct
          </div>
        </div>

        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Required Completion</div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-xl font-extrabold text-slate-800 dark:text-slate-200">{comp}%</span>
          </div>
          <div className="text-[10px] text-slate-400">
            {accuracy.filled_fields_count} of {accuracy.required_fields_count} required fields
          </div>
        </div>

        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Tool Call Success Rate</div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-xl font-extrabold text-blue-600 dark:text-blue-400">
              {tStats.success_rate_percent ?? 100}%
            </span>
          </div>
          <div className="text-[10px] text-slate-400">
            {tStats.successful_calls ?? 0} of {tStats.total_calls ?? 0} tool calls passed
          </div>
        </div>

        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Error Recovery</div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-xl font-extrabold text-slate-800 dark:text-slate-200">
              {rec.recovery_rate_percent ?? 100}%
            </span>
          </div>
          <div className="text-[10px] text-slate-400">
            {rec.successfully_resolved ?? 0} of {rec.retry_attempts ?? 0} retried fields fixed
          </div>
        </div>
      </div>

      {/* Field Comparison Table */}
      <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-[11px] font-semibold text-slate-600 dark:bg-slate-800/70 dark:text-slate-400">
            <tr>
              <th className="px-3 py-2">Field</th>
              <th className="px-3 py-2">Expected Value</th>
              <th className="px-3 py-2">Saved Value</th>
              <th className="px-3 py-2">Verdict</th>
              <th className="px-3 py-2">Diagnostic Notes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {fieldRows.map((row, idx) => {
              const isOk = row.correct;
              return (
                <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                  <td className="px-3 py-2">
                    <span className="font-semibold text-slate-900 dark:text-slate-100">{row.field_label}</span>
                    {row.required && (
                      <span className="ml-1 text-[10px] font-medium text-red-500">*req</span>
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-slate-600 dark:text-slate-400">
                    {String(row.expected)}
                  </td>
                  <td className="px-3 py-2 font-mono font-medium text-slate-900 dark:text-slate-100">
                    {String(row.saved)}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    {isOk ? (
                      <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                        ✓ Correct
                      </span>
                    ) : (
                      <span className="rounded bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-800 dark:bg-red-950 dark:text-red-300">
                        ✗ Wrong
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-[11px] text-slate-500 dark:text-slate-400">
                    {row.notes || "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
