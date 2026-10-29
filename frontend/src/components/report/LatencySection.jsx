import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceArea,
} from "recharts";

/**
 * Section 5: Latency Analysis (Gemini)
 * Displays average, median, p90, max reply times,
 * interactive Recharts turn-by-turn reply time line chart,
 * and the 3 slowest turns with diagnostic reasons.
 */

export default function LatencySection({ latency }) {
  if (!latency) return null;

  const chartData = latency.turn_chart_data || [];
  const rating = latency.rating || "Good";

  const ratingStyles = {
    Good: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
    OK: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
    Poor: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  }[rating] || "bg-slate-100 text-slate-800";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3 dark:border-slate-800 mb-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            5. Latency & Turn Reply Speeds
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Time from caller finish to Gemini audio output (ms)
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${ratingStyles}`}>
            Rating: {rating} ({latency.average_ms} ms avg)
          </span>
        </div>
      </div>

      {/* Latency Stats Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-4">
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Average Latency</div>
          <div className="mt-1 text-xl font-extrabold text-slate-800 dark:text-slate-200">{latency.average_ms} ms</div>
          <div className="text-[10px] text-slate-400">Benchmark: &lt;1000ms</div>
        </div>
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Median (p50)</div>
          <div className="mt-1 text-xl font-extrabold text-slate-800 dark:text-slate-200">{latency.median_ms} ms</div>
          <div className="text-[10px] text-slate-400">Typical response</div>
        </div>
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">90th Percentile (p90)</div>
          <div className="mt-1 text-xl font-extrabold text-slate-800 dark:text-slate-200">{latency.p90_ms} ms</div>
          <div className="text-[10px] text-slate-400">Tail latency</div>
        </div>
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Maximum Latency</div>
          <div className="mt-1 text-xl font-extrabold text-slate-800 dark:text-slate-200">{latency.max_ms} ms</div>
          <div className="text-[10px] text-slate-400">Worst turn delay</div>
        </div>
      </div>

      {/* Chart */}
      <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-4 dark:border-slate-800 dark:bg-slate-800/20 mb-5">
        <div className="flex items-center justify-between mb-3 text-xs">
          <span className="font-semibold text-slate-700 dark:text-slate-300">
            Response Latency per Turn
          </span>
          <div className="flex items-center gap-3 text-[11px] text-slate-500">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-emerald-500" /> Good (&lt;1000ms)
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-amber-500" /> OK (1000-1500ms)
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-red-500" /> Poor (&gt;1500ms)
            </span>
          </div>
        </div>

        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="turn_index" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(val) => [`${val} ms`, "Total Latency"]}
                contentStyle={{ backgroundColor: "#1e293b", borderColor: "#334155", color: "#fff", fontSize: "12px", borderRadius: "8px" }}
              />
              <ReferenceArea y1={0} y2={1000} fill="#10b981" fillOpacity={0.07} />
              <ReferenceArea y1={1000} y2={1500} fill="#f59e0b" fillOpacity={0.07} />
              <ReferenceArea y1={1500} y2={3000} fill="#ef4444" fillOpacity={0.07} />
              <Line
                type="monotone"
                dataKey="total_ms"
                stroke="#059669"
                strokeWidth={2.5}
                dot={{ r: 4, fill: "#059669" }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Slowest 3 Turns Details */}
      {latency.slowest_turns?.length > 0 && (
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-2">
            Slowest 3 Turns & Diagnostic Root Causes
          </h4>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {latency.slowest_turns.map((st, i) => (
              <div
                key={i}
                className="rounded-lg border border-slate-200 bg-white p-3 text-xs shadow-xs dark:border-slate-800 dark:bg-slate-800/50"
              >
                <div className="flex items-center justify-between font-semibold">
                  <span className="text-slate-800 dark:text-slate-200">Turn #{st.turn_index}</span>
                  <span className="rounded bg-red-100 px-1.5 py-0.5 font-bold text-red-700 dark:bg-red-950 dark:text-red-300">
                    {st.latency_ms} ms
                  </span>
                </div>
                <p className="mt-1.5 font-medium text-slate-600 dark:text-slate-300">
                  {st.reason}
                </p>
                {st.user_said && (
                  <p className="mt-1 text-[11px] text-slate-500 italic truncate" title={st.user_said}>
                    Caller: &ldquo;{st.user_said}&rdquo;
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
