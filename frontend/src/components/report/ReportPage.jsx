import { useEffect, useState } from "react";
import { api } from "../../api";
import CallSummarySection from "./CallSummarySection";
import AISummarySection from "./AISummarySection";
import TranscriptSection from "./TranscriptSection";
import MishearingsSection from "./MishearingsSection";
import VoiceQualitySection from "./VoiceQualitySection";
import LatencySection from "./LatencySection";
import LanguageSection from "./LanguageSection";
import AccuracySection from "./AccuracySection";
import CostSection from "./CostSection";
import IssuesSection from "./IssuesSection";

export default function ReportPage({ callId, onBack, events, settings }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSavingRatings, setIsSavingRatings] = useState(false);
  const [isRegeneratingAI, setIsRegeneratingAI] = useState(false);
  // activeTab: the current call_id or "gemini" for the sample report
  const [activeTab, setActiveTab] = useState(callId || "gemini");

  // Fetch report when activeTab changes
  useEffect(() => {
    loadReport(activeTab);
  }, [activeTab]);

  async function loadReport(targetId) {
    setLoading(true);
    setError(null);
    try {
      let data;
      if (targetId === "gemini") {
        data = await api.getSampleReport("gemini");
      } else {
        try {
          data = await api.getPostCallReport(targetId);
        } catch {
          // If call was lost between serverless lambda containers on Vercel,
          // try sending the client-collected session data.
          if (events && events.transcript?.length > 0) {
            const clientPayload = {
              call_id: targetId,
              provider: "gemini",
              model: settings?.model || "gemini-3.8-live",
              transcript: events.transcript || [],
              answers: events.formState?.answers || {},
              turn_metrics: Object.values(events.turns || {}),
              tool_calls: events.toolCalls || [],
            };
            data = await api.generatePostCallReport(targetId, { call_payload: clientPayload });
          } else {
            // Fallback to Gemini sample report
            data = await api.getSampleReport("gemini");
          }
        }
      }
      setReport(data);
    } catch (err) {
      setError(err.message || "Failed to load report");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveRatings(ratings) {
    if (!report) return;
    setIsSavingRatings(true);
    try {
      const curCallId = report.call_info?.call_id || activeTab;
      await api.saveRatings(curCallId, ratings);
      // Reload report with updated score
      await loadReport(activeTab);
    } catch (err) {
      alert(`Could not save ratings: ${err.message}`);
    } finally {
      setIsSavingRatings(false);
    }
  }

  async function handleRegenerateAISummary() {
    if (!report) return;
    setIsRegeneratingAI(true);
    try {
      const curCallId = report.call_info?.call_id || activeTab;
      const updated = await api.generatePostCallReport(curCallId, { include_ai_summary: true });
      setReport(updated);
    } catch (err) {
      alert(`AI summary generation failed: ${err.message}`);
    } finally {
      setIsRegeneratingAI(false);
    }
  }

  function handleDownload(format) {
    if (!report) return;
    const curCallId = report.call_info?.call_id || activeTab;
    const exportUrl = api.getPostCallExportUrl(curCallId, format);
    window.open(exportUrl, "_blank");
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 pb-16">
      {/* Top Test Mode Banner */}
      <div className="bg-red-600 px-4 py-1.5 text-center text-xs font-bold uppercase tracking-wider text-white shadow-sm">
        TEST MODE — DUMMY DATA ONLY
      </div>

      {/* Navigation & Header */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur-md dark:border-slate-800 dark:bg-slate-900/95">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <button
              onClick={onBack}
              className="flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              ← Back to Tester
            </button>
            <div>
              <h1 className="text-base font-bold leading-tight">
                Post-Call Performance Report
              </h1>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Unified cross-provider evaluation module for Zolabs Voice Form Testers
              </p>
            </div>
          </div>

          {/* Export Action Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => handleDownload("pdf")}
              disabled={loading || !report}
              className="flex items-center gap-1 rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
            >
              📄 Download PDF
            </button>
            <button
              onClick={() => handleDownload("md")}
              disabled={loading || !report}
              className="flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
            >
              📝 Markdown
            </button>
            <button
              onClick={() => handleDownload("json")}
              disabled={loading || !report}
              className="flex items-center gap-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
            >
              📦 JSON (Comparison)
            </button>
          </div>
        </div>

        {/* Report Tab Row */}
        <div className="mx-auto max-w-7xl mt-3 flex flex-wrap items-center gap-1 border-t border-slate-100 pt-2.5 dark:border-slate-800">
          <span className="text-xs font-semibold text-slate-500 mr-2">View Report:</span>

          {/* Current real call (shown only when opened from a live/simulated call) */}
          {callId && (
            <button
              onClick={() => setActiveTab(callId)}
              className={`rounded-md px-3 py-1 text-xs font-semibold transition ${
                activeTab === callId
                  ? "bg-emerald-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
              }`}
            >
              📞 Current Call ({callId.slice(-6)})
            </button>
          )}

          {/* Gemini sample report tab */}
          <button
            onClick={() => setActiveTab("gemini")}
            className={`rounded-md px-3 py-1 text-xs font-semibold transition ${
              activeTab === "gemini"
                ? "bg-emerald-600 text-white"
                : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
            }`}
          >
            🔵 Gemini Sample
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-7xl px-4 pt-6">
        {loading ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-emerald-600 border-t-transparent" />
            <p className="text-xs text-slate-500">Computing call metrics and compiling report...</p>
          </div>
        ) : error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-xs text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
            <p className="font-bold text-sm mb-1">Failed to Load Report</p>
            <p>{error}</p>
            <button
              onClick={() => loadReport(activeTab)}
              className="mt-3 rounded-md bg-red-600 px-3 py-1 text-white hover:bg-red-700"
            >
              Retry
            </button>
          </div>
        ) : report ? (
          <div className="space-y-6">
            {/* Security Alerts Banner if any */}
            {report.metadata?.security_warnings?.length > 0 && (
              <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
                <span className="font-bold">⚠️ Security Notice: </span>
                {report.metadata.security_warnings.join(" · ")}
              </div>
            )}

            {/* Section 1: Call Summary */}
            <CallSummarySection callInfo={report.call_info} scoring={report.scoring} />

            {/* Section 10: AI-Written Executive Summary */}
            <AISummarySection
              aiSummary={report.ai_summary}
              onRegenerate={handleRegenerateAISummary}
              isRegenerating={isRegeneratingAI}
            />

            {/* Section 2: Transcript */}
            <TranscriptSection transcript={report.transcript} />

            {/* Section 3: Mishearings */}
            <MishearingsSection mishearings={report.mishearings} />

            {/* Section 4: Voice Quality & Audio Issues */}
            <VoiceQualitySection
              voiceQuality={report.voice_quality}
              onSaveRatings={handleSaveRatings}
              isSaving={isSavingRatings}
            />

            {/* Section 5: Latency Analysis */}
            <LatencySection latency={report.latency} />

            {/* Section 6: Language Support */}
            <LanguageSection language={report.language} />

            {/* Section 7: Accuracy & Tool Calls */}
            <AccuracySection accuracy={report.accuracy} />

            {/* Section 8: Cost Analysis */}
            <CostSection cost={report.cost} />

            {/* Section 9: Issues & Recommendations */}
            <IssuesSection issues={report.issues_and_recommendations} />

            {/* Mandatory Footer Notice */}
            <footer className="mt-8 border-t border-slate-200 pt-4 text-center text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
              <p>{report.metadata?.footer_notice || "AI-assisted test report - must be reviewed by a team member before sharing outside EdZola."}</p>
              <p className="mt-1 text-[11px] text-slate-400">
                Generated by Zolabs Post-Call Report Module · Gemini Voice Form Tester
              </p>
            </footer>
          </div>
        ) : null}
      </main>
    </div>
  );
}
