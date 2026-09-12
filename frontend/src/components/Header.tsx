import React, { useState, useRef, useEffect } from 'react';
import { Cart, CommerceContract } from '@/lib/types';
import CartButton from './CartButton';
import { useAuth } from '@/context/AuthContext';

interface HeaderProps {
  cart: Cart | null;
  currentView: 'home' | 'discover' | 'assistant' | 'orders' | 'buyer' | 'cart' | 'login' | 'register';
  onNavigate: (view: 'home' | 'discover' | 'assistant' | 'orders' | 'buyer' | 'cart' | 'login' | 'register') => void;
  onCartClick: () => void;
  onContractClick: () => void;
  onReplayClick?: () => void;
  onLabClick?: () => void;
  onResetDemo?: () => void;
  contract?: CommerceContract | null;
}

export default function Header({
  cart,
  currentView,
  onNavigate,
  onCartClick,
  onContractClick,
  onReplayClick,
  onLabClick,
  onResetDemo,
  contract,
}: HeaderProps) {
  const { user, isAuthenticated, logout } = useAuth();
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Tier 1: Primary navigation tabs
  const primaryNavItems: { id: 'buyer' | 'assistant' | 'orders'; label: string; icon: string }[] = [
    { id: 'buyer', label: 'Buyer Agent', icon: '🤖' },
    { id: 'assistant', label: 'AI Assistant', icon: '✨' },
    { id: 'orders', label: 'Orders', icon: '📦' },
  ];

  const loggedOutNavItems: { id: 'home' | 'discover'; label: string; icon: string }[] = [
    { id: 'home', label: 'Home', icon: '🏠' },
    { id: 'discover', label: 'Discover', icon: '🔍' },
  ];

  const navItems = isAuthenticated ? primaryNavItems : loggedOutNavItems;

  const handleLogout = async () => {
    setIsUserMenuOpen(false);
    await logout();
    onNavigate('home');
  };

  const isContractActive = contract?.status === 'ACTIVE';
  const contractBudget = contract?.max_budget;

  return (
    <header className="bg-midnight border-b border-mountainside/80 px-6 py-3.5 sticky top-0 z-30 shadow-md">
      <div className="flex items-center justify-between max-w-7xl mx-auto">
        {/* Logo */}
        <div
          className="flex items-center gap-3 cursor-pointer group"
          onClick={() => onNavigate(isAuthenticated ? 'buyer' : 'home')}
        >
          <div className="w-10 h-10 bg-mountainside border border-slopes/30 rounded-xl flex items-center justify-center shadow-sm group-hover:border-slopes/60 transition-all">
            <span className="text-white font-bold text-xl tracking-tight">N</span>
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-1.5">
              NexaCart
              <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-accent/20 text-indigo-300 border border-accent/30 hidden sm:inline-block">
                AI Commerce
              </span>
            </h1>
          </div>
        </div>

        {/* Center Navigation */}
        <nav className="flex items-center gap-1 mx-4 sm:mx-6 bg-mountainside/60 p-1 rounded-xl border border-mountainside">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`px-3.5 sm:px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                currentView === item.id
                  ? 'bg-midnight text-white shadow-sm border border-slopes/30'
                  : 'text-slopes hover:text-white hover:bg-mountainside/80'
              }`}
            >
              <span className="hidden sm:inline">{item.icon}</span>
              <span className="sm:ml-1.5">{item.label}</span>
            </button>
          ))}
        </nav>

        {/* Right Actions */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          {isAuthenticated ? (
            <>
              {/* Contract Status Chip */}
              <button
                onClick={onContractClick}
                className={`hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all border ${
                  isContractActive
                    ? 'bg-emerald-50/80 border-emerald-200 text-emerald-700 hover:bg-emerald-100 hover:border-emerald-300'
                    : 'bg-arctic-soft/60 border-slopes/30 text-apres hover:bg-arctic-soft hover:border-slopes/50'
                }`}
                title="AI Commerce Contract"
              >
                <span className="text-sm">🛡️</span>
                <span className="hidden lg:inline">
                  {isContractActive
                    ? `Contract: Active${contractBudget != null ? ` · ₹${contractBudget.toLocaleString('en-IN')}` : ''}`
                    : 'No Active Contract'}
                </span>
              </button>

              {/* Cart Button */}
              <CartButton cart={cart} onClick={onCartClick} />

              {/* User Menu Dropdown */}
              <div className="relative" ref={menuRef}>
                <button
                  onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                  className="flex items-center gap-2 pl-2 pr-2.5 sm:pr-3 py-1.5 rounded-full bg-mountainside/80 border border-slopes/30 hover:border-slopes/60 hover:bg-mountainside text-white transition-all"
                  aria-label="User profile menu"
                >
                  <div className="w-7 h-7 rounded-full bg-accent text-white font-bold text-xs flex items-center justify-center">
                    {user?.name ? user.name.charAt(0).toUpperCase() : 'U'}
                  </div>
                  <span className="text-xs font-semibold text-arctic-light max-w-[90px] sm:max-w-[120px] truncate hidden sm:inline">
                    {user?.name || 'Account'}
                  </span>
                  <span className="text-slopes text-[10px]">▼</span>
                </button>

                {isUserMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 bg-midnight border border-mountainside rounded-xl shadow-2xl py-2 z-50 animate-in fade-in slide-in-from-top-2 text-arctic">
                    <div className="px-4 py-2.5 border-b border-mountainside">
                      <p className="text-[10px] text-apres uppercase tracking-wider font-semibold">Signed in as</p>
                      <p className="text-sm font-bold text-white truncate mt-0.5">{user?.name}</p>
                      <p className="text-xs text-slopes truncate font-mono">{user?.email}</p>
                    </div>

                    <div className="py-1">
                      <button
                        onClick={() => {
                          setIsUserMenuOpen(false);
                          onNavigate('buyer');
                        }}
                        className="w-full text-left px-4 py-2 text-sm text-arctic hover:text-white hover:bg-mountainside/70 flex items-center gap-2.5 transition-colors"
                      >
                        <span>🤖</span>
                        <span>Buyer Agent</span>
                      </button>

                      <button
                        onClick={() => {
                          setIsUserMenuOpen(false);
                          onNavigate('assistant');
                        }}
                        className="w-full text-left px-4 py-2 text-sm text-arctic hover:text-white hover:bg-mountainside/70 flex items-center gap-2.5 transition-colors"
                      >
                        <span>✨</span>
                        <span>AI Assistant</span>
                      </button>

                      <button
                        onClick={() => {
                          setIsUserMenuOpen(false);
                          onNavigate('orders');
                        }}
                        className="w-full text-left px-4 py-2 text-sm text-arctic hover:text-white hover:bg-mountainside/70 flex items-center gap-2.5 transition-colors"
                      >
                        <span>📦</span>
                        <span>My Orders</span>
                      </button>
                    </div>

                    <div className="border-t border-mountainside pt-1 mt-1">
                      {onResetDemo && (
                        <button
                          onClick={() => {
                            setIsUserMenuOpen(false);
                            if (window.confirm('Reset demo session? This will clear your cart, contract, and buyer agent workspace. Orders history will be preserved.')) {
                              onResetDemo();
                            }
                          }}
                          className="w-full text-left px-4 py-2 text-sm text-amber-400 hover:bg-mountainside/70 font-medium flex items-center gap-2.5 transition-colors"
                        >
                          <span>🔄</span>
                          <span>Reset Demo Session</span>
                        </button>
                      )}
                      <button
                        onClick={handleLogout}
                        className="w-full text-left px-4 py-2 text-sm text-rose-400 hover:bg-mountainside/70 font-medium flex items-center gap-2.5 transition-colors"
                      >
                        <span>🚪</span>
                        <span>Sign Out</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center gap-2.5">
              <button
                onClick={() => onNavigate('login')}
                className="px-4 py-2 text-sm font-medium text-arctic hover:text-white hover:bg-mountainside/60 rounded-xl transition-all"
              >
                Log In
              </button>
              <button
                onClick={() => onNavigate('register')}
                className="px-4 py-2 text-sm font-semibold text-midnight bg-arctic-soft hover:bg-white rounded-xl shadow-sm transition-all hover:shadow hover:scale-[1.02]"
              >
                Get Started
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
