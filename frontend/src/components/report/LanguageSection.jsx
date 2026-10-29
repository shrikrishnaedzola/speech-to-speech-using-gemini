/**
 * Section 6: Language Support & Code-Mixing
 * Displays target language compliance, detected caller languages,
 * code-mixing handling quality, and language-specific mishearings.
 */

export default function LanguageSection({ language }) {
  if (!language) return null;

  const adherence = language.agent_adherence_percent ?? 100;
  const cmRating = language.code_mixing_rating ?? 4;
  const detected = language.detected_caller_languages || [];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="border-b border-slate-100 pb-3 dark:border-slate-800 mb-4">
        <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
          6. Language Adherence & Code-Mixing
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Multilingual performance, dialect stability, and Hinglish/Tanglish handling
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {/* Selected vs Detected */}
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Selected Language</div>
          <div className="mt-1 text-base font-bold text-slate-800 dark:text-slate-200">
            {language.selected_language}
          </div>
          <div className="mt-1 text-[11px] text-slate-500">
            Detected caller: <span className="font-semibold text-slate-700 dark:text-slate-300">{detected.join(", ") || "None"}</span>
          </div>
        </div>

        {/* Adherence % */}
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Agent Language Adherence</div>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-xl font-extrabold text-emerald-600 dark:text-emerald-400">{adherence}%</span>
            <span className="text-[11px] text-slate-400">of turns</span>
          </div>
          <div className="mt-1 text-[11px] text-slate-500">
            {language.agent_turns_correct_language} of {language.agent_turns_total} turns in {language.selected_language}
          </div>
        </div>

        {/* Code Mixing */}
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Code-Mixing Quality</div>
          <div className="mt-1 flex items-center gap-1.5">
            <span className="text-xl font-extrabold text-slate-800 dark:text-slate-200">{cmRating}</span>
            <span className="text-xs font-semibold text-slate-400">/5.0</span>
          </div>
          <div className="mt-1 text-[11px] text-slate-600 dark:text-slate-300 truncate" title={language.code_mixing_description}>
            {language.code_mixing_description}
          </div>
        </div>

        {/* Language Mishearings */}
        <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-800 dark:bg-slate-800/40">
          <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">Language-Specific Errors</div>
          <div className="mt-1 text-xl font-extrabold text-slate-800 dark:text-slate-200">
            {language.language_specific_mishearings_count ?? 0}
          </div>
          <div className="mt-1 text-[11px] text-slate-500">Acoustic or script discrepancies</div>
        </div>
      </div>
    </div>
  );
}
