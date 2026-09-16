import React from 'react';
import { ArrowRight } from 'lucide-react';
import { ScreenType } from '../types';

interface LandingPageProps {
  onNavigate: (screen: ScreenType) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onNavigate }) => {
  return (
    <div className="min-h-screen bg-[#2B2320] text-[#FBF9F5] flex flex-col items-center justify-center px-6">
      <div className="w-14 h-14 rounded-2xl bg-[#FBF9F5] text-[#2B2320] flex items-center justify-center font-bold text-2xl mb-6">
        B
      </div>
      <h1 className="font-serif text-4xl sm:text-5xl font-normal tracking-tight text-center">BhoomiAI</h1>
      <p className="mt-3 text-sm text-[#A89F97] text-center max-w-sm">
        Land record digitization and validation
      </p>
      <button
        onClick={() => onNavigate('login')}
        className="mt-10 h-11 px-6 rounded-xl bg-[#FBF9F5] text-[#2B2320] text-sm font-semibold flex items-center gap-2"
      >
        <span>Sign in</span>
        <ArrowRight className="w-4 h-4" />
      </button>
    </div>
  );
};
