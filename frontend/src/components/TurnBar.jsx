// One turn's response time (caller stops speaking -> first agent audio) as a bar.
// One series, so one color and no legend. All bars share one scale (the slowest
// turn = full width) so they compare. The exact number is always printed.

import { formatMs } from "./ui";

export default function TurnBar({ turn, scaleMs }) {
  const total = turn.total_ms;
  const widthPct = scaleMs > 0 && total != null ? Math.max(2, (total / scaleMs) * 100) : 0;
  const label = turn.turn_index === 0 ? "Greeting" : `Turn ${turn.turn_index}`;
  const tip = [
    `${label}: ${total != null ? formatMs(total) : "no caller speech before this reply"}`,
    turn.tool_ms ? `tools ${formatMs(turn.tool_ms)} (ran alongside)` : null,
    turn.user_text ? `Caller: ${turn.user_text}` : null,
  ].filter(Boolean).join("\n");

  return (
    <div className="py-1" title={tip}>
      <div className="flex items-baseline justify-between text-xs">
        <span className="font-medium">
          {label}
          {turn.interrupted && <span className="ml-1 text-amber-600">· barge-in</span>}
        </span>
        <span className="font-semibold tabular-nums">{total != null ? formatMs(total) : "-"}</span>
      </div>
      <div className="mt-1 h-2.5 w-full">
        {widthPct > 0 && (
          <div className="h-full rounded" style={{ width: `${widthPct}%`, background: "var(--bar-response)" }} />
        )}
      </div>
      {(turn.tool_ms || total == null) && (
        <div className="mt-0.5 text-[11px] tabular-nums text-slate-500">
          {total == null && <span>agent spoke without a caller turn</span>}
          {turn.tool_ms ? <span> tools {formatMs(turn.tool_ms)}</span> : null}
        </div>
      )}
    </div>
  );
}
