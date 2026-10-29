// Advanced settings: voice activity detection, tool behaviour, thinking and cost rates.

import { NumberInput, Select } from "./ui";

const SENSITIVITY = [
  { value: "default", label: "default" },
  { value: "high", label: "high" },
  { value: "low", label: "low" },
];

export default function SettingsDrawer({ settings, setSettings, options, disabled, simSpeed, setSimSpeed }) {
  const set = (key) => (value) => setSettings((s) => ({ ...s, [key]: value }));
  const model = options.models.find((m) => m.id === settings.model) ?? {};
  return (
    <details className="mt-3 rounded-lg border border-slate-200 p-2 text-sm dark:border-slate-800">
      <summary className="cursor-pointer font-medium">Settings (VAD, tools, thinking, cost rates)</summary>

      <p className="mt-2 text-xs font-medium text-slate-600 dark:text-slate-400">Voice activity detection (Gemini, automatic)</p>
      <div className="mt-1 grid grid-cols-2 gap-2">
        <Select label="Start-of-speech sensitivity" value={settings.vad_start_sensitivity}
          onChange={set("vad_start_sensitivity")} options={SENSITIVITY} disabled={disabled} />
        <Select label="End-of-speech sensitivity" value={settings.vad_end_sensitivity}
          onChange={set("vad_end_sensitivity")} options={SENSITIVITY} disabled={disabled} />
        <NumberInput label="Silence before end of turn (ms)" value={settings.vad_silence_ms} onChange={set("vad_silence_ms")}
          disabled={disabled} hint="How long the caller must be quiet before Gemini answers. Docs recommend 500-800." />
        <NumberInput label="Prefix padding (ms)" value={settings.vad_prefix_padding_ms} onChange={set("vad_prefix_padding_ms")}
          disabled={disabled} hint="Speech needed before a start of speech is committed." />
      </div>

      <p className="mt-3 text-xs font-medium text-slate-600 dark:text-slate-400">Tool calls</p>
      <div className="mt-1 grid grid-cols-2 gap-2">
        <Select label="Tool behaviour" value={model.supports_scheduling ? settings.tool_behavior : "NON_BLOCKING"}
          onChange={set("tool_behavior")} disabled={disabled || !model.supports_scheduling}
          options={[{ value: "NON_BLOCKING", label: "NON_BLOCKING (async)" }, { value: "BLOCKING", label: "BLOCKING" }]} />
        <Select label="Scheduling for successful saves" value={settings.save_ok_scheduling}
          onChange={set("save_ok_scheduling")} disabled={disabled || !model.supports_scheduling}
          options={[
            { value: "AUTO", label: "AUTO (SILENT if talking, else WHEN_IDLE)" },
            { value: "SILENT", label: "always SILENT" },
            { value: "WHEN_IDLE", label: "always WHEN_IDLE" },
          ]} />
        <NumberInput label="Tool timeout (ms)" value={settings.tool_timeout_ms} onChange={set("tool_timeout_ms")} disabled={disabled} />
        <NumberInput label="Retries after failure" value={settings.tool_max_retries} onChange={set("tool_max_retries")} disabled={disabled} />
        <NumberInput label="Extra tool delay (ms)" value={settings.tool_delay_ms} onChange={set("tool_delay_ms")} disabled={disabled}
          hint="Pretend our backend is slow, to watch the agent keep talking during a tool call. 0 = off." />
        <Select label="Thinking level (extended only)" value={settings.thinking_level} onChange={set("thinking_level")}
          disabled={disabled || !model.supports_thinking_level}
          options={["low", "medium", "high"].map((v) => ({ value: v, label: v }))} />
      </div>
      {!model.supports_scheduling && (
        <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
          Extended thinking: tools are always NON_BLOCKING and scheduling is not supported, so errors rely on the
          prompt to make the agent re-ask.
        </p>
      )}
      <NumberInput label="Simulate speed (x)" step={0.5} value={simSpeed} onChange={setSimSpeed} disabled={disabled} />

      <p className="mt-3 text-xs font-medium text-slate-600 dark:text-slate-400">Cost rates (USD per 1M tokens, Gemini pricing page)</p>
      <div className="mt-1 grid grid-cols-2 gap-2">
        <NumberInput label="Audio input" step={0.05} value={settings.rate_audio_input_per_1m} onChange={set("rate_audio_input_per_1m")} />
        <NumberInput label="Text input" step={0.05} value={settings.rate_text_input_per_1m} onChange={set("rate_text_input_per_1m")} />
        <NumberInput label="Audio output" step={0.05} value={settings.rate_audio_output_per_1m} onChange={set("rate_audio_output_per_1m")} />
        <NumberInput label="Text output (incl. thinking)" step={0.05} value={settings.rate_text_output_per_1m} onChange={set("rate_text_output_per_1m")} />
        <NumberInput label="USD → INR" step={0.5} value={settings.usd_to_inr} onChange={set("usd_to_inr")} />
        <Select label="Usage counting" value={settings.usage_counting} onChange={set("usage_counting")} disabled={disabled}
          options={[{ value: "sum", label: "sum every usage message" }, { value: "last", label: "running total (take latest)" }]} />
      </div>
      <p className="mt-2 text-xs text-slate-500">Settings are saved with each call when it starts.</p>
    </details>
  );
}
