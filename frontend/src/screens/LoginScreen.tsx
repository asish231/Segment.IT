import React, { useState } from 'react';
import { Shield, Sparkles, ArrowRight, KeyRound } from 'lucide-react';

interface LoginScreenProps {
  onLoginSuccess: (email: string) => void;
  onExploreDemo: () => void;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({
  onLoginSuccess,
  onExploreDemo,
}) => {
  const [email, setEmail] = useState('asish@team-revision.in');
  const [password, setPassword] = useState('••••••••••••');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // False/Mock auth: any email/password enters immediately
    onLoginSuccess(email || 'asish@team-revision.in');
  };

  return (
    <div className="min-h-screen w-full flex bg-[#FBF9F5] text-[#2B2320]">
      {/* Left Column: Editorial Hero */}
      <div className="hidden lg:flex lg:w-7/12 bg-[#2B2320] text-[#FBF9F5] p-16 flex-col justify-between relative overflow-hidden">
        {/* Subtle background glow & editorial illustration overlay */}
        <div 
          className="absolute inset-0 opacity-15 bg-cover bg-center mix-blend-luminosity pointer-events-none"
          style={{ backgroundImage: `url('/assets/hero_art.jpg')` }}
        />
        <div className="absolute -right-24 -bottom-24 w-96 h-96 rounded-full bg-[#E05A47]/10 blur-3xl pointer-events-none" />

        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#FBF9F5] text-[#2B2320] flex items-center justify-center font-bold text-xl shadow-md">
              B
            </div>
            <div>
              <div className="font-serif text-2xl tracking-tight font-semibold">
                BhoomiAI
              </div>
              <div className="text-[10px] uppercase tracking-widest text-[#A89F97] font-semibold">
                Benchmark Studio
              </div>
            </div>
          </div>

          <div className="mt-28 max-w-xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#FFFFFF]/10 border border-[#FFFFFF]/15 text-[#E05A47] text-xs font-semibold mb-6">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Smart India Hackathon 2026 · AI Revenue Tech</span>
            </div>
            
            <h1 className="font-serif text-5xl xl:text-6xl font-normal leading-[1.08] tracking-tight text-[#FBF9F5]">
              Turn difficult records into defensible data.
            </h1>
            
            <p className="mt-6 text-lg text-[#D5CDC2] font-light leading-relaxed max-w-lg">
              A transparent, verifiable OCR workspace for Tier-0 stamp neutralization, table-first cadastral segmentation, dual-engine comparison, and coordinate audit trails.
            </p>
          </div>
        </div>

        {/* Feature Pills */}
        <div className="relative z-10 pt-12">
          <div className="flex flex-wrap gap-3">
            <div className="px-4 py-2.5 rounded-xl bg-[#FFFFFF]/08 border border-[#FFFFFF]/15 backdrop-blur-sm text-sm font-medium text-[#FBF9F5] flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#E05A47]" />
              Dual OCR Engine
            </div>
            <div className="px-4 py-2.5 rounded-xl bg-[#FFFFFF]/08 border border-[#FFFFFF]/15 backdrop-blur-sm text-sm font-medium text-[#FBF9F5] flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#2C5E43]" />
              Evidence-Linked Coords
            </div>
            <div className="px-4 py-2.5 rounded-xl bg-[#FFFFFF]/08 border border-[#FFFFFF]/15 backdrop-blur-sm text-sm font-medium text-[#FBF9F5] flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#C89D55]" />
              Schema-First Validation
            </div>
          </div>
        </div>
      </div>

      {/* Right Column: Sign In Card */}
      <div className="w-full lg:w-5/12 flex items-center justify-center p-8 sm:p-14">
        <div className="w-full max-w-md space-y-8">
          <div>
            <div className="text-xs uppercase tracking-widest font-bold text-[#E05A47] mb-2">
              Welcome back
            </div>
            <h2 className="font-serif text-3xl sm:text-4xl text-[#2B2320] font-normal tracking-tight">
              Sign in to continue
            </h2>
            <p className="mt-2 text-sm text-[#756C65]">
              Access benchmark datasets, interactive correction studio, and the live OCR backend.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold text-[#2B2320] mb-2">
                Email address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@agency.gov.in"
                className="w-full h-12 px-4 rounded-xl border border-[#E8E2D9] bg-[#FFFFFF] text-sm text-[#2B2320] focus:outline-none focus:ring-2 focus:ring-[#2B2320] focus:border-transparent transition-all shadow-2xs"
                required
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-semibold text-[#2B2320]">
                  Password
                </label>
                <span className="text-[11px] text-[#A89F97]">Any password accepted</span>
              </div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full h-12 px-4 rounded-xl border border-[#E8E2D9] bg-[#FFFFFF] text-sm text-[#2B2320] focus:outline-none focus:ring-2 focus:ring-[#2B2320] focus:border-transparent transition-all shadow-2xs"
                required
              />
            </div>

            <button
              type="submit"
              className="w-full h-12 rounded-xl bg-[#2B2320] hover:bg-[#181412] text-[#FBF9F5] font-semibold text-sm transition-all shadow-xs flex items-center justify-center gap-2 group cursor-pointer"
            >
              <span>Sign in</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
            </button>
          </form>

          {/* 1-Click Demo Workspace Button */}
          <div className="pt-2">
            <button
              onClick={onExploreDemo}
              className="w-full p-4 rounded-xl bg-[#F0F6F8] hover:bg-[#E4EFF3] border border-[#CFE2EA] text-[#1F364D] text-center transition-all cursor-pointer group"
            >
              <div className="flex items-center justify-center gap-2 text-xs font-bold uppercase tracking-wider text-[#205E8C] mb-1">
                <KeyRound className="w-3.5 h-3.5" />
                <span>Demo workspace · SIH 2026</span>
              </div>
              <p className="text-xs text-[#526B7E]">
                One-click instant access to live pre-loaded Urdu & Devanagari records.
              </p>
            </button>
          </div>

          <div className="flex items-center justify-center gap-2 text-[11px] text-[#756C65] pt-4 border-t border-[#E8E2D9]">
            <Shield className="w-3.5 h-3.5 text-[#2C5E43]" />
            <span>False authentication enabled for evaluation. Any credentials proceed.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
