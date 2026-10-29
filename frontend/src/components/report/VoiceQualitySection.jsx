import { useState } from "react";

/**
 * Section 4: Voice Quality & Audio Issues
 * Interactive 1-5 rating sliders/buttons for human evaluation,
 * local automated MOS score (if enabled), and detected audio issues.
 */

export default function VoiceQualitySection({ voiceQuality, onSaveRatings, isSaving }) {
  if (!voiceQuality) return null;

  const hr = voiceQuality.human_ratings || {};
  const [naturalness, setNaturalness] = useState(hr.naturalness ?? 4);
  const [clarity, setClarity] = useState(hr.clarity ?? 4);
  const [pronunciation, setPronunciation] = useState(hr.pronunciation ?? 4);
  const [accentFit, setAccentFit] = useState(hr.accent_fit ?? 4);
  const [politeness, setPoliteness] = useState(hr.politeness ?? 5);

  const audioIssues = voiceQuality.audio_issues || [];

  function handleSave() {
    if (onSaveRatings) {
      onSaveRatings({
        naturalness: Number(naturalness),
        clarity: Number(clarity),
        pronunciation: Number(pronunciation),
        accent_fit: Number(accentFit),
        politeness: Number(politeness),
      });
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3 dark:border-slate-800 mb-4">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
            4. Voice Quality & Audio Evaluation
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Subjective human perception ratings (1–5) and log-based audio defect detection
          </p>
        </div>

        {voiceQuality.automatic_mos && (
          <div className="flex items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs dark:border-indigo-800 dark:bg-indigo-950/40">
            <span className="font-medium text-indigo-700 dark:text-indigo-300">Automated MOS (UTMOS):</span>
            <span className="font-bold text-indigo-900 dark:text-indigo-100">{voiceQuality.automatic_mos} / 5.0</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Human Rating Inputs */}
        <div className="space-y-3 rounded-lg border border-slate-100 bg-slate-50/50 p-4 dark:border-slate-800 dark:bg-slate-800/30">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Tester Subjective Ratings (1–5 Scale)
            </h4>
            <span className="text-xs font-semibold text-slate-500">
              Avg: {hr.average ?? 4.0}/5.0
            </span>
          </div>

          {[
            { label: "Naturalness & Human Warmth", val: naturalness, set: setNaturalness },
            { label: "Audio Clarity & Intelligibility", val: clarity, set: setClarity },
            { label: "Pronunciation Accuracy", val: pronunciation, set: setPronunciation },
            { label: "Accent Fit for Target Language", val: accentFit, set: setAccentFit },
            { label: "Politeness, Tone & Professionalism", val: politeness, set: setPoliteness },
          ].map((item, idx) => (
            <div key={idx} className="flex items-center justify-between gap-3 text-xs">
              <span className="text-slate-600 dark:text-slate-400 min-w-[190px]">{item.label}</span>
              <div className="flex items-center gap-1.5">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => item.set(star)}
                    className={`h-6 w-6 rounded text-xs font-semibold transition ${
                      item.val >= star
                        ? "bg-amber-400 text-slate-900 hover:bg-amber-500"
                        : "bg-slate-200 text-slate-600 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-400"
                    }`}
                  >
                    {star}
                  </button>
                ))}
              </div>
            </div>
          ))}

          <div className="pt-2 flex justify-end">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {isSaving ? "Saving..." : "Save Ratings & Recalculate Score"}
            </button>
          </div>
        </div>

        {/* Audio Issues Detected */}
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-3">
            Audio Anomalies Detected in Logs
          </h4>

          {audioIssues.length === 0 ? (
            <div className="rounded-lg border border-emerald-100 bg-emerald-50/50 p-4 text-xs text-emerald-800 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-300">
              ✓ Clean audio delivery: No long pauses (&gt; 2s), cut-offs, or robotic phrase repetitions detected.
            </div>
          ) : (
            <div className="space-y-2">
              {audioIssues.map((issue, idx) => (
                <div
                  key={idx}
                  className="rounded-lg border border-amber-200 bg-amber-50/60 p-3 text-xs dark:border-amber-900/50 dark:bg-amber-950/20"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-amber-900 dark:text-amber-300 flex items-center gap-1">
                      <span>⚠️</span> {issue.type}
                    </span>
                    <span className="rounded bg-amber-200/80 px-2 py-0.5 text-[10px] font-semibold text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                      Severity: {issue.severity}
                    </span>
                  </div>
                  <p className="mt-1 text-slate-700 dark:text-slate-300">{issue.description}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
