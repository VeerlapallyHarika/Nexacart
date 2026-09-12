'use client';

import React, { useState, useEffect, useRef } from 'react';
import { BuyerAgentAction, BuyerAgentRunResult, PurchaseReplayData, ReplayStep } from '@/lib/types';
import { runBuyerAgent, fetchPurchaseReplay } from '@/lib/api';

interface BuyerAgentViewProps {
  sessionId?: string;
  onNavigateToCart: () => void;
  onOpenReplay: () => void;
  onOpenTrace: () => void;
  onOpenLab?: () => void;
  onDecisionCreated?: (decisionId: string) => void;
  onResetDemo?: () => void;
}

const EXAMPLE_CHIPS = [
  {
    goal: 'Buy headphones under ₹5,000 with 30+ hour battery',
    icon: '🎧',
    bgColor: 'bg-violet-50/80 hover:bg-violet-100/90',
    borderColor: 'border-violet-200/90',
    borderLeftColor: 'border-l-violet-500',
    textColor: 'text-violet-950',
    iconBg: 'bg-violet-200/60 text-violet-700',
  },
  {
    goal: 'Buy a laptop under ₹40,000',
    icon: '💻',
    bgColor: 'bg-sky-50/80 hover:bg-sky-100/90',
    borderColor: 'border-sky-200/90',
    borderLeftColor: 'border-l-sky-500',
    textColor: 'text-sky-950',
    iconBg: 'bg-sky-200/60 text-sky-700',
  },
  {
    goal: 'Buy the Sony WH-1000XM4 headphones',
    icon: '🎵',
    bgColor: 'bg-indigo-50/80 hover:bg-indigo-100/90',
    borderColor: 'border-indigo-200/90',
    borderLeftColor: 'border-l-indigo-500',
    textColor: 'text-indigo-950',
    iconBg: 'bg-indigo-200/60 text-indigo-700',
  },
];

const ACTION_COLORS: Record<string, string> = {
  search_products: 'text-sky-300 border-sky-500/30 bg-sky-500/10',
  get_product_details: 'text-violet-300 border-violet-500/30 bg-violet-500/10',
  compare_products: 'text-amber-300 border-amber-500/30 bg-amber-500/10',
  add_to_cart: 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10',
  view_cart: 'text-teal-300 border-teal-500/30 bg-teal-500/10',
  verify_cart: 'text-indigo-300 border-indigo-500/30 bg-indigo-500/10',
};

function isStepBlocked(action: BuyerAgentAction): boolean {
  if (!action.output || typeof action.output !== 'object') return false;
  return (
    Boolean(action.output.blocked) ||
    action.output.reason === 'contract_violation' ||
    Boolean(action.output.violations && action.output.violations.length > 0) ||
    action.output.status === 'blocked'
  );
}

function renderHighlightedJson(obj: any): React.ReactNode {
  const jsonString = JSON.stringify(obj, null, 2);
  const tokenRegex = /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?|[{}[\],])/g;
  
  const elements: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenRegex.exec(jsonString)) !== null) {
    if (match.index > lastIndex) {
      elements.push(jsonString.substring(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('"')) {
      if (token.endsWith(':')) {
        const keyName = token.slice(0, -1);
        elements.push(
          <React.Fragment key={match.index}>
            <span className="text-purple-300 font-semibold">{keyName}</span>
            <span className="text-slate-500">:</span>
          </React.Fragment>
        );
      } else {
        elements.push(
          <span key={match.index} className="text-emerald-300">{token}</span>
        );
      }
    } else if (/^(true|false|null)$/.test(token)) {
      elements.push(
        <span key={match.index} className="text-violet-300 font-medium">{token}</span>
      );
    } else if (/^-?\d+/.test(token)) {
      elements.push(
        <span key={match.index} className="text-amber-300 font-mono">{token}</span>
      );
    } else {
      elements.push(
        <span key={match.index} className="text-slate-400">{token}</span>
      );
    }
    lastIndex = tokenRegex.lastIndex;
  }
  if (lastIndex < jsonString.length) {
    elements.push(jsonString.substring(lastIndex));
  }

  return elements;
}

interface AgentContext {
  goal: string;
  category: string | null;
  maxBudget: number | null;
  contractNote: string | null;
  recommendedName: string | null;
  recommendedPrice: number | null;
  recommendedWithinContract: boolean | null;
  journeyTypes: string[];
  blocked: boolean;
  searchQuery?: string | null;
}

function deriveAgentContext(
  journey: PurchaseReplayData | null,
  result: BuyerAgentRunResult | null,
  fallbackGoal: string
): AgentContext | null {
  if (!result && (!journey || journey.steps.length === 0)) return null;

  const goal = result?.goal || fallbackGoal;
  let category: string | null = null;
  let maxBudget: number | null = null;
  let recommendedName: string | null = null;
  let recommendedPrice: number | null = null;
  let recommendedWithinContract: boolean | null = null;
  let contractNote: string | null = null;
  let searchQuery: string | null = null;
  let blocked = result?.final_state === 'blocked_by_contract';

  // Inspect result.actions for rich context
  if (result?.actions) {
    for (const act of result.actions) {
      if (act.action === 'search_products' && act.input) {
        if (act.input.category) category = String(act.input.category);
        if (act.input.max_price != null) maxBudget = Number(act.input.max_price);
        if (act.input.query) searchQuery = String(act.input.query);
      }
      if ((act.action === 'get_product_details' || act.action === 'compare_products') && act.output) {
        if (act.output.name && !recommendedName) recommendedName = String(act.output.name);
        if (act.output.price != null && !recommendedPrice) recommendedPrice = Number(act.output.price);
      }
      if (act.action === 'add_to_cart' && act.output) {
        if (act.output.blocked) {
          blocked = true;
          recommendedWithinContract = false;
          contractNote = act.output.message || 'Exceeds active contract limits';
        } else if (act.output.success) {
          recommendedWithinContract = true;
          contractNote = 'Fully compliant with active AI Commerce Contract';
        }
      }
    }
  }

  // Inspect journey steps if available
  if (journey && journey.steps.length > 0) {
    const steps: ReplayStep[] = journey.steps;
    for (const step of steps) {
      if (step.type === 'AGENT_GOAL' && step.description) {
        const catMatch = /category:\s*([a-z0-9 ]+)/i.exec(step.description);
        if (catMatch && !category) category = catMatch[1];
        const budMatch = /budget of up to ₹([\d,]+)/i.exec(step.description);
        if (budMatch && !maxBudget) maxBudget = Number(budMatch[1].replace(/,/g, ''));
      }
      if (step.type === 'AGENT_RECOMMENDATION' && step.description) {
        const nameMatch = /recommended \*\*([^*]+)\*\*/i.exec(step.description);
        if (nameMatch) recommendedName = nameMatch[1];
        const priceMatch = /at ₹([\d,]+)/i.exec(step.description);
        if (priceMatch) recommendedPrice = Number(priceMatch[1].replace(/,/g, ''));
        if (recommendedWithinContract === null) {
          recommendedWithinContract = !/exceeds/i.test(step.description);
        }
        const noteMatch = /Contract:\s*(.+)$/i.exec(step.description);
        if (noteMatch && !contractNote) contractNote = noteMatch[1];
      }
      if (step.type === 'CONTRACT_VIOLATION') {
        blocked = true;
      }
    }
  }

  const journeyTypes = journey?.steps.map((s) => s.type) || result?.actions.map((a) => a.action) || [];

  return {
    goal,
    category,
    maxBudget,
    contractNote,
    recommendedName,
    recommendedPrice,
    recommendedWithinContract,
    journeyTypes,
    blocked,
    searchQuery,
  };
}

interface TimelineStage {
  id: string;
  label: string;
  icon: string;
  description: string;
}

const TIMELINE_STAGES: TimelineStage[] = [
  { id: 'request', label: 'Request', icon: '🧠', description: 'Parsed Intent' },
  { id: 'analyze', label: 'Analyze', icon: '🔍', description: 'Search & Compare' },
  { id: 'recommend', label: 'Recommend', icon: '⭐', description: 'AI Selection' },
  { id: 'approval', label: 'Human Approval', icon: '🔒', description: 'Awaiting Gate' },
  { id: 'verified', label: 'Verified', icon: '🛡️', description: 'Contract Checked' },
  { id: 'cart', label: 'Cart', icon: '🛒', description: 'Cart Updated' },
  { id: 'payment', label: 'Payment', icon: '💳', description: 'Ready to Checkout' },
];

export default function BuyerAgentView({
  sessionId,
  onNavigateToCart,
  onOpenReplay,
  onOpenTrace,
  onOpenLab,
  onDecisionCreated,
}: BuyerAgentViewProps) {
  const [goal, setGoal] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BuyerAgentRunResult | null>(null);
  const [visibleSteps, setVisibleSteps] = useState(0);
  const [cartPrompted, setCartPrompted] = useState(false);
  const [journey, setJourney] = useState<PurchaseReplayData | null>(null);
  const [showProtocolStream, setShowProtocolStream] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Stream the structured log one action at a time for a "live protocol" feel.
  useEffect(() => {
    if (!result) return;
    if (visibleSteps >= result.actions.length) {
      if (result.final_state === 'ready_for_approval' && !cartPrompted) {
        setCartPrompted(true);
        onNavigateToCart();
      }
      return;
    }
    const timer = setTimeout(() => {
      setVisibleSteps((n) => n + 1);
    }, 350);
    return () => clearTimeout(timer);
  }, [result, visibleSteps, cartPrompted, onNavigateToCart]);

  useEffect(() => {
    if (showProtocolStream) {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [visibleSteps, showProtocolStream]);

  // Phase 1: Run Agent (Evaluates & Recommends ONLY - NO Cart Addition)
  const handleRun = async (overrideGoal?: string) => {
    const targetGoal = (overrideGoal ?? goal).trim();
    if (!targetGoal) return;
    if (!sessionId) {
      setError('No active session. Please log in or refresh to start a session.');
      return;
    }
    setGoal(overrideGoal ?? goal);
    setIsRunning(true);
    setError(null);
    setResult(null);
    setVisibleSteps(0);
    setCartPrompted(false);
    setJourney(null);
    try {
      const data = await runBuyerAgent(targetGoal, sessionId, undefined, false);
      setResult(data);
      if (data.decision_id && onDecisionCreated) {
        onDecisionCreated(data.decision_id);
      }
      try {
        const replay = await fetchPurchaseReplay(sessionId);
        setJourney(replay);
      } catch {
        setJourney(null);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to run the buyer agent.');
    } finally {
      setIsRunning(false);
    }
  };

  // Phase 2: Approve Purchase (Verifies Contract & Performs Cart Addition)
  const handleApprovePurchase = async () => {
    if (!result || !sessionId) return;
    const targetProductId = result.recommended_product_id || result.added_product_id;
    setIsApproving(true);
    setError(null);
    try {
      const data = await runBuyerAgent(
        result.goal,
        sessionId,
        targetProductId || undefined,
        true,
        result.run_id
      );
      setResult(data);
      if (data.decision_id && onDecisionCreated) {
        onDecisionCreated(data.decision_id);
      }
      try {
        const replay = await fetchPurchaseReplay(sessionId);
        setJourney(replay);
      } catch {
        setJourney(null);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to approve purchase.');
    } finally {
      setIsApproving(false);
    }
  };

  const isRecReady = result?.final_state === 'recommendation_ready';
  const isBlocked = result?.final_state === 'blocked_by_contract';
  const isReady = result?.final_state === 'ready_for_approval';
  const isMaxSteps = result?.final_state === 'max_steps_reached';
  const isNoMatch = result?.final_state === 'no_matching_products';
  const isError = result?.final_state === 'error';

  const context = deriveAgentContext(journey, result, result?.goal ?? goal);
  const hasRecommendation = Boolean(context?.recommendedName);

  // Helper to determine stage status for connected decision timeline
  const getStageStatus = (stageId: string): 'completed' | 'current' | 'blocked' | 'upcoming' => {
    if (!result) return 'upcoming';

    if (isBlocked) {
      if (stageId === 'request' || stageId === 'analyze' || stageId === 'recommend') return 'completed';
      if (stageId === 'approval' || stageId === 'verified') return 'blocked';
      return 'upcoming';
    }

    if (stageId === 'request') return 'completed';
    if (stageId === 'analyze') return visibleSteps >= 1 ? 'completed' : isRunning ? 'current' : 'upcoming';
    if (stageId === 'recommend') return visibleSteps >= 2 || isRecReady || isReady ? 'completed' : isRunning ? 'current' : 'upcoming';
    if (stageId === 'approval') return isReady ? 'completed' : isRecReady ? 'current' : 'upcoming';
    if (stageId === 'verified') return isReady ? 'completed' : isApproving ? 'current' : 'upcoming';
    if (stageId === 'cart') return isReady ? 'current' : 'upcoming';
    if (stageId === 'payment') return 'upcoming';

    return 'upcoming';
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-arctic-soft">
      {/* Premium Compact Header */}
      <div className="bg-white border-b border-slopes/20 px-4 sm:px-8 py-3.5 shadow-2xs shrink-0">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-midnight text-white border border-mountainside/30 rounded-xl flex items-center justify-center shadow-xs text-xl shrink-0">
              🤖
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold text-midnight tracking-tight">Buyer Agent Command Centre</h1>
                <span className="px-2 py-0.5 rounded-md bg-indigo-50 border border-indigo-200/80 text-indigo-700 text-[10px] font-bold uppercase tracking-wider">
                  Autonomous AI Decision Flow
                </span>
              </div>
              <p className="text-xs text-apres mt-0.5">
                Evaluates catalog candidate choices before human approval — machine-to-machine protocol.
              </p>
            </div>
          </div>

          {/* Compact Pill-style Status Bar */}
          <div className="flex items-center gap-1.5 p-1 px-3 rounded-full border border-slate-200 bg-slate-50/90 text-[11px] shadow-2xs self-start md:self-auto">
            <span className="inline-flex items-center gap-1.5 text-indigo-700 font-semibold">
              <span className="relative inline-flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
              </span>
              {isRecReady ? 'Awaiting Human Approval' : isReady ? 'Cart Verified' : isRunning ? 'Evaluating Goal' : 'Autonomous'}
            </span>
            <span className="text-slate-300 font-light">•</span>
            <span className="inline-flex items-center gap-1 text-slate-700 font-medium">
              <span>🛡️</span> Contract Active
            </span>
            <span className="text-slate-300 font-light">•</span>
            <span className="inline-flex items-center gap-1 text-slate-700 font-medium">
              <span>🔒</span> Approval Gate
            </span>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-8 py-5">
        <div className="max-w-5xl mx-auto space-y-5">
          
          {/* User Request / Goal Card */}
          <div className="rounded-2xl border border-slopes/30 bg-white p-4 sm:p-5 shadow-2xs transition-all space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <div className="p-2 rounded-xl bg-indigo-50 border border-indigo-100 text-indigo-700 text-lg shrink-0 mt-0.5">
                  🎯
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold text-indigo-700 uppercase tracking-wider">Active Purchase Goal</span>
                    {isRunning && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-medium animate-pulse">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Evaluating Candidate Choice
                      </span>
                    )}
                  </div>
                  <h2 className="text-base sm:text-lg font-bold text-midnight mt-0.5 leading-snug break-words">
                    {result?.goal || goal ? `"${result?.goal || goal}"` : 'Enter a purchase goal to trigger the autonomous agent'}
                  </h2>
                </div>
              </div>

              {result && (
                <button
                  onClick={() => {
                    setResult(null);
                    setGoal('');
                  }}
                  disabled={isRunning || isApproving}
                  className="self-start sm:self-center px-3 py-1.5 rounded-xl border border-slopes/40 bg-arctic-soft/60 hover:bg-arctic-soft text-apres hover:text-midnight text-xs font-semibold transition-all shrink-0"
                >
                  New Goal
                </button>
              )}
            </div>

            {/* Input form bar */}
            <div className="flex gap-2 pt-1">
              <input
                type="text"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !isRunning && !isApproving) handleRun();
                }}
                placeholder="Describe a purchase goal, e.g. 'Buy the Sony WH-1000XM4 headphones'"
                className="flex-1 px-4 py-2.5 rounded-xl border border-slopes/40 bg-slate-50/50 text-midnight text-sm placeholder:text-apres/60 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500 transition-all"
              />
              <button
                onClick={() => handleRun()}
                disabled={isRunning || isApproving || !goal.trim()}
                className="px-5 py-2.5 rounded-xl bg-midnight hover:bg-mountainside text-white text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-xs hover:scale-[1.01] flex items-center justify-center gap-2 shrink-0 min-w-[120px]"
              >
                {isRunning ? (
                  <>
                    <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>Evaluating…</span>
                  </>
                ) : (
                  <>
                    <span className="text-emerald-400">⚡</span>
                    <span>Run Agent</span>
                  </>
                )}
              </button>
            </div>

            {/* Example suggestion chips */}
            {!result && !isRunning && (
              <div className="pt-2 border-t border-slopes/15">
                <p className="text-[11px] font-semibold text-apres mb-2">Try an example goal:</p>
                <div className="flex flex-wrap gap-2">
                  {EXAMPLE_CHIPS.map((chip) => (
                    <button
                      key={chip.goal}
                      onClick={() => handleRun(chip.goal)}
                      disabled={isRunning}
                      className={`px-3 py-1.5 text-xs font-medium ${chip.textColor} ${chip.bgColor} border ${chip.borderColor} ${chip.borderLeftColor} border-l-3 rounded-full transition-all duration-150 hover:-translate-y-0.5 hover:shadow-2xs flex items-center gap-1.5`}
                    >
                      <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${chip.iconBg}`}>
                        {chip.icon}
                      </span>
                      <span>{chip.goal}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {error && (
              <p className="mt-1 text-xs text-rose-600 font-medium">{error}</p>
            )}
          </div>

          {/* Outcome Banners */}
          {result && (
            <>
              {isBlocked && (
                <div className="p-4 rounded-2xl border border-rose-300 bg-rose-50/90 text-rose-900 shadow-2xs animate-in fade-in duration-200">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-bold flex items-center gap-2 text-rose-900">
                        <span>⛔</span> Blocked by Commerce Contract
                      </p>
                      <p className="text-xs mt-1 text-rose-800 leading-relaxed">
                        {result.reason || 'Action was halted by your active AI Commerce Contract.'}
                      </p>
                    </div>
                    <button
                      onClick={onOpenReplay}
                      className="px-3 py-1.5 rounded-lg bg-rose-600 text-white text-xs font-semibold hover:bg-rose-700 transition-all shrink-0 shadow-2xs"
                    >
                      Violation Log →
                    </button>
                  </div>
                </div>
              )}

              {isReady && (
                <div className="p-4 rounded-2xl border border-emerald-300 bg-emerald-50/90 text-emerald-900 shadow-2xs animate-in fade-in duration-200">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-bold flex items-center gap-2 text-emerald-900">
                        <span>✅</span> Approved &amp; Added to Shopping Cart
                      </p>
                      <p className="text-xs mt-0.5 text-emerald-800">
                        Contract verified. Review your cart and proceed to checkout.
                      </p>
                    </div>
                    <button
                      onClick={onNavigateToCart}
                      className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition-all shadow-xs shrink-0 flex items-center gap-1.5"
                    >
                      <span>🛒</span> Open Cart &amp; Checkout
                    </button>
                  </div>
                </div>
              )}

              {isMaxSteps && (
                <div className="p-4 rounded-2xl border border-amber-300 bg-amber-50/90 text-amber-900 shadow-2xs">
                  <p className="text-sm font-bold flex items-center gap-2">
                    <span>⚠️</span> Step Limit Reached
                  </p>
                  <p className="text-xs mt-1 text-amber-800">
                    {result.reason || 'The agent reached its maximum step threshold before completing.'}
                  </p>
                </div>
              )}

              {isNoMatch && (
                <div className="p-4 rounded-2xl border border-amber-300 bg-amber-50/90 text-amber-900 shadow-2xs">
                  <p className="text-sm font-bold flex items-center gap-2">
                    <span>🔎</span> No Catalog Matches
                  </p>
                  <p className="text-xs mt-1 text-amber-800">
                    {result.reason || 'No products matched the requested goal in the catalog.'}
                  </p>
                </div>
              )}

              {isError && (
                <div className="p-4 rounded-2xl border border-rose-300 bg-rose-50/90 text-rose-900 shadow-2xs">
                  <p className="text-sm font-bold flex items-center gap-2">
                    <span>🛑</span> Execution Error
                  </p>
                  <p className="text-xs mt-1 text-rose-800">
                    {result.reason || 'The autonomous run encountered an error.'}
                  </p>
                </div>
              )}

              {/* Agent Command Centre & Hero AI Recommendation Card */}
              {context && (
                <div className="space-y-4">
                  {/* Grid: Agent Understanding + Hero AI Recommendation */}
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-stretch">
                    
                    {/* Agent Understanding Card (5 columns) */}
                    <div className="md:col-span-5 rounded-2xl border border-slopes/30 bg-white p-4 sm:p-5 shadow-2xs flex flex-col justify-between space-y-3">
                      <div>
                        <div className="flex items-center justify-between pb-2 border-b border-slopes/15 mb-3">
                          <div className="flex items-center gap-2">
                            <span className="p-1.5 rounded-lg bg-indigo-100 text-indigo-700 text-xs">🧠</span>
                            <span className="text-xs font-bold text-midnight uppercase tracking-wider">
                              Agent Understanding
                            </span>
                          </div>
                          <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-[10px] font-mono">
                            Intent Parsed
                          </span>
                        </div>

                        <p className="text-xs text-apres font-medium">Understood Goal:</p>
                        <p className="text-xs sm:text-sm font-semibold text-midnight mt-0.5 leading-snug break-words">
                          "{context.goal}"
                        </p>
                      </div>

                      <div className="space-y-2 pt-2 border-t border-slopes/15">
                        <p className="text-[10px] font-bold text-apres uppercase tracking-wider">Extracted Criteria:</p>
                        <div className="flex flex-wrap gap-1.5">
                          {context.category && (
                            <span className="px-2.5 py-1 rounded-lg bg-sky-50 border border-sky-200 text-sky-800 text-[11px] font-semibold flex items-center gap-1">
                              <span>🗂️</span> {context.category}
                            </span>
                          )}
                          {context.maxBudget != null && (
                            <span className="px-2.5 py-1 rounded-lg bg-violet-50 border border-violet-200 text-violet-800 text-[11px] font-semibold flex items-center gap-1">
                              <span>₹</span> {context.maxBudget.toLocaleString('en-IN')} max budget
                            </span>
                          )}
                          {context.searchQuery && (
                            <span className="px-2.5 py-1 rounded-lg bg-slate-100 border border-slate-200 text-slate-700 text-[11px] font-medium flex items-center gap-1">
                              <span>🔍</span> "{context.searchQuery}"
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* AI Recommendation Card (HERO CARD - 7 columns) */}
                    <div className="md:col-span-7">
                      {hasRecommendation ? (
                        <div className="h-full rounded-2xl border-2 border-emerald-500/40 bg-gradient-to-br from-emerald-50/90 via-white to-emerald-50/30 p-4 sm:p-5 shadow-sm flex flex-col justify-between space-y-3 relative overflow-hidden">
                          
                          {/* Top Highlight Bar */}
                          <div className="flex items-center justify-between gap-2 pb-2 border-b border-emerald-200/70">
                            <div className="flex items-center gap-2">
                              <span className="p-1.5 rounded-lg bg-emerald-500 text-white text-xs shadow-2xs">⭐</span>
                              <span className="text-xs font-extrabold text-emerald-950 uppercase tracking-wider">
                                AI BUYER AGENT
                              </span>
                            </div>
                            
                            <div className="flex items-center gap-1.5">
                              {isRecReady && (
                                <span className="px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300 text-[10px] font-bold animate-pulse">
                                  🔒 Human Approval Required
                                </span>
                              )}
                              {isReady && (
                                <span className="px-2.5 py-0.5 rounded-full bg-emerald-600 text-white text-[10px] font-bold">
                                  ✓ Added to Cart
                                </span>
                              )}
                            </div>
                          </div>

                          {/* Recommendation Title & Hero Product */}
                          <div>
                            <p className="text-[11px] font-bold text-emerald-800 uppercase tracking-wider">
                              "Here's what I recommend"
                            </p>
                            <div className="flex items-baseline justify-between gap-2 mt-1">
                              <h3 className="text-base sm:text-xl font-extrabold text-midnight tracking-tight">
                                {context.recommendedName}
                              </h3>
                              {context.recommendedPrice != null && (
                                <div className="text-base sm:text-xl font-mono font-bold text-emerald-950 bg-emerald-100/90 px-3 py-1 rounded-xl border border-emerald-300/80 shrink-0">
                                  ₹{context.recommendedPrice.toLocaleString('en-IN')}
                                </div>
                              )}
                            </div>
                          </div>

                          {/* "Why this product?" Section */}
                          <div className="pt-2 border-t border-emerald-200/60 space-y-1.5">
                            <p className="text-[10px] font-bold text-emerald-900 uppercase tracking-wider flex items-center gap-1">
                              <span>💡</span> Why this product?
                            </p>
                            <div className="space-y-1 text-xs text-emerald-950 font-medium">
                              <div className="flex items-center gap-2">
                                <span className="text-emerald-600 font-bold">✓</span>
                                <span>Matches your requested product</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="text-emerald-600 font-bold">✓</span>
                                <span>Meets the required specifications</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="text-emerald-600 font-bold">✓</span>
                                <span>Best available match based on your constraints</span>
                              </div>
                            </div>
                          </div>

                          {/* Explicit Human Approval Action Buttons */}
                          <div className="pt-3 border-t border-emerald-200/80 flex flex-col sm:flex-row items-center justify-between gap-2">
                            <button
                              onClick={onOpenTrace}
                              className="w-full sm:w-auto px-4 py-2 rounded-xl border border-emerald-300 bg-white hover:bg-emerald-50 text-emerald-950 text-xs font-semibold transition-all shadow-2xs flex items-center justify-center gap-1.5"
                            >
                              <span>🧭</span> View Decision
                            </button>

                            {isRecReady && (
                              <button
                                onClick={handleApprovePurchase}
                                disabled={isApproving}
                                className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-extrabold transition-all shadow-md hover:scale-[1.02] flex items-center justify-center gap-2 disabled:opacity-50"
                              >
                                {isApproving ? (
                                  <>
                                    <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24" fill="none">
                                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    <span>Verifying Contract…</span>
                                  </>
                                ) : (
                                  <>
                                    <span>✓</span>
                                    <span>Approve Purchase</span>
                                  </>
                                )}
                              </button>
                            )}

                            {isReady && (
                              <button
                                onClick={onNavigateToCart}
                                className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-midnight hover:bg-mountainside text-white text-xs font-bold transition-all shadow-xs flex items-center justify-center gap-1.5"
                              >
                                <span>🛒</span> Proceed to Cart
                              </button>
                            )}
                          </div>
                        </div>
                      ) : (
                        <div className="h-full rounded-2xl border border-slopes/30 bg-white p-5 flex flex-col items-center justify-center text-center space-y-2">
                          <span className="text-2xl text-slate-400">🔍</span>
                          <p className="text-xs font-semibold text-midnight">Evaluating Catalog Recommendations</p>
                          <p className="text-[11px] text-apres">AI selection will appear here as search completes</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Connected Decision Timeline */}
                  <div className="rounded-2xl border border-slopes/30 bg-white p-4 sm:p-5 shadow-2xs space-y-3">
                    <div className="flex items-center justify-between pb-2 border-b border-slopes/15">
                      <div className="flex items-center gap-2">
                        <span className="p-1.5 rounded-lg bg-indigo-100 text-indigo-700 text-xs">🗺️</span>
                        <span className="text-xs font-bold text-midnight uppercase tracking-wider">
                          Connected Decision Flow
                        </span>
                      </div>
                      <span className="text-[11px] text-apres font-mono">
                        Run ID: {result.run_id}
                      </span>
                    </div>

                    {/* Timeline Stepper */}
                    <div className="pt-2 pb-1 overflow-x-auto">
                      <div className="flex items-center justify-between min-w-[700px] relative">
                        
                        {TIMELINE_STAGES.map((stage, idx) => {
                          const status = getStageStatus(stage.id);
                          const isLast = idx === TIMELINE_STAGES.length - 1;

                          return (
                            <div key={stage.id} className="flex-1 flex items-center relative">
                              {/* Node */}
                              <div className="flex flex-col items-center z-10 shrink-0 mx-auto">
                                <div
                                  className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                                    status === 'completed'
                                      ? 'bg-emerald-600 text-white shadow-xs ring-4 ring-emerald-100'
                                      : status === 'blocked'
                                      ? 'bg-rose-600 text-white shadow-xs ring-4 ring-rose-100'
                                      : status === 'current'
                                      ? 'bg-amber-500 text-white shadow-xs ring-4 ring-amber-100 animate-pulse'
                                      : 'bg-slate-100 text-slate-400 border border-slate-300'
                                  }`}
                                >
                                  {status === 'completed' ? '✓' : status === 'blocked' ? '⛔' : stage.icon}
                                </div>
                                <span className={`text-[11px] font-bold mt-1.5 text-center ${
                                  status === 'completed' ? 'text-emerald-950' : status === 'blocked' ? 'text-rose-900' : status === 'current' ? 'text-amber-900 font-extrabold' : 'text-slate-400'
                                }`}>
                                  {stage.label}
                                </span>
                                <span className="text-[9px] text-apres/80 font-mono text-center">
                                  {stage.description}
                                </span>
                              </div>

                              {/* Connector Line */}
                              {!isLast && (
                                <div
                                  className={`h-0.5 flex-1 mx-2 transition-all ${
                                    status === 'completed'
                                      ? 'bg-emerald-500'
                                      : status === 'blocked'
                                      ? 'bg-rose-400 border-dashed'
                                      : 'bg-slate-200'
                                  }`}
                                />
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Quick navigation buttons */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-3 border-t border-slopes/15">
                      <button
                        onClick={onOpenReplay}
                        className="py-2 px-3 rounded-xl border border-slopes/40 bg-slate-50 hover:bg-slate-100 text-midnight text-xs font-semibold transition-all flex items-center justify-center gap-1.5 shadow-2xs"
                      >
                        <span>▶</span> Replay Purchase Journey
                      </button>
                      <button
                        onClick={onOpenTrace}
                        className="py-2 px-3 rounded-xl bg-midnight hover:bg-mountainside text-white text-xs font-semibold transition-all flex items-center justify-center gap-1.5 shadow-2xs"
                      >
                        <span>🧭</span> View Decision Trace
                      </button>
                      {onOpenLab && (
                        <button
                          onClick={onOpenLab}
                          className="py-2 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition-all flex items-center justify-center gap-1.5 shadow-2xs"
                        >
                          <span>🧪</span> AI Decision Lab
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Collapsible Technical Execution Data (JSON Stream) */}
                  <div className="rounded-2xl border border-midnight/70 bg-midnight shadow-md overflow-hidden">
                    {/* Header Bar with Toggle */}
                    <button
                      onClick={() => setShowProtocolStream(!showProtocolStream)}
                      className="w-full px-4 py-3 bg-midnight-surface hover:bg-midnight-light border-b border-white/10 flex items-center justify-between text-left transition-all"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1.5">
                          <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80 inline-block"></span>
                          <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80 inline-block"></span>
                          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80 inline-block"></span>
                        </div>
                        <span className="font-mono text-xs font-bold tracking-wider text-slopes uppercase flex items-center gap-1.5">
                          <span>🖥️</span> TECHNICAL EXECUTION DATA (JSON STREAM)
                        </span>
                      </div>

                      <div className="flex items-center gap-3">
                        <span className="font-mono text-[11px] text-emerald-400 bg-black/40 px-2 py-0.5 rounded border border-emerald-500/30">
                          {visibleSteps}/{result.actions.length} frames
                        </span>
                        <span className="px-3 py-1 rounded-lg bg-white/10 text-white text-xs font-semibold hover:bg-white/20 transition-all flex items-center gap-1">
                          {showProtocolStream ? 'Collapse Logs ▴' : 'Expand Execution Logs ▾'}
                        </span>
                      </div>
                    </button>

                    {/* Collapsed Summary Line */}
                    {!showProtocolStream && (
                      <div className="px-4 py-3 text-xs font-mono text-slopes flex items-center justify-between bg-midnight/90">
                        <span>▸ {result.actions.length} protocol frames captured autonomously.</span>
                        <span
                          onClick={() => setShowProtocolStream(true)}
                          className="text-emerald-400 hover:underline cursor-pointer"
                        >
                          View JSON Stream →
                        </span>
                      </div>
                    )}

                    {/* Expanded Stream Content */}
                    {showProtocolStream && (
                      <div className="p-4 space-y-3.5 max-h-[50vh] overflow-y-auto">
                        {result.actions.slice(0, visibleSteps).map((action) => {
                          const blocked = isStepBlocked(action);
                          return (
                            <div
                              key={action.step}
                              className={`rounded-xl px-4 py-3 border transition-all ${
                                blocked
                                  ? 'bg-rose-950/40 border-rose-500/60 shadow-xs shadow-rose-950/60'
                                  : 'bg-midnight-surface/80 border-white/10'
                              }`}
                            >
                              <div className="flex items-center justify-between text-xs font-mono mb-2.5 pb-2 border-b border-white/5">
                                <div className="flex items-center gap-2">
                                  <span
                                    className={`px-2.5 py-0.5 rounded-md border text-[11px] font-bold uppercase tracking-wider font-mono ${
                                      blocked
                                        ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                                        : 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
                                    }`}
                                  >
                                    {blocked ? '⛔ STEP' : 'STEP'} {action.step}
                                  </span>
                                  <span
                                    className={`px-2.5 py-0.5 rounded-md border text-[11px] font-semibold font-mono ${
                                      ACTION_COLORS[action.action] || 'text-sky-300 border-sky-500/30 bg-sky-500/10'
                                    }`}
                                  >
                                    {action.action}
                                  </span>
                                </div>
                                {blocked && (
                                  <span className="text-[10px] font-bold font-mono text-rose-400 bg-rose-500/20 border border-rose-500/30 px-2 py-0.5 rounded uppercase tracking-wider">
                                    Contract Blocked
                                  </span>
                                )}
                              </div>
                              <pre className="text-xs sm:text-[13px] leading-relaxed text-arctic font-mono whitespace-pre-wrap break-words overflow-x-auto">
                                {renderHighlightedJson({
                                  action: action.action,
                                  input: action.input,
                                  result: action.output,
                                })}
                              </pre>
                            </div>
                          );
                        })}
                        {visibleSteps < result.actions.length && (
                          <div className="text-xs font-mono text-emerald-400/90 animate-pulse px-2 py-1 flex items-center gap-2">
                            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400"></span>
                            ▸ streaming next protocol frame…
                          </div>
                        )}
                        <div ref={logEndRef} />
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Empty State when no run performed yet */}
          {!result && !isRunning && (
            <div className="rounded-2xl border border-slopes/25 bg-white p-8 text-center space-y-3 shadow-2xs">
              <div className="w-12 h-12 bg-slate-50 border border-slopes/30 rounded-2xl flex items-center justify-center mx-auto text-xl shadow-2xs text-slate-500">
                📡
              </div>
              <h3 className="text-sm font-bold text-midnight">No Autonomous Run Active</h3>
              <p className="text-xs text-apres max-w-md mx-auto leading-relaxed">
                Describe a purchase goal above and click <strong>Run Agent</strong>. The agent will evaluate candidates, present a recommendation, and await your explicit approval before contract verification and cart insertion.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
