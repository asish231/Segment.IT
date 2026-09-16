import React, { useState } from 'react';
import { ArrowRight, Loader2 } from 'lucide-react';
import { AuthUser } from '../types';
import { login, register } from '../services/api';

interface LoginScreenProps {
  onAuthenticated: (user: AuthUser) => void;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({ onAuthenticated }) => {
  const [mode, setMode] = useState<'signin' | 'register'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [district, setDistrict] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result =
        mode === 'signin'
          ? await login(email, password)
          : await register(email, password, name, '', district);
      onAuthenticated(result.user);
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex bg-[#FBF9F5] text-[#2B2320]">
      <div className="hidden lg:flex lg:w-7/12 bg-[#2B2320] text-[#FBF9F5] p-16 flex-col justify-between relative overflow-hidden">
        <div
          className="absolute inset-0 opacity-15 bg-cover bg-center mix-blend-luminosity pointer-events-none"
          style={{ backgroundImage: `url('/assets/hero_art.jpg')` }}
        />
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#FBF9F5] text-[#2B2320] flex items-center justify-center font-bold text-xl shadow-md">
              B
            </div>
            <div>
              <div className="font-serif text-2xl tracking-tight font-semibold">BhoomiAI</div>
              <div className="text-[10px] uppercase tracking-widest text-[#A89F97] font-semibold">
                Land Record Digitization
              </div>
            </div>
          </div>

          <div className="mt-28 max-w-xl">
            <h1 className="font-serif text-5xl xl:text-6xl font-normal leading-[1.08] tracking-tight text-[#FBF9F5]">
              Digitize and validate land records.
            </h1>
            <p className="mt-6 text-lg text-[#D5CDC2] font-light leading-relaxed max-w-lg">
              OCR, table extraction, and DoLR/DILRMP schema compilation for scanned Jamabandi,
              Khatauni, and Khasra records.
            </p>
          </div>
        </div>
      </div>

      <div className="w-full lg:w-5/12 flex items-center justify-center p-8 sm:p-14">
        <div className="w-full max-w-md space-y-8">
          <div>
            <h2 className="font-serif text-3xl sm:text-4xl text-[#2B2320] font-normal tracking-tight">
              {mode === 'signin' ? 'Sign in' : 'Create an account'}
            </h2>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {mode === 'register' && (
              <div>
                <label className="block text-xs font-semibold text-[#2B2320] mb-2">Full name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full h-12 px-4 rounded-xl border border-[#E8E2D9] bg-[#FFFFFF] text-sm text-[#2B2320] focus:outline-none focus:ring-2 focus:ring-[#2B2320] focus:border-transparent transition-all"
                  required
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-[#2B2320] mb-2">Email address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@agency.gov.in"
                className="w-full h-12 px-4 rounded-xl border border-[#E8E2D9] bg-[#FFFFFF] text-sm text-[#2B2320] focus:outline-none focus:ring-2 focus:ring-[#2B2320] focus:border-transparent transition-all"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#2B2320] mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                minLength={mode === 'register' ? 8 : undefined}
                className="w-full h-12 px-4 rounded-xl border border-[#E8E2D9] bg-[#FFFFFF] text-sm text-[#2B2320] focus:outline-none focus:ring-2 focus:ring-[#2B2320] focus:border-transparent transition-all"
                required
              />
            </div>

            {mode === 'register' && (
              <div>
                <label className="block text-xs font-semibold text-[#2B2320] mb-2">District</label>
                <input
                  type="text"
                  value={district}
                  onChange={(e) => setDistrict(e.target.value)}
                  placeholder="e.g. Solan"
                  className="w-full h-12 px-4 rounded-xl border border-[#E8E2D9] bg-[#FFFFFF] text-sm text-[#2B2320] focus:outline-none focus:ring-2 focus:ring-[#2B2320] focus:border-transparent transition-all"
                />
              </div>
            )}

            {error && (
              <div className="text-sm text-[#E05A47] bg-[#FEF1EC] border border-[#FADCD5] rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full h-12 rounded-xl bg-[#2B2320] hover:bg-[#181412] text-[#FBF9F5] font-semibold text-sm transition-all flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <span>{mode === 'signin' ? 'Sign in' : 'Create account'}</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="text-center text-sm text-[#756C65]">
            {mode === 'signin' ? (
              <>
                No account yet?{' '}
                <button
                  onClick={() => { setMode('register'); setError(null); }}
                  className="text-[#2B2320] font-semibold underline underline-offset-2"
                >
                  Create one
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button
                  onClick={() => { setMode('signin'); setError(null); }}
                  className="text-[#2B2320] font-semibold underline underline-offset-2"
                >
                  Sign in
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
