import React from 'react';

interface HomeViewProps {
  onNavigate: (view: 'home' | 'discover' | 'assistant' | 'orders' | 'buyer' | 'login' | 'register') => void;
}

export default function HomeView({ onNavigate }: HomeViewProps) {
  return (
    <div className="flex-1 overflow-y-auto bg-arctic-soft pb-20">
      {/* Hero Section */}
      <section className="bg-midnight text-white py-24 px-6 border-b border-mountainside relative overflow-hidden">
        {/* Subtle decorative background gradient */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-mountainside/40 via-midnight to-midnight pointer-events-none" />
        
        <div className="max-w-5xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-mountainside/70 border border-slopes/30 text-xs font-semibold text-slopes mb-8 shadow-sm">
            <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
            <span>Autonomous AI Commerce Platform</span>
          </div>

          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight mb-8 leading-[1.1]">
            Built for AI Buyers. <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-arctic via-white to-slopes">
              Safe by Design.
            </span>
          </h1>

          <p className="text-lg sm:text-xl text-slopes max-w-3xl mx-auto mb-12 leading-relaxed font-normal">
            NexaCart lets autonomous agents search, decide, and purchase on a merchant's catalog — bounded by enforceable contracts, gated by human approval, and fully auditable. Humans can shop too.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={() => onNavigate('buyer')}
              className="px-8 py-4 bg-white text-midnight hover:bg-arctic font-bold text-base rounded-xl transition-all shadow-lg hover:shadow-xl hover:scale-[1.02] w-full sm:w-auto"
            >
              Try the Buyer Agent
            </button>
            <button
              onClick={() => onNavigate('assistant')}
              className="px-8 py-4 bg-mountainside/50 border border-slopes/40 text-arctic hover:text-white hover:bg-mountainside hover:border-slopes/70 font-semibold text-base rounded-xl transition-all w-full sm:w-auto"
            >
              Try Human Chat
            </button>
          </div>
        </div>
      </section>

      {/* How it Works */}
      <section className="py-20 px-6 bg-white border-b border-slopes/20">
        <div className="max-w-5xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-3xl font-extrabold text-midnight tracking-tight mb-3">How NexaCart Works</h2>
            <p className="text-apres text-sm">From requirement to verified delivery in a few intuitive steps.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 text-center relative">
            <div className="flex flex-col items-center p-6 rounded-2xl bg-arctic-soft/50 border border-slopes/20">
              <div className="w-12 h-12 bg-midnight text-white rounded-xl flex items-center justify-center text-lg font-bold mb-4 shadow-sm">1</div>
              <h3 className="text-base font-bold text-midnight mb-2">Tell us what you need</h3>
              <p className="text-apres text-xs leading-relaxed">Type your constraints or natural desires just like speaking to an expert assistant.</p>
            </div>

            <div className="flex flex-col items-center p-6 rounded-2xl bg-arctic-soft/50 border border-slopes/20">
              <div className="w-12 h-12 bg-mountainside text-white rounded-xl flex items-center justify-center text-lg font-bold mb-4 shadow-sm">2</div>
              <h3 className="text-base font-bold text-midnight mb-2">AI understands you</h3>
              <p className="text-apres text-xs leading-relaxed">Our engine extracts budget, technical specs, categories, and personal preferences.</p>
            </div>

            <div className="flex flex-col items-center p-6 rounded-2xl bg-arctic-soft/50 border border-slopes/20">
              <div className="w-12 h-12 bg-midnight text-white rounded-xl flex items-center justify-center text-lg font-bold mb-4 shadow-sm">3</div>
              <h3 className="text-base font-bold text-midnight mb-2">Find & Compare</h3>
              <p className="text-apres text-xs leading-relaxed">Evaluates real catalog products dynamically with generic constraint scoring.</p>
            </div>

            <div className="flex flex-col items-center p-6 rounded-2xl bg-arctic-soft/50 border border-slopes/20">
              <div className="w-12 h-12 bg-mountainside text-white rounded-xl flex items-center justify-center text-lg font-bold mb-4 shadow-sm">4</div>
              <h3 className="text-base font-bold text-midnight mb-2">Secure Payment</h3>
              <p className="text-apres text-xs leading-relaxed">Deterministic verification checks inventory and enforces contracts before checkout.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Differentiators */}
      <section className="py-20 px-6 bg-arctic-soft">
        <div className="max-w-5xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="text-3xl font-extrabold text-midnight tracking-tight mb-3">The AI-Native Difference</h2>
            <p className="text-apres text-sm">Engineered with guardrails, transparency, and safety at its core.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slopes/30 hover:border-mountainside/50 hover:shadow-md transition-all">
              <div className="text-3xl mb-4">🤖</div>
              <h3 className="text-lg font-bold text-midnight mb-2">Autonomous Buyer Agent</h3>
              <p className="text-apres text-sm leading-relaxed">Machine-to-machine purchasing, bounded by the same contract and approval gate as human checkout. Let AI buy for you — safely.</p>
            </div>

            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slopes/30 hover:border-mountainside/50 hover:shadow-md transition-all">
              <div className="text-3xl mb-4">💬</div>
              <h3 className="text-lg font-bold text-midnight mb-2">Conversational Shopping</h3>
              <p className="text-apres text-sm leading-relaxed">Skip the endless scrolling and manual filtering. Have a natural conversation to find exactly what you need in seconds.</p>
            </div>

            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slopes/30 hover:border-mountainside/50 hover:shadow-md transition-all">
              <div className="text-3xl mb-4">🛡️</div>
              <h3 className="text-lg font-bold text-midnight mb-2">AI Commerce Contract</h3>
              <p className="text-apres text-sm leading-relaxed">Set hard, deterministic boundaries for the AI. Limit spending, enforce specific categories, and maintain total control.</p>
            </div>

            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slopes/30 hover:border-mountainside/50 hover:shadow-md transition-all">
              <div className="text-3xl mb-4">🧪</div>
              <h3 className="text-lg font-bold text-midnight mb-2">AI Decision Lab</h3>
              <p className="text-apres text-sm leading-relaxed">Challenge any recommendation, simulate what-if scenarios, and see exactly why a product was or wasn't chosen.</p>
            </div>

            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slopes/30 hover:border-mountainside/50 hover:shadow-md transition-all">
              <div className="text-3xl mb-4">✅</div>
              <h3 className="text-lg font-bold text-midnight mb-2">Verified Checkout</h3>
              <p className="text-apres text-sm leading-relaxed">Before any payment, our system double-checks inventory and pricing to ensure what you see is what you get.</p>
            </div>

            <div className="bg-white p-8 rounded-2xl shadow-sm border border-slopes/30 hover:border-mountainside/50 hover:shadow-md transition-all">
              <div className="text-3xl mb-4">🎬</div>
              <h3 className="text-lg font-bold text-midnight mb-2">Purchase Replay</h3>
              <p className="text-apres text-sm leading-relaxed">Review the exact conversational journey that led to a purchase. Full auditability and transparency into decision making.</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
