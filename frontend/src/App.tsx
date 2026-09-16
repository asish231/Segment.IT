import React, { useEffect, useState } from 'react';
import { ScreenType, AuthUser } from './types';
import { checkBackendHealth, clearTokens, fetchMe, getAccessToken, logout as apiLogout } from './services/api';
import { Sidebar, Topbar } from './components/Navigation';
import { LandingPage } from './screens/LandingPage';
import { LoginScreen } from './screens/LoginScreen';
import { DashboardScreen } from './screens/DashboardScreen';
import { NewSessionScreen } from './screens/NewSessionScreen';
import { InteractiveStudioScreen } from './screens/InteractiveStudioScreen';
import { VerifyScreen } from './screens/VerifyScreen';
import { ApiPlaygroundScreen } from './screens/ApiPlaygroundScreen';

const VALID_SCREENS: ScreenType[] = ['landing', 'login', 'dashboard', 'new', 'workspace', 'verify', 'api'];
const APP_SCREENS: ScreenType[] = ['dashboard', 'new', 'workspace', 'verify', 'api'];

function parseHash(): { screen: ScreenType; jobId: string | null } {
  const raw = window.location.hash.replace('#', '');
  const [screenPart, jobPart] = raw.split('/');
  const screen = VALID_SCREENS.includes(screenPart as ScreenType) ? (screenPart as ScreenType) : 'landing';
  return { screen, jobId: jobPart || null };
}

export function App() {
  const initial = parseHash();
  const [currentScreen, setCurrentScreen] = useState<ScreenType>(initial.screen);
  const [activeJobId, setActiveJobId] = useState<string | null>(initial.jobId);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [backendOnline, setBackendOnline] = useState(true);

  const navigate = (screen: ScreenType, jobId?: string) => {
    const hash = jobId ? `${screen}/${jobId}` : screen;
    window.location.hash = hash;
  };

  // Sync from hash (back/forward, and initial deep link)
  useEffect(() => {
    const onHashChange = () => {
      const { screen, jobId } = parseHash();
      setCurrentScreen(screen);
      if (jobId) setActiveJobId(jobId);
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  // Validate any stored session on load
  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      setAuthChecked(true);
      return;
    }
    fetchMe()
      .then((u) => setUser(u))
      .catch(() => {
        clearTokens();
        setUser(null);
        if (APP_SCREENS.includes(currentScreen)) navigate('login');
      })
      .finally(() => setAuthChecked(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll backend health
  useEffect(() => {
    const verify = () => checkBackendHealth().then((h) => setBackendOnline(h.online));
    verify();
    const interval = setInterval(verify, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleAuthenticated = (authedUser: AuthUser) => {
    setUser(authedUser);
    navigate('dashboard');
  };

  const handleLogout = () => {
    apiLogout();
    setUser(null);
    navigate('login');
  };

  const handleOpenJob = (jobId: string) => {
    setActiveJobId(jobId);
    navigate('workspace', jobId);
  };

  if (!authChecked) {
    return <div className="min-h-screen bg-[#FBF9F5]" />;
  }

  if (currentScreen === 'landing' && !user) {
    return <LandingPage onNavigate={(s) => navigate(s)} />;
  }

  if (!user) {
    return <LoginScreen onAuthenticated={handleAuthenticated} />;
  }

  return (
    <div className="flex min-h-screen bg-[#FBF9F5] text-[#2B2320]">
      <Sidebar
        currentScreen={currentScreen}
        onNavigate={(s) => navigate(s, s === 'workspace' || s === 'verify' ? activeJobId || undefined : undefined)}
        backendOnline={backendOnline}
        user={user}
        onLogout={handleLogout}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <Topbar currentScreen={currentScreen} onNavigate={(s) => navigate(s)} backendOnline={backendOnline} />

        <main className="flex-1 p-6 sm:p-8 overflow-y-auto">
          {currentScreen === 'dashboard' && (
            <DashboardScreen onOpenJob={handleOpenJob} onNavigate={(s) => navigate(s)} />
          )}

          {currentScreen === 'new' && (
            <NewSessionScreen onDocumentReady={handleOpenJob} onNavigate={(s) => navigate(s)} />
          )}

          {currentScreen === 'workspace' && (
            <InteractiveStudioScreen jobId={activeJobId} onNavigate={(s) => navigate(s, activeJobId || undefined)} />
          )}

          {currentScreen === 'verify' && (
            <VerifyScreen jobId={activeJobId} user={user} onNavigate={(s) => navigate(s, activeJobId || undefined)} />
          )}

          {currentScreen === 'api' && <ApiPlaygroundScreen />}
        </main>
      </div>
    </div>
  );
}

export default App;
