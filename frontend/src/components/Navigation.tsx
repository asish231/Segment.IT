import React from 'react';
import {
  LayoutDashboard,
  PlusCircle,
  Sparkles,
  CheckCircle2,
  Terminal,
  LogOut,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { AuthUser, ScreenType } from '../types';

interface NavigationProps {
  currentScreen: ScreenType;
  onNavigate: (screen: ScreenType) => void;
  backendOnline: boolean;
  user: AuthUser | null;
  onLogout: () => void;
}

const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('') || '?';

export const Sidebar: React.FC<NavigationProps> = ({ currentScreen, onNavigate, backendOnline, user, onLogout }) => {
  return (
    <aside className="w-64 bg-[#FFFFFF]/80 backdrop-blur-md border-r border-[#E8E2D9] p-5 flex flex-col justify-between shrink-0 h-screen sticky top-0">
      <div>
        <div onClick={() => onNavigate('dashboard')} className="flex items-center gap-3 px-2 py-2 mb-6 cursor-pointer group">
          <div className="w-9 h-9 rounded-xl bg-[#2B2320] text-[#FBF9F5] flex items-center justify-center font-bold text-lg group-hover:bg-[#E05A47] transition-colors">
            B
          </div>
          <div className="font-serif text-xl tracking-tight font-semibold text-[#2B2320]">BhoomiAI</div>
        </div>

        <div className="space-y-6">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-[#A89F97] px-3 mb-2">Workspace</div>
            <nav className="space-y-1">
              <NavButton icon={<LayoutDashboard className="w-4 h-4" />} label="Overview" active={currentScreen === 'dashboard'} onClick={() => onNavigate('dashboard')} />
              <NavButton icon={<PlusCircle className="w-4 h-4" />} label="New document" active={currentScreen === 'new'} onClick={() => onNavigate('new')} />
              <NavButton icon={<Sparkles className="w-4 h-4" />} label="Studio" active={currentScreen === 'workspace'} onClick={() => onNavigate('workspace')} />
              <NavButton icon={<CheckCircle2 className="w-4 h-4" />} label="Verify" active={currentScreen === 'verify'} onClick={() => onNavigate('verify')} />
            </nav>
          </div>

          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-[#A89F97] px-3 mb-2">Developers</div>
            <nav className="space-y-1">
              <NavButton icon={<Terminal className="w-4 h-4" />} label="API" active={currentScreen === 'api'} onClick={() => onNavigate('api')} />
            </nav>
          </div>
        </div>
      </div>

      <div className="space-y-4 pt-4 border-t border-[#E8E2D9]">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#F8F5EE] border border-[#E4DCD3] text-xs font-semibold text-[#2B2320]">
          {backendOnline ? <Wifi className="w-3.5 h-3.5 text-[#5A524C]" /> : <WifiOff className="w-3.5 h-3.5 text-[#E05A47]" />}
          <span>{backendOnline ? 'Backend connected' : 'Backend unreachable'}</span>
        </div>

        {user && (
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 shrink-0 rounded-full bg-[#2B2320] text-white flex items-center justify-center text-xs font-bold">
                {initials(user.name || user.email)}
              </div>
              <div className="min-w-0">
                <div className="text-xs font-bold text-[#2B2320] truncate">{user.name || user.email}</div>
                <div className="text-[10px] text-[#756C65] capitalize">{user.role}</div>
              </div>
            </div>
            <button onClick={onLogout} title="Sign out" className="text-[#A89F97] hover:text-[#E05A47] transition-colors p-1 shrink-0">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
};

const NavButton: React.FC<{ icon: React.ReactNode; label: string; active: boolean; onClick: () => void }> = ({
  icon,
  label,
  active,
  onClick,
}) => (
  <button
    onClick={onClick}
    className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
      active ? 'bg-[#2B2320] text-[#FBF9F5]' : 'text-[#5A524C] hover:bg-[#F5F1E9] hover:text-[#2B2320]'
    }`}
  >
    <span className="opacity-80">{icon}</span>
    <span>{label}</span>
  </button>
);

const TITLES: Record<ScreenType, string> = {
  landing: 'BhoomiAI',
  login: 'Sign in',
  dashboard: 'Overview',
  new: 'New document',
  workspace: 'Studio',
  verify: 'Verify',
  api: 'API',
};

export const Topbar: React.FC<{
  currentScreen: ScreenType;
  onNavigate: (screen: ScreenType) => void;
  backendOnline: boolean;
}> = ({ currentScreen, onNavigate }) => {
  return (
    <header className="h-16 border-b border-[#E8E2D9] bg-[#FFFFFF]/70 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-20">
      <div className="text-sm font-semibold text-[#2B2320]">{TITLES[currentScreen]}</div>

      <button
        onClick={() => onNavigate('new')}
        className="h-9 px-4 rounded-lg bg-[#2B2320] hover:bg-[#1A1513] text-[#FBF9F5] text-xs font-semibold flex items-center gap-1.5 transition-all"
      >
        <PlusCircle className="w-3.5 h-3.5" />
        <span>New document</span>
      </button>
    </header>
  );
};
