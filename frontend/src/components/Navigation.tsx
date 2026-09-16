import React from 'react';
import { 
  LayoutDashboard, 
  PlusCircle, 
  Sparkles, 
  CheckCircle2, 
  Terminal, 
  Compass, 
  LogOut, 
  ShieldCheck,
  HelpCircle,
  Settings
} from 'lucide-react';
import { ScreenType } from '../types';

interface NavigationProps {
  currentScreen: ScreenType;
  onNavigate: (screen: ScreenType) => void;
  backendOnline: boolean;
  userEmail?: string;
  onLogout: () => void;
}

export const Sidebar: React.FC<NavigationProps> = ({
  currentScreen,
  onNavigate,
  backendOnline,
  onLogout,
}) => {
  return (
    <aside className="w-64 bg-[#FFFFFF]/80 backdrop-blur-md border-r border-[#E8E2D9] p-5 flex flex-col justify-between shrink-0 h-screen sticky top-0">
      <div>
        {/* Brand */}
        <div 
          onClick={() => onNavigate('landing')}
          className="flex items-center gap-3 px-2 py-2 mb-6 cursor-pointer group"
        >
          <div className="w-9 h-9 rounded-xl bg-[#2B2320] text-[#FBF9F5] flex items-center justify-center font-bold text-lg shadow-sm group-hover:bg-[#E05A47] transition-colors">
            B
          </div>
          <div>
            <div className="font-serif text-xl tracking-tight font-semibold text-[#2B2320] flex items-center gap-1.5">
              BhoomiAI
            </div>
            <div className="text-[9px] uppercase tracking-widest text-[#756C65] font-semibold">
              Benchmark Studio
            </div>
          </div>
        </div>

        {/* Navigation Sections */}
        <div className="space-y-6">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-[#A89F97] px-3 mb-2">
              Workspace
            </div>
            <nav className="space-y-1">
              <button
                onClick={() => onNavigate('dashboard')}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                  currentScreen === 'dashboard'
                    ? 'bg-[#2B2320] text-[#FBF9F5] shadow-xs'
                    : 'text-[#5A524C] hover:bg-[#F5F1E9] hover:text-[#2B2320]'
                }`}
              >
                <LayoutDashboard className="w-4 h-4 opacity-80" />
                <span>Overview</span>
              </button>

              <button
                onClick={() => onNavigate('new')}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                  currentScreen === 'new'
                    ? 'bg-[#2B2320] text-[#FBF9F5] shadow-xs'
                    : 'text-[#5A524C] hover:bg-[#F5F1E9] hover:text-[#2B2320]'
                }`}
              >
                <PlusCircle className="w-4 h-4 opacity-80" />
                <span>New session</span>
              </button>

              <button
                onClick={() => onNavigate('workspace')}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                  currentScreen === 'workspace'
                    ? 'bg-[#2B2320] text-[#FBF9F5] shadow-xs'
                    : 'text-[#5A524C] hover:bg-[#F5F1E9] hover:text-[#2B2320]'
                }`}
              >
                <Sparkles className="w-4 h-4 opacity-80 text-[#E05A47]" />
                <span>Interactive studio</span>
              </button>

              <button
                onClick={() => onNavigate('results')}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                  currentScreen === 'results'
                    ? 'bg-[#2B2320] text-[#FBF9F5] shadow-xs'
                    : 'text-[#5A524C] hover:bg-[#F5F1E9] hover:text-[#2B2320]'
                }`}
              >
                <CheckCircle2 className="w-4 h-4 opacity-80 text-[#2C5E43]" />
                <span>Results</span>
              </button>
            </nav>
          </div>

          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-[#A89F97] px-3 mb-2">
              Developers
            </div>
            <nav className="space-y-1">
              <button
                onClick={() => onNavigate('api')}
                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                  currentScreen === 'api'
                    ? 'bg-[#2B2320] text-[#FBF9F5] shadow-xs'
                    : 'text-[#5A524C] hover:bg-[#F5F1E9] hover:text-[#2B2320]'
                }`}
              >
                <Terminal className="w-4 h-4 opacity-80" />
                <span>API playground</span>
              </button>

              <button
                onClick={() => onNavigate('landing')}
                className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-[#756C65] hover:bg-[#F5F1E9] hover:text-[#2B2320] transition-all"
              >
                <Compass className="w-4 h-4 opacity-80" />
                <span>Editorial narrative</span>
              </button>
            </nav>
          </div>
        </div>
      </div>

      {/* Footer System Status & User Profile */}
      <div className="space-y-4 pt-4 border-t border-[#E8E2D9]">
        {/* Pipeline Online Card */}
        <div className="bg-[#F8F5EE] border border-[#E4DCD3] rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <span className={`w-2 h-2 rounded-full ${backendOnline ? 'bg-[#2C5E43]' : 'bg-[#E05A47]'}`} />
            <span className="text-xs font-semibold text-[#2B2320]">
              {backendOnline ? 'Pipeline online' : 'Backend offline'}
            </span>
          </div>
          <p className="text-[11px] text-[#756C65] leading-relaxed">
            PaddleOCR, Tier-0 Stamp Cutter & TrOCR workers active.
          </p>
        </div>

        {/* User Card */}
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#E05A47] to-[#C89D55] text-white flex items-center justify-center text-xs font-bold shadow-xs">
              AS
            </div>
            <div>
              <div className="text-xs font-bold text-[#2B2320]">Asish Sharma</div>
              <div className="text-[10px] text-[#756C65]">Project Lead · SIH 2026</div>
            </div>
          </div>
          <button 
            onClick={onLogout}
            title="Sign out / Demo Reset"
            className="text-[#A89F97] hover:text-[#E05A47] transition-colors p-1"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};

export const Topbar: React.FC<{
  currentScreen: ScreenType;
  onNavigate: (screen: ScreenType) => void;
  backendOnline: boolean;
}> = ({ currentScreen, onNavigate, backendOnline }) => {
  const getCrumbTitle = () => {
    switch (currentScreen) {
      case 'dashboard': return 'Overview';
      case 'new': return 'New benchmark session';
      case 'workspace': return 'Interactive studio';
      case 'results': return 'Benchmark result';
      case 'api': return 'API playground';
      case 'landing': return 'Platform architecture';
      default: return 'Studio';
    }
  };

  return (
    <header className="h-16 border-b border-[#E8E2D9] bg-[#FFFFFF]/70 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center gap-3">
        <div className="text-sm font-semibold text-[#2B2320] flex items-center gap-2">
          <span>{getCrumbTitle()}</span>
          {backendOnline && (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#2C5E43] bg-[#EAF4ED] px-2 py-0.5 rounded-full border border-[#D0E6D7]">
              <ShieldCheck className="w-3 h-3" /> Live Engine Connected
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2.5">
        <button 
          onClick={() => onNavigate('landing')} 
          className="h-9 px-3 rounded-lg border border-[#E8E2D9] bg-[#FFFFFF] hover:bg-[#F5F1E9] text-xs font-medium text-[#5A524C] transition-colors flex items-center gap-1.5"
        >
          <Compass className="w-3.5 h-3.5" />
          <span>Architecture Docs</span>
        </button>

        <button 
          onClick={() => onNavigate('api')} 
          className="h-9 w-9 rounded-lg border border-[#E8E2D9] bg-[#FFFFFF] hover:bg-[#F5F1E9] text-[#5A524C] flex items-center justify-center transition-colors"
          title="API Inspector"
        >
          <Settings className="w-4 h-4" />
        </button>

        <button
          onClick={() => onNavigate('new')}
          className="h-9 px-4 rounded-lg bg-[#2B2320] hover:bg-[#1A1513] text-[#FBF9F5] text-xs font-semibold shadow-xs flex items-center gap-1.5 transition-all"
        >
          <PlusCircle className="w-3.5 h-3.5" />
          <span>New session</span>
        </button>
      </div>
    </header>
  );
};
