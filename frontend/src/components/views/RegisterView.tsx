import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';

interface RegisterViewProps {
  onNavigate: (view: 'home' | 'discover' | 'assistant' | 'orders' | 'login' | 'register') => void;
  notice?: string | null;
  onSuccessRedirect?: () => void;
}

export default function RegisterView({ onNavigate, notice, onSuccessRedirect }: RegisterViewProps) {
  const { register } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || !password || !confirmPassword) {
      setError('Please fill in all fields');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters long');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);
      await register({ name, email, password });
      if (onSuccessRedirect) {
        onSuccessRedirect();
      } else {
        onNavigate('assistant');
      }
    } catch (err: any) {
      setError(err?.message || 'Registration failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-arctic-soft flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border border-slopes/40 p-8 my-8">
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-midnight border border-mountainside rounded-xl flex items-center justify-center mx-auto mb-4 shadow-sm">
            <span className="text-white font-bold text-xl">N</span>
          </div>
          <h2 className="text-2xl font-bold text-midnight tracking-tight">Create your Account</h2>
          <p className="text-sm text-apres mt-1">Start your AI-native commerce experience</p>
        </div>

        {notice && (
          <div className="mb-6 p-4 bg-arctic-soft border border-slopes/40 rounded-xl text-xs text-mountainside font-medium flex items-start gap-3">
            <span className="text-base">🔒</span>
            <div className="leading-relaxed">{notice}</div>
          </div>
        )}

        {error && (
          <div className="mb-6 p-4 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-midnight uppercase tracking-wider mb-1.5">
              Full Name
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Alice Wonderland"
              className="w-full px-4 py-2.5 bg-arctic-soft/40 border border-slopes/40 rounded-xl text-sm text-midnight placeholder:text-apres/60 focus:outline-none focus:ring-2 focus:ring-midnight focus:border-transparent transition-all"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-midnight uppercase tracking-wider mb-1.5">
              Email address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full px-4 py-2.5 bg-arctic-soft/40 border border-slopes/40 rounded-xl text-sm text-midnight placeholder:text-apres/60 focus:outline-none focus:ring-2 focus:ring-midnight focus:border-transparent transition-all"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-midnight uppercase tracking-wider mb-1.5">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 6 characters"
              className="w-full px-4 py-2.5 bg-arctic-soft/40 border border-slopes/40 rounded-xl text-sm text-midnight placeholder:text-apres/60 focus:outline-none focus:ring-2 focus:ring-midnight focus:border-transparent transition-all"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-midnight uppercase tracking-wider mb-1.5">
              Confirm Password
            </label>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Repeat your password"
              className="w-full px-4 py-2.5 bg-arctic-soft/40 border border-slopes/40 rounded-xl text-sm text-midnight placeholder:text-apres/60 focus:outline-none focus:ring-2 focus:ring-midnight focus:border-transparent transition-all"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-sm shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed mt-2 hover:scale-[1.01]"
          >
            {isSubmitting ? 'Creating account...' : 'Create Account'}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-slopes/20 text-center text-xs text-apres">
          Already have an account?{' '}
          <button
            onClick={() => onNavigate('login')}
            className="text-midnight font-bold hover:underline"
          >
            Sign in
          </button>
        </div>
      </div>
    </div>
  );
}
