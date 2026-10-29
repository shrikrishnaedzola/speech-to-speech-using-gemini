/**
 * Section 8: Cost & Economics
 * Displays call cost in USD and INR, cost per minute/completed form,
 * 1,000 calls projection, and itemized billing breakdown table.
 */

export default function CostSection({ cost }) {
  if (!cost) return null;

  const proj = cost.projection_1000_calls || {};
  const breakdown = cost.breakdown || [];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3 dark:border-slate-800 mb-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            8. Cost Analysis & 1,000 Calls Projection
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Provider: {cost.provider_display_name} · Rates updated {cost.rates_last_updated} (1 USD = ₹{cost.exchange_rate_usd_to_inr})
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="text-right">
            <span className="text-lg font-extrabold text-slate-900 dark:text-slate-100">
              ${cost.total_cost_usd?.toFixed(4)}
            </span>
            <span className="ml-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
              (₹{cost.total_cost_inr?.toFixed(2)})
            </span>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-4">
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Total Call Cost</div>
          <div className="mt-1 text-lg font-extrabold text-slate-900 dark:text-slate-100">
            ${cost.total_cost_usd?.toFixed(4)}
          </div>
          <div className="text-[10px] text-slate-400">₹{cost.total_cost_inr?.toFixed(2)} INR</div>
        </div>

        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Cost per Minute</div>
          <div className="mt-1 text-lg font-extrabold text-slate-900 dark:text-slate-100">
            ${cost.cost_per_minute_usd?.toFixed(4)}
          </div>
          <div className="text-[10px] text-slate-400">₹{cost.cost_per_minute_inr?.toFixed(2)} / min</div>
        </div>

        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Cost per Completed Form</div>
          <div className="mt-1 text-lg font-extrabold text-slate-900 dark:text-slate-100">
            ${cost.cost_per_completed_form_usd?.toFixed(4)}
          </div>
          <div className="text-[10px] text-slate-400">₹{cost.cost_per_completed_form_inr?.toFixed(2)} INR</div>
        </div>

        <div className="rounded-lg border border-indigo-100 bg-indigo-50/50 p-3 dark:border-indigo-950 dark:bg-indigo-950/30">
          <div className="text-[11px] font-medium text-indigo-700 dark:text-indigo-300">1,000 Calls Projection</div>
          <div className="mt-1 text-lg font-extrabold text-indigo-900 dark:text-indigo-100">
            ${proj.usd?.toLocaleString()}
          </div>
          <div className="text-[10px] text-indigo-600 dark:text-indigo-300">₹{proj.inr?.toLocaleString()} INR</div>
        </div>
      </div>

      {/* Breakdown Table */}
      {breakdown.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-[11px] font-semibold text-slate-600 dark:bg-slate-800/70 dark:text-slate-400">
              <tr>
                <th className="px-3 py-2">Billing Component</th>
                <th className="px-3 py-2">Usage / Quantity</th>
                <th className="px-3 py-2">Standard Unit Rate</th>
                <th className="px-3 py-2">Cost (USD)</th>
                <th className="px-3 py-2">Cost (INR)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {breakdown.map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                  <td className="px-3 py-2 font-medium text-slate-800 dark:text-slate-200">
                    {item.item}
                  </td>
                  <td className="px-3 py-2 text-slate-600 dark:text-slate-400 font-mono text-[11px]">
                    {item.quantity}
                  </td>
                  <td className="px-3 py-2 text-slate-500 font-mono text-[11px]">
                    {item.rate}
                  </td>
                  <td className="px-3 py-2 font-mono font-medium text-slate-900 dark:text-slate-100">
                    ${item.cost_usd?.toFixed(5)}
                  </td>
                  <td className="px-3 py-2 font-mono text-emerald-600 dark:text-emerald-400">
                    ₹{item.cost_inr?.toFixed(2)}
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
