import React from 'react';
import { 
  ArrowRight, 
  Sparkles, 
  ShieldCheck, 
  Cpu, 
  Layers, 
  Compass, 
  KeyRound,
  FileCheck,
  ExternalLink,
  ChevronRight
} from 'lucide-react';
import { ScreenType } from '../types';

interface LandingPageProps {
  onNavigate: (screen: ScreenType) => void;
  onExploreDemo: () => void;
  backendOnline: boolean;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onNavigate,
  onExploreDemo,
  backendOnline,
}) => {
  return (
    <div className="min-h-screen bg-[#FBF9F5] text-[#2B2320]">
      {/* Top Editorial Navbar */}
      <header className="max-w-7xl mx-auto px-6 sm:px-10 h-20 flex items-center justify-between border-b border-[#E8E2D9]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#2B2320] text-[#FBF9F5] flex items-center justify-center font-bold text-lg shadow-sm">
            B
          </div>
          <div>
            <span className="font-serif text-2xl font-semibold tracking-tight text-[#2B2320]">
              BhoomiAI
            </span>
            <span className="hidden sm:inline-block ml-3 text-[10px] uppercase tracking-widest text-[#756C65] font-semibold">
              Revenue Record & Stamp Forensics
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 sm:gap-4">
          <button
            onClick={() => onNavigate('api')}
            className="text-xs font-semibold text-[#5A524C] hover:text-[#2B2320] transition-colors"
          >
            API Playground
          </button>
          <button
            onClick={() => onNavigate('dashboard')}
            className="text-xs font-semibold text-[#5A524C] hover:text-[#2B2320] transition-colors"
          >
            Studio
          </button>
          <button
            onClick={onExploreDemo}
            className="h-9 px-4 rounded-xl bg-[#2B2320] hover:bg-[#1A1513] text-[#FBF9F5] text-xs font-semibold shadow-xs flex items-center gap-1.5 transition-all cursor-pointer"
          >
            <span>Demo Workspace</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      {/* Hero Section: Minimal Conceptual Editorial Line Art */}
      <section className="max-w-7xl mx-auto px-6 sm:px-10 pt-14 sm:pt-20 pb-16">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          {/* Left Text Narrative (6 cols) */}
          <div className="lg:col-span-6 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#FFFFFF] border border-[#E8E2D9] text-xs font-semibold text-[#E05A47] shadow-2xs">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Smart India Hackathon 2026 · AI Revenue Tech</span>
            </div>

            <h1 className="font-serif text-5xl sm:text-6xl xl:text-7xl font-normal leading-[1.05] tracking-tight text-[#2B2320]">
              Where ancient parchment meets defensible data.
            </h1>

            <p className="text-base sm:text-lg text-[#756C65] font-light leading-relaxed max-w-xl">
              Historical land records are plagued by bleed-through, faded Urdu nastaliq, and intricate fiscal seals. BhoomiAI unrolls complex deeds into verifiable, coordinate-linked schemas with dual-engine adjudication.
            </p>

            <div className="pt-2 flex flex-wrap items-center gap-4">
              <button
                onClick={onExploreDemo}
                className="h-12 px-6 rounded-xl bg-[#2B2320] hover:bg-[#1A1513] text-[#FBF9F5] font-semibold text-sm shadow-sm flex items-center gap-2 transition-all cursor-pointer"
              >
                <span>Launch Benchmark Studio</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                onClick={() => onNavigate('api')}
                className="h-12 px-5 rounded-xl border border-[#E8E2D9] bg-[#FFFFFF] hover:bg-[#F5F1E9] text-[#2B2320] font-semibold text-sm transition-colors cursor-pointer flex items-center gap-2"
              >
                <span>Explore API</span>
              </button>
            </div>

            {/* Micro badges */}
            <div className="pt-6 border-t border-[#E8E2D9] flex flex-wrap items-center gap-6 text-xs text-[#756C65]">
              <div className="flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-[#2C5E43]" />
                <span>Court-Defensible BBoxes</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Cpu className="w-4 h-4 text-[#205E8C]" />
                <span>C++ Line-Cut Engine</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#E05A47]" />
                <span>Urdu & Devanagari Native</span>
              </div>
            </div>
          </div>

          {/* Right Hero Editorial Art (6 cols) */}
          <div className="lg:col-span-6 relative">
            <div className="rounded-3xl overflow-hidden border border-[#E8E2D9] bg-[#FFFFFF] p-3 shadow-md">
              <img
                src="/assets/hero_art.jpg"
                alt="Editorial line art of human figures examining historical deed scroll"
                className="w-full h-auto object-cover rounded-2xl"
              />
            </div>
            <div className="mt-3 text-center text-xs text-[#A89F97] italic">
              Fig 1.1 — The gestural continuum from land registry scroll to verified data ledger.
            </div>
          </div>
        </div>
      </section>

      {/* Four Pillars Section */}
      <section className="border-t border-[#E8E2D9] bg-[#FFFFFF] py-20">
        <div className="max-w-7xl mx-auto px-6 sm:px-10">
          <div className="text-xs uppercase tracking-widest font-bold text-[#E05A47] mb-2">
            System Architecture
          </div>
          <h2 className="font-serif text-3xl sm:text-4xl text-[#2B2320] font-normal tracking-tight max-w-2xl">
            Engineered for documents standard OCR fails to read.
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mt-12">
            <div className="p-6 rounded-2xl bg-[#FBF9F5] border border-[#E8E2D9] space-y-3">
              <div className="w-8 h-8 rounded-lg bg-[#F5F1E9] text-[#2B2320] flex items-center justify-center font-serif font-bold text-sm">
                01
              </div>
              <h3 className="font-serif text-lg font-semibold text-[#2B2320]">
                Tier-0 Stamp Separation
              </h3>
              <p className="text-xs text-[#756C65] leading-relaxed">
                Detects and masks circular British Indian and Princely State embossing medallions before line segmentation to prevent bleed errors.
              </p>
            </div>

            <div className="p-6 rounded-2xl bg-[#FBF9F5] border border-[#E8E2D9] space-y-3">
              <div className="w-8 h-8 rounded-lg bg-[#F5F1E9] text-[#2B2320] flex items-center justify-center font-serif font-bold text-sm">
                02
              </div>
              <h3 className="font-serif text-lg font-semibold text-[#2B2320]">
                Table-First Line Cut
              </h3>
              <p className="text-xs text-[#756C65] leading-relaxed">
                Horizontal projection and morphological kernel sweeps isolate tabular Khasra cells without shearing handwritten characters.
              </p>
            </div>

            <div className="p-6 rounded-2xl bg-[#FBF9F5] border border-[#E8E2D9] space-y-3">
              <div className="w-8 h-8 rounded-lg bg-[#F5F1E9] text-[#2B2320] flex items-center justify-center font-serif font-bold text-sm">
                03
              </div>
              <h3 className="font-serif text-lg font-semibold text-[#2B2320]">
                Dual-Engine Cross Check
              </h3>
              <p className="text-xs text-[#756C65] leading-relaxed">
                PaddleOCR (Layout-aware) and TrOCR (Vision Transformer) run in parallel; disagreements are automatically flagged for review.
              </p>
            </div>

            <div className="p-6 rounded-2xl bg-[#FBF9F5] border border-[#E8E2D9] space-y-3">
              <div className="w-8 h-8 rounded-lg bg-[#F5F1E9] text-[#2B2320] flex items-center justify-center font-serif font-bold text-sm">
                04
              </div>
              <h3 className="font-serif text-lg font-semibold text-[#2B2320]">
                Coordinate Provenance
              </h3>
              <p className="text-xs text-[#756C65] leading-relaxed">
                Every extracted field is bound to normalized pixel space coordinates, ensuring auditability in revenue appellate courts.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Cadastral Narrative Feature */}
      <section className="py-20 max-w-7xl mx-auto px-6 sm:px-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-6 rounded-3xl overflow-hidden border border-[#E8E2D9] bg-[#FFFFFF] p-3 shadow-md">
            <img
              src="/assets/khasra_art.jpg"
              alt="Editorial line art of surveyor walking along unrolling land record scroll"
              className="w-full h-auto object-cover rounded-2xl"
            />
          </div>

          <div className="lg:col-span-6 space-y-6">
            <div className="text-xs uppercase tracking-widest font-bold text-[#2C5E43]">
              Cadastral Precision
            </div>
            <h2 className="font-serif text-3xl sm:text-4xl text-[#2B2320] font-normal tracking-tight">
              A continuous thread from field boundary to land registry.
            </h2>
            <p className="text-sm text-[#756C65] leading-relaxed">
              When land records disagree, manual dispute resolution can take decades. BhoomiAI brings scientific transparency to the process by surfacing confidence scores, alternate engine hypotheses, and pixel crops directly in the interactive studio.
            </p>

            <div className="pt-2">
              <button
                onClick={() => onNavigate('workspace')}
                className="h-11 px-5 rounded-xl bg-[#2B2320] hover:bg-[#1A1513] text-[#FBF9F5] text-xs font-semibold shadow-xs flex items-center gap-2 transition-all cursor-pointer"
              >
                <span>Try Interactive Studio with Sample Deed</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Developer API Feature */}
      <section className="border-t border-[#E8E2D9] bg-[#FFFFFF] py-20">
        <div className="max-w-7xl mx-auto px-6 sm:px-10">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            <div className="lg:col-span-6 space-y-6">
              <div className="text-xs uppercase tracking-widest font-bold text-[#205E8C]">
                Integration Ready
              </div>
              <h2 className="font-serif text-3xl sm:text-4xl text-[#2B2320] font-normal tracking-tight">
                Integrate historical OCR directly into state registries.
              </h2>
              <p className="text-sm text-[#756C65] leading-relaxed">
                Connect your existing registry software with one public HTTP endpoint. Stream live processing milestones, retrieve normalized polygons, and export court-ready GeoJSON and Word records.
              </p>

              <div className="pt-2">
                <button
                  onClick={() => onNavigate('api')}
                  className="h-11 px-5 rounded-xl border border-[#E8E2D9] bg-white hover:bg-[#F5F1E9] text-[#2B2320] text-xs font-semibold flex items-center gap-2 transition-colors cursor-pointer"
                >
                  <span>Open API Playground</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <div className="lg:col-span-6 rounded-3xl overflow-hidden border border-[#E8E2D9] bg-[#FFFFFF] p-3 shadow-md">
              <img
                src="/assets/api_art.jpg"
                alt="Editorial line art of scribe quill transforming into digital brackets"
                className="w-full h-auto object-cover rounded-2xl"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#E8E2D9] bg-[#FBF9F5] py-12">
        <div className="max-w-7xl mx-auto px-6 sm:px-10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs text-[#756C65]">
            <span className="font-bold text-[#2B2320]">BhoomiAI</span>
            <span>·</span>
            <span>Smart India Hackathon 2026</span>
            <span>·</span>
            <span>Team BhoomiAI</span>
          </div>

          <div className="flex items-center gap-4 text-xs text-[#756C65]">
            <button onClick={() => onNavigate('dashboard')} className="hover:text-[#2B2320]">Studio</button>
            <button onClick={() => onNavigate('new')} className="hover:text-[#2B2320]">New Session</button>
            <button onClick={() => onNavigate('api')} className="hover:text-[#2B2320]">API</button>
            <button onClick={() => onNavigate('login')} className="hover:text-[#2B2320]">Login</button>
          </div>
        </div>
      </footer>
    </div>
  );
};
