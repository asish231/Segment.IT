import React from 'react';
import { 
  PlusCircle, 
  TrendingUp, 
  AlertTriangle, 
  Clock, 
  CheckCircle2, 
  FileText, 
  ChevronRight, 
  Sparkles,
  ArrowUpRight,
  Database
} from 'lucide-react';
import { BenchmarkSession, ScreenType } from '../types';

interface DashboardScreenProps {
  sessions: BenchmarkSession[];
  onSelectSession: (session: BenchmarkSession) => void;
  onNavigate: (screen: ScreenType) => void;
  backendOnline: boolean;
}

export const DashboardScreen: React.FC<DashboardScreenProps> = ({
  sessions,
  onSelectSession,
  onNavigate,
  backendOnline,
}) => {
  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#E8E2D9] pb-6">
        <div>
          <div className="text-xs uppercase tracking-widest font-bold text-[#E05A47] mb-1">
            Sunday, 14 September 2026
          </div>
          <h1 className="font-serif text-3xl sm:text-4xl text-[#2B2320] font-normal tracking-tight">
            Benchmark overview
          </h1>
          <p className="text-sm text-[#756C65] mt-1">
            Track extraction precision, dual-engine agreement, and continue active evaluation sessions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => onNavigate('new')}
            className="h-10 px-4 rounded-xl bg-[#2B2320] hover:bg-[#1A1513] text-[#FBF9F5] text-xs font-semibold shadow-xs flex items-center gap-2 transition-all cursor-pointer"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Start benchmark</span>
          </button>
        </div>
      </div>

      {/* 4 Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#FFFFFF] border border-[#E8E2D9] rounded-2xl p-5 shadow-2xs hover:border-[#D5CDC2] transition-colors">
          <div className="text-xs font-medium text-[#756C65]">Sessions evaluated</div>
          <div className="font-serif text-3xl font-semibold text-[#2B2320] my-2">
            24
          </div>
          <div className="flex items-center gap-1.5 text-xs text-[#2C5E43] font-medium">
            <TrendingUp className="w-3.5 h-3.5" />
            <span>↗ 6 this week</span>
          </div>
        </div>

        <div className="bg-[#FFFFFF] border border-[#E8E2D9] rounded-2xl p-5 shadow-2xs hover:border-[#D5CDC2] transition-colors">
          <div className="text-xs font-medium text-[#756C65]">Final field accuracy</div>
          <div className="font-serif text-3xl font-semibold text-[#2B2320] my-2">
            94.2%
          </div>
          <div className="flex items-center gap-1.5 text-xs text-[#2C5E43] font-medium">
            <TrendingUp className="w-3.5 h-3.5" />
            <span>↗ 8.7% after review</span>
          </div>
        </div>

        <div className="bg-[#FFFFFF] border border-[#E8E2D9] rounded-2xl p-5 shadow-2xs hover:border-[#D5CDC2] transition-colors">
          <div className="text-xs font-medium text-[#756C65]">Review required</div>
          <div className="font-serif text-3xl font-semibold text-[#E05A47] my-2">
            03
          </div>
          <div className="flex items-center gap-1.5 text-xs text-[#C89D55] font-medium">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>12 fields unresolved</span>
          </div>
        </div>

        <div className="bg-[#FFFFFF] border border-[#E8E2D9] rounded-2xl p-5 shadow-2xs hover:border-[#D5CDC2] transition-colors">
          <div className="text-xs font-medium text-[#756C65]">Median processing</div>
          <div className="font-serif text-3xl font-semibold text-[#2B2320] my-2">
            8.4s
          </div>
          <div className="flex items-center gap-1.5 text-xs text-[#2C5E43] font-medium">
            <Clock className="w-3.5 h-3.5" />
            <span>1.2s faster with C++ cut</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Sessions & Live Pipeline */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Recent Sessions (7 cols) */}
        <div className="lg:col-span-7 bg-[#FFFFFF] border border-[#E8E2D9] rounded-2xl p-6 shadow-2xs">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="font-serif text-xl font-medium text-[#2B2320]">
                Recent sessions
              </h3>
              <p className="text-xs text-[#756C65] mt-0.5">
                Click any benchmark run to inspect coordinates in the interactive studio.
              </p>
            </div>
            <button 
              onClick={() => onNavigate('new')}
              className="text-xs font-semibold text-[#205E8C] hover:text-[#17232D] transition-colors"
            >
              View all
            </button>
          </div>

          <div className="divide-y divide-[#F0ECE6]">
            {sessions.map((sess) => (
              <div
                key={sess.id}
                onClick={() => onSelectSession(sess)}
                className="py-4 flex items-center justify-between gap-4 group cursor-pointer hover:bg-[#FBF9F5] -mx-4 px-4 rounded-xl transition-all"
              >
                <div className="flex items-center gap-3.5 min-w-0">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 ${
                    sess.documentType === 'PDF' 
                      ? 'bg-[#EBF3FB] text-[#205E8C] border border-[#D5E5F6]' 
                      : 'bg-[#FDF3E7] text-[#C89D55] border border-[#F6E1C7]'
                  }`}>
                    {sess.documentType}
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-[#2B2320] group-hover:text-[#E05A47] transition-colors truncate">
                      {sess.title}
                    </div>
                    <div className="text-xs text-[#756C65] mt-0.5">
                      {sess.script} · {sess.totalFields} fields {sess.correctionsCount > 0 ? `· ${sess.correctionsCount} corrections` : ''}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-5 shrink-0">
                  <div className="w-28 text-right hidden sm:block">
                    <div className="flex items-center justify-end gap-1.5">
                      <span className={`inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full ${
                        sess.status === 'complete'
                          ? 'bg-[#EAF4ED] text-[#2C5E43]'
                          : sess.status === 'review'
                          ? 'bg-[#FEF1EC] text-[#E05A47]'
                          : 'bg-[#EBF3FB] text-[#205E8C]'
                      }`}>
                        {sess.status === 'complete' ? '✓ Complete' : sess.status === 'review' ? '! Review' : '● Running'}
                      </span>
                    </div>
                    <div className="w-full bg-[#EAE5DD] h-1.5 rounded-full mt-2 overflow-hidden">
                      <div 
                        className={`h-full rounded-full ${sess.accuracy > 90 ? 'bg-[#2C5E43]' : 'bg-[#E05A47]'}`}
                        style={{ width: `${sess.accuracy}%` }}
                      />
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="font-mono text-sm font-semibold text-[#2B2320]">
                      {sess.accuracy ? `${sess.accuracy}%` : '—'}
                    </span>
                  </div>

                  <ChevronRight className="w-4 h-4 text-[#A89F97] group-hover:text-[#2B2320] group-hover:translate-x-0.5 transition-all" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Live Pipeline & Quick Actions (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Live Pipeline Visualizer */}
          <div className="bg-[#FFFFFF] border border-[#E8E2D9] rounded-2xl p-6 shadow-2xs">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-serif text-xl font-medium text-[#2B2320]">
                Live pipeline
              </h3>
              <span className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full ${
                backendOnline 
                  ? 'bg-[#EAF4ED] text-[#2C5E43] border border-[#D0E6D7]'
                  : 'bg-[#FEF1EC] text-[#E05A47] border border-[#FADCD5]'
              }`}>
                <span className="w-1.5 h-1.5 rounded-full bg-current" />
                {backendOnline ? 'Healthy' : 'Disconnected'}
              </span>
            </div>

            <p className="text-xs text-[#756C65] mb-5">
              Active microservices executing on local port 8000:
            </p>

            <div className="grid grid-cols-5 gap-2">
              <div className="p-2.5 rounded-xl border border-[#D0E6D7] bg-[#EAF4ED] text-center">
                <div className="w-5 h-5 rounded-full bg-[#2C5E43] text-white flex items-center justify-center text-[10px] mx-auto mb-1">
                  ✓
                </div>
                <div className="text-[11px] font-bold text-[#2B2320]">Orient</div>
                <div className="text-[9px] text-[#756C65]">0.3s</div>
              </div>

              <div className="p-2.5 rounded-xl border border-[#D0E6D7] bg-[#EAF4ED] text-center">
                <div className="w-5 h-5 rounded-full bg-[#2C5E43] text-white flex items-center justify-center text-[10px] mx-auto mb-1">
                  ✓
                </div>
                <div className="text-[11px] font-bold text-[#2B2320]">Segment</div>
                <div className="text-[9px] text-[#756C65]">1.2s</div>
              </div>

              <div className="p-2.5 rounded-xl border border-[#D0E6D7] bg-[#EAF4ED] text-center">
                <div className="w-5 h-5 rounded-full bg-[#2C5E43] text-white flex items-center justify-center text-[10px] mx-auto mb-1">
                  ✓
                </div>
                <div className="text-[11px] font-bold text-[#2B2320]">OCR</div>
                <div className="text-[9px] text-[#756C65]">Dual</div>
              </div>

              <div className="p-2.5 rounded-xl border border-[#E8E2D9] bg-[#FBF9F5] text-center">
                <div className="w-5 h-5 rounded-full bg-[#2B2320] text-white flex items-center justify-center text-[10px] mx-auto mb-1">
                  4
                </div>
                <div className="text-[11px] font-bold text-[#2B2320]">Structure</div>
                <div className="text-[9px] text-[#756C65]">JSON</div>
              </div>

              <div className="p-2.5 rounded-xl border border-[#E8E2D9] bg-[#FBF9F5] text-center">
                <div className="w-5 h-5 rounded-full bg-[#A89F97] text-white flex items-center justify-center text-[10px] mx-auto mb-1">
                  5
                </div>
                <div className="text-[11px] font-bold text-[#2B2320]">Validate</div>
                <div className="text-[9px] text-[#756C65]">Coords</div>
              </div>
            </div>
          </div>

          {/* Quick Action Tiles */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div 
              onClick={() => onNavigate('api')}
              className="bg-[#FFFFFF] border border-[#E8E2D9] hover:border-[#2B2320] rounded-2xl p-5 cursor-pointer group transition-all"
            >
              <div className="w-8 h-8 rounded-lg bg-[#F5F1E9] text-[#2B2320] flex items-center justify-center mb-3 group-hover:bg-[#2B2320] group-hover:text-white transition-colors">
                <ArrowUpRight className="w-4 h-4" />
              </div>
              <div className="text-sm font-semibold text-[#2B2320] mb-1">
                Use the API
              </div>
              <p className="text-xs text-[#756C65] leading-relaxed">
                Send a document and schema directly from your application via cURL.
              </p>
            </div>

            <div 
              onClick={() => onNavigate('workspace')}
              className="bg-[#FFFFFF] border border-[#E8E2D9] hover:border-[#2B2320] rounded-2xl p-5 cursor-pointer group transition-all"
            >
              <div className="w-8 h-8 rounded-lg bg-[#F5F1E9] text-[#2B2320] flex items-center justify-center mb-3 group-hover:bg-[#2B2320] group-hover:text-white transition-colors">
                <Sparkles className="w-4 h-4 text-[#E05A47]" />
              </div>
              <div className="text-sm font-semibold text-[#2B2320] mb-1">
                Benchmark mode
              </div>
              <p className="text-xs text-[#756C65] leading-relaxed">
                Compare extraction against verified revenue ground truth coordinates.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
