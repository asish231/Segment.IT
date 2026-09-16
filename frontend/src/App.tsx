import React, { useState, useEffect } from 'react';
import { ScreenType, BenchmarkSession, ExtractedField } from './types';
import { INITIAL_SESSIONS, checkBackendHealth } from './services/api';
import { Sidebar, Topbar } from './components/Navigation';
import { LandingPage } from './screens/LandingPage';
import { LoginScreen } from './screens/LoginScreen';
import { DashboardScreen } from './screens/DashboardScreen';
import { NewSessionScreen } from './screens/NewSessionScreen';
import { InteractiveStudioScreen } from './screens/InteractiveStudioScreen';
import { ResultsScreen } from './screens/ResultsScreen';
import { ApiPlaygroundScreen } from './screens/ApiPlaygroundScreen';

export function App() {
  // Hash routing support for direct linking: #landing, #login, #dashboard, #new, #workspace, #results, #api
  const getInitialScreen = (): ScreenType => {
    const hash = window.location.hash.replace('#', '') as ScreenType;
    const validScreens: ScreenType[] = ['landing', 'login', 'dashboard', 'new', 'workspace', 'results', 'api'];
    return validScreens.includes(hash) ? hash : 'dashboard';
  };

  const [currentScreen, setCurrentScreen] = useState<ScreenType>(getInitialScreen);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(true);
  const [backendOnline, setBackendOnline] = useState<boolean>(true);
  const [sessions, setSessions] = useState<BenchmarkSession[]>(INITIAL_SESSIONS);
  const [activeSession, setActiveSession] = useState<BenchmarkSession>(INITIAL_SESSIONS[0]);

  // Sync with URL hash
  useEffect(() => {
    window.location.hash = currentScreen;
  }, [currentScreen]);

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '') as ScreenType;
      const validScreens: ScreenType[] = ['landing', 'login', 'dashboard', 'new', 'workspace', 'results', 'api'];
      if (validScreens.includes(hash)) {
        setCurrentScreen(hash);
      }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // Poll backend health
  useEffect(() => {
    const verifyHealth = async () => {
      const health = await checkBackendHealth();
      setBackendOnline(health.online);
    };
    verifyHealth();
    const interval = setInterval(verifyHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleNavigate = (screen: ScreenType) => {
    setCurrentScreen(screen);
  };

  const handleSelectSession = (session: BenchmarkSession) => {
    setActiveSession(session);
    setCurrentScreen('workspace');
  };

  const handleStartSession = (
    file: File | null, 
    sampleName: string, 
    _schema: string, 
    customResult?: any
  ) => {
    const newId = `bhm_sess_${Date.now().toString().slice(-4)}`;
    const title = file ? file.name : sampleName.replace('.png', '').replace(/_/g, ' ');
    
    let generatedFields: ExtractedField[] = [...INITIAL_SESSIONS[0].fields];

    // If real backend returned cuts, map them
    if (customResult && customResult.ocr_results && customResult.ocr_results.length > 0) {
      generatedFields = customResult.ocr_results.map((r: any, idx: number) => ({
        id: `f_${idx}`,
        name: `Extracted Line ${idx + 1}`,
        expectedValue: r.text || '',
        extractedValue: r.text || '',
        confidence: r.confidence || 0.95,
        status: 'correct',
        sourceLine: `C++ LineCut ${idx + 1}`,
        bbox: r.bbox ? { x: r.bbox[0], y: r.bbox[1], w: r.bbox[2], h: r.bbox[3] } : undefined
      }));
    }

    const newSession: BenchmarkSession = {
      id: newId,
      title: title,
      documentType: file?.name.endsWith('.pdf') ? 'PDF' : 'IMG',
      script: sampleName.includes('urdu') ? 'Urdu (Nastaliq)' : 'Hindi (Devanagari)',
      totalFields: generatedFields.length || 15,
      accuracy: 94.2,
      status: 'review',
      processingTime: '8.4s',
      correctionsCount: 0,
      date: 'Today',
      thumbnailUrl: file ? URL.createObjectURL(file) : `/samples/${sampleName}`,
      fields: generatedFields
    };

    setSessions([newSession, ...sessions]);
    setActiveSession(newSession);
  };

  const handleUpdateField = (fieldId: string, newValue: string) => {
    if (!activeSession) return;
    const updatedFields = activeSession.fields.map(f => {
      if (f.id === fieldId) {
        return {
          ...f,
          extractedValue: newValue,
          status: 'corrected' as const,
          confidence: 0.98
        };
      }
      return f;
    });

    const updatedSession = {
      ...activeSession,
      fields: updatedFields,
      correctionsCount: activeSession.correctionsCount + 1,
      accuracy: 96.7
    };

    setActiveSession(updatedSession);
    setSessions(sessions.map(s => s.id === updatedSession.id ? updatedSession : s));
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setCurrentScreen('login');
  };

  const handleLoginSuccess = (_email: string) => {
    setIsAuthenticated(true);
    setCurrentScreen('dashboard');
  };

  const handleExploreDemo = () => {
    setIsAuthenticated(true);
    setCurrentScreen('dashboard');
  };

  // If user is on the Landing Page, show full-bleed editorial experience
  if (currentScreen === 'landing') {
    return (
      <LandingPage
        onNavigate={handleNavigate}
        onExploreDemo={handleExploreDemo}
        backendOnline={backendOnline}
      />
    );
  }

  // If on Login screen (or unauthenticated without landing)
  if (currentScreen === 'login' || !isAuthenticated) {
    return (
      <LoginScreen
        onLoginSuccess={handleLoginSuccess}
        onExploreDemo={handleExploreDemo}
      />
    );
  }

  // Dashboard / App Workspace Shell with Sidebar and Topbar
  return (
    <div className="flex min-h-screen bg-[#FBF9F5] text-[#2B2320]">
      <Sidebar
        currentScreen={currentScreen}
        onNavigate={handleNavigate}
        backendOnline={backendOnline}
        onLogout={handleLogout}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <Topbar
          currentScreen={currentScreen}
          onNavigate={handleNavigate}
          backendOnline={backendOnline}
        />

        <main className="flex-1 p-6 sm:p-8 overflow-y-auto">
          {currentScreen === 'dashboard' && (
            <DashboardScreen
              sessions={sessions}
              onSelectSession={handleSelectSession}
              onNavigate={handleNavigate}
              backendOnline={backendOnline}
            />
          )}

          {currentScreen === 'new' && (
            <NewSessionScreen
              onStartSession={handleStartSession}
              onNavigate={handleNavigate}
            />
          )}

          {currentScreen === 'workspace' && (
            <InteractiveStudioScreen
              session={activeSession}
              onNavigate={handleNavigate}
              onUpdateField={handleUpdateField}
            />
          )}

          {currentScreen === 'results' && (
            <ResultsScreen
              session={activeSession}
              onNavigate={handleNavigate}
            />
          )}

          {currentScreen === 'api' && (
            <ApiPlaygroundScreen
              backendOnline={backendOnline}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
