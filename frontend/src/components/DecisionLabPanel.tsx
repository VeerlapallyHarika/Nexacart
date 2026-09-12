'use client';

import { useState, useEffect, useRef } from 'react';
import {
  DecisionLabExplanation,
  DecisionLabAlternatives,
  DecisionLabAlternative,
  DecisionLabCompareResult,
  SimulationResult,
  SimulationSummary,
  SimulationConstraint,
} from '@/lib/types';
import {
  fetchDecisionLabExplanation,
  fetchDecisionLabAlternatives,
  compareProducts,
  runSimulation,
  applySimulation,
  fetchSimulations,
} from '@/lib/api';

interface DecisionLabPanelProps {
  decisionId: string | null;
  sessionId: string | undefined;
  isOpen: boolean;
  onClose: () => void;
  onApplied?: (productName: string) => void;
}

type TabType = 'explain' | 'alternatives' | 'simulate' | 'history';

function formatCurrency(val?: number | null): string {
  if (val == null) return '';
  return `₹${Number(val).toLocaleString('en-IN')}`;
}

export default function DecisionLabPanel({
  decisionId,
  sessionId,
  isOpen,
  onClose,
  onApplied,
}: DecisionLabPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('explain');

  // Explanation state
  const [explanation, setExplanation] = useState<DecisionLabExplanation | null>(null);
  const [isExplainLoading, setIsExplainLoading] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);

  // Alternatives state
  const [alternativesData, setAlternativesData] = useState<DecisionLabAlternatives | null>(null);
  const [isAltLoading, setIsAltLoading] = useState(false);
  const [altError, setAltError] = useState<string | null>(null);

  // Compare state
  const [compareResult, setCompareResult] = useState<DecisionLabCompareResult | null>(null);
  const [isComparing, setIsComparing] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);
  const [comparingProductId, setComparingProductId] = useState<string | null>(null);

  // Simulation state
  const [simBudget, setSimBudget] = useState<string>('');
  const [simMinBudget, setSimMinBudget] = useState<string>('');
  const [simCategory, setSimCategory] = useState<string>('');
  const [simBrand, setSimBrand] = useState<string>('');
  const [simLabel, setSimLabel] = useState<string>('');
  const [constraints, setConstraints] = useState<SimulationConstraint[]>([]);
  const [newConstraintKey, setNewConstraintKey] = useState('');
  const [newConstraintVal, setNewConstraintVal] = useState('');
  const [newConstraintOp, setNewConstraintOp] = useState('gte');

  const [activeSimulation, setActiveSimulation] = useState<SimulationResult | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  // History state
  const [simulations, setSimulations] = useState<SimulationSummary[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  // Apply state
  const [isApplying, setIsApplying] = useState(false);
  const [applySuccessMessage, setApplySuccessMessage] = useState<string | null>(null);
  const [applyErrorMessage, setApplyErrorMessage] = useState<string | null>(null);

  // Staleness guard: track the active decisionId to prevent stale async
  // responses from overwriting state for a newer decision.
  const activeDecisionRef = useRef<string | null>(null);

  // Load data when opened or decisionId changes
  useEffect(() => {
    if (isOpen && decisionId) {
      activeDecisionRef.current = decisionId;
      resetState();
      loadExplanation();
      loadAlternatives();
      loadSimulations();
    } else if (isOpen && !decisionId) {
      // Panel opened without a valid decisionId - show empty state
      resetState();
    } else {
      resetState();
    }
  }, [isOpen, decisionId]);

  const resetState = () => {
    setExplanation(null);
    setAlternativesData(null);
    setCompareResult(null);
    setActiveSimulation(null);
    setSimulations([]);
    setExplainError(null);
    setAltError(null);
    setCompareError(null);
    setSimError(null);
    setHistoryError(null);
    setApplySuccessMessage(null);
    setApplyErrorMessage(null);
    setActiveTab('explain');
  };

  const loadExplanation = async () => {
    if (!decisionId) return;
    const reqDecision = decisionId;
    setIsExplainLoading(true);
    setExplainError(null);
    try {
      const data = await fetchDecisionLabExplanation(decisionId);
      if (activeDecisionRef.current !== reqDecision) return;
      setExplanation(data);
      if (data.product?.price) {
        setSimBudget(String(data.product.price));
      }
      if (data.product?.category) {
        setSimCategory(data.product.category);
      }
    } catch (err: any) {
      if (activeDecisionRef.current !== reqDecision) return;
      // Handle "not found" errors gracefully - don't show as error
      const msg = err.message || '';
      if (msg.includes('404') || msg.includes('not found') || msg.includes('No decision trace')) {
        setExplainError(null);
      } else {
        setExplainError(msg || 'Failed to load recommendation explanation');
      }
    } finally {
      if (activeDecisionRef.current === reqDecision) {
        setIsExplainLoading(false);
      }
    }
  };

  const loadAlternatives = async () => {
    if (!decisionId) return;
    const reqDecision = decisionId;
    setIsAltLoading(true);
    setAltError(null);
    try {
      const data = await fetchDecisionLabAlternatives(decisionId, 6);
      if (activeDecisionRef.current !== reqDecision) return;
      setAlternativesData(data);
    } catch (err: any) {
      if (activeDecisionRef.current !== reqDecision) return;
      // Handle "not found" errors gracefully - don't show as error
      const msg = err.message || '';
      if (msg.includes('404') || msg.includes('not found') || msg.includes('No decision trace')) {
        setAltError(null);
      } else {
        setAltError(msg || 'Failed to load alternatives');
      }
    } finally {
      if (activeDecisionRef.current === reqDecision) {
        setIsAltLoading(false);
      }
    }
  };

  const loadSimulations = async () => {
    if (!decisionId) return;
    const reqDecision = decisionId;
    setIsHistoryLoading(true);
    setHistoryError(null);
    try {
      const data = await fetchSimulations(decisionId);
      if (activeDecisionRef.current !== reqDecision) return;
      setSimulations(data);
    } catch (err: any) {
      if (activeDecisionRef.current !== reqDecision) return;
      // Handle "not found" errors gracefully - don't show as error
      const msg = err.message || '';
      if (msg.includes('404') || msg.includes('not found') || msg.includes('No decision trace')) {
        setHistoryError(null);
      } else {
        setHistoryError(msg || 'Failed to load simulation history');
      }
    } finally {
      if (activeDecisionRef.current === reqDecision) {
        setIsHistoryLoading(false);
      }
    }
  };

  const handleCompare = async (alt: DecisionLabAlternative) => {
    if (!explanation?.product?.id) return;
    setComparingProductId(alt.id);
    setIsComparing(true);
    setCompareError(null);
    try {
      const result = await compareProducts(explanation.product.id, alt.id);
      setCompareResult(result);
    } catch (err: any) {
      setCompareError(err.message || 'Failed to compare products');
    } finally {
      setIsComparing(false);
    }
  };

  const handleAddConstraint = () => {
    if (!newConstraintKey.trim() || !newConstraintVal.trim()) return;
    const numVal = Number(newConstraintVal);
    const value = isNaN(numVal) ? newConstraintVal.trim() : numVal;
    setConstraints([
      ...constraints,
      { key: newConstraintKey.trim(), value, operator: newConstraintOp },
    ]);
    setNewConstraintKey('');
    setNewConstraintVal('');
  };

  const handleRemoveConstraint = (index: number) => {
    setConstraints(constraints.filter((_, i) => i !== index));
  };

  const handleRunSimulation = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!decisionId || !sessionId) return;

    setIsSimulating(true);
    setSimError(null);
    setApplySuccessMessage(null);
    setApplyErrorMessage(null);

    try {
      const payload: any = {
        session_id: sessionId,
        label: simLabel.trim() || undefined,
        max_price: simBudget ? Number(simBudget) : undefined,
        min_price: simMinBudget ? Number(simMinBudget) : undefined,
        category: simCategory.trim() || undefined,
        brand: simBrand.trim() || undefined,
        constraints: constraints.length > 0 ? constraints : undefined,
      };
      const result = await runSimulation(decisionId, payload);
      setActiveSimulation(result);
      loadSimulations();
    } catch (err: any) {
      setSimError(err.message || 'Simulation failed to run');
    } finally {
      setIsSimulating(false);
    }
  };

  const handleApply = async (simulationId: string) => {
    if (!sessionId) return;
    setIsApplying(true);
    setApplySuccessMessage(null);
    setApplyErrorMessage(null);

    try {
      const res = await applySimulation(simulationId, sessionId);
      setApplySuccessMessage(res.message);
      loadSimulations();
      loadExplanation();
      loadAlternatives();
      setActiveTab('explain');
      if (onApplied && res.product?.name) {
        onApplied(res.product.name);
      }
    } catch (err: any) {
      setApplyErrorMessage(err.message || 'Failed to apply simulation recommendation');
    } finally {
      setIsApplying(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-midnight/70 backdrop-blur-xs z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slopes/40 w-full max-w-2xl max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="p-5 border-b border-slopes/25 bg-arctic-soft/40 flex-shrink-0">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <span className="text-2xl">🧪</span>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-midnight tracking-tight">AI Decision Lab</h2>
                  <span className="px-2 py-0.5 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-[10px] font-bold">
                    Interactive Trade-off Simulator
                  </span>
                </div>
                <p className="text-xs text-apres">
                  Understand reasoning, evaluate alternatives & simulate what-if scenarios
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-arctic text-apres hover:text-midnight rounded-xl transition-all border border-transparent hover:border-slopes/30"
              title="Close Decision Lab"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Decision ID and Meta */}
          {decisionId && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-md border border-mountainside/30 bg-midnight text-arctic font-mono text-[11px] font-bold">
                {decisionId}
              </span>
              {explanation?.product && (
                <span
                  key={explanation.product.name}
                  className="text-xs text-apres animate-highlight-flash px-2 py-0.5 rounded-md"
                >
                  Target: <strong className="text-midnight">{explanation.product.name}</strong> ({formatCurrency(explanation.product.price)})
                </span>
              )}
            </div>
          )}

          {/* Navigation Tabs */}
          <div className="mt-4 flex gap-1 bg-arctic-soft p-1 rounded-xl border border-slopes/30">
            <button
              onClick={() => setActiveTab('explain')}
              className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                activeTab === 'explain'
                  ? 'bg-white text-midnight shadow-xs border border-slopes/20'
                  : 'text-apres hover:text-midnight'
              }`}
            >
              <span>💡</span> Why Recommended?
            </button>
            <button
              onClick={() => setActiveTab('alternatives')}
              className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                activeTab === 'alternatives'
                  ? 'bg-white text-midnight shadow-xs border border-slopes/20'
                  : 'text-apres hover:text-midnight'
              }`}
            >
              <span>🔄</span> Alternatives
            </button>
            <button
              onClick={() => setActiveTab('simulate')}
              className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                activeTab === 'simulate'
                  ? 'bg-white text-midnight shadow-xs border border-slopes/20'
                  : 'text-apres hover:text-midnight'
              }`}
            >
              <span>⚡</span> What-If Simulator
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                activeTab === 'history'
                  ? 'bg-white text-midnight shadow-xs border border-slopes/20'
                  : 'text-apres hover:text-midnight'
              }`}
            >
              <span>📜</span> History ({simulations.length})
            </button>
          </div>
        </div>

        {/* Tab Content Body */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* TAB 1: WHY THIS RECOMMENDATION */}
          {activeTab === 'explain' && (
            <div className="space-y-4">
              {isExplainLoading ? (
                <div className="py-12 text-center text-apres">
                  <div className="inline-block h-8 w-8 border-3 border-slopes border-t-midnight rounded-full animate-spin mb-3" />
                  <p className="text-xs font-semibold">Analyzing recommendation reasoning...</p>
                </div>
              ) : explainError ? (
                <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-center text-rose-700 text-xs">
                  <p className="font-bold">{explainError}</p>
                </div>
              ) : explanation ? (
                <>
                  {/* Recommended Product Card */}
                  <div className="bg-arctic-soft/60 border border-slopes/30 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 border border-emerald-300 rounded text-[10px] font-bold">
                          AI Chosen Match
                        </span>
                        <span className="text-[11px] text-apres uppercase font-bold tracking-wider">
                          {explanation.product.category}
                        </span>
                      </div>
                      <h3 className="text-base font-bold text-midnight mt-1">
                        {explanation.product.name}
                      </h3>
                      <p className="text-base font-extrabold text-midnight mt-0.5">
                        {formatCurrency(explanation.product.price)}
                      </p>
                    </div>

                    <div className="flex flex-col items-end gap-1">
                      <div className="text-right">
                        <span className="text-2xl font-black text-emerald-600">
                          {explanation.match_percentage}%
                        </span>
                        <span className="text-xs text-apres block">Overall Match Score</span>
                      </div>
                      <div className="w-32 bg-slopes/30 rounded-full h-2 overflow-hidden mt-1">
                        <div
                          className="bg-emerald-500 h-full rounded-full"
                          style={{ width: `${Math.min(explanation.match_percentage, 100)}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Why it matches vs Trade-offs */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {/* Strong Matches */}
                    <div className="bg-emerald-50/50 border border-emerald-200/60 rounded-xl p-4">
                      <div className="flex items-center gap-1.5 mb-2 text-emerald-800 font-bold text-xs">
                        <span>✅</span> Strong Matches & Fit
                      </div>
                      {explanation.strong_matches.length > 0 ? (
                        <ul className="space-y-1.5">
                          {explanation.strong_matches.map((item, idx) => (
                            <li key={idx} className="text-xs text-emerald-900 flex items-start gap-2">
                              <span className="text-emerald-500 font-bold">•</span>
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-xs text-apres italic">No strong match details recorded.</p>
                      )}
                    </div>

                    {/* Trade-offs */}
                    <div className="bg-amber-50/50 border border-amber-200/60 rounded-xl p-4">
                      <div className="flex items-center gap-1.5 mb-2 text-amber-800 font-bold text-xs">
                        <span>⚠️</span> Trade-offs & Compromises
                      </div>
                      {explanation.trade_offs.length > 0 ? (
                        <ul className="space-y-1.5">
                          {explanation.trade_offs.map((item, idx) => (
                            <li key={idx} className="text-xs text-amber-900 flex items-start gap-2">
                              <span className="text-amber-500 font-bold">•</span>
                              <span>{item}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-xs text-emerald-700 font-medium">
                          No major trade-offs or compromises identified.
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Search Candidate Funnel */}
                  <div className="bg-arctic-soft/40 border border-slopes/25 rounded-xl p-3.5 flex items-center justify-between text-xs text-apres">
                    <div>
                      <span>Scanned Catalog: </span>
                      <strong className="text-midnight">{explanation.total_candidates_scanned} products</strong>
                    </div>
                    <div>
                      <span>Ranked Pool: </span>
                      <strong className="text-midnight">{explanation.total_candidates_ranked} candidates</strong>
                    </div>
                    <div>
                      <span>Contract Status: </span>
                      <strong className={explanation.contract?.passed ? 'text-emerald-700' : 'text-amber-700'}>
                        {explanation.contract?.active ? (explanation.contract.passed ? 'Compliant' : 'Contract Warning') : 'No Active Contract'}
                      </strong>
                    </div>
                  </div>
                </>
              ) : (
                <div className="py-12 text-center text-apres">
                  <div className="w-14 h-14 bg-arctic-soft rounded-2xl flex items-center justify-center mx-auto mb-3 text-2xl border border-slopes/25">
                    🧪
                  </div>
                  <p className="font-bold text-midnight text-sm">No active AI decision yet</p>
                  <p className="text-xs text-apres mt-1">Run the Buyer Agent or AI Assistant to create a decision trace.</p>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: ALTERNATIVES & COMPARISON */}
          {activeTab === 'alternatives' && (
            <div className="space-y-4">
              {isAltLoading ? (
                <div className="py-12 text-center text-apres">
                  <div className="inline-block h-8 w-8 border-3 border-slopes border-t-midnight rounded-full animate-spin mb-3" />
                  <p className="text-xs font-semibold">Finding real alternative products...</p>
                </div>
              ) : altError ? (
                <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-center text-rose-700 text-xs">
                  <p className="font-bold">{altError}</p>
                </div>
              ) : compareResult ? (
                /* INLINE COMPARISON VIEW */
                <div className="space-y-4 animate-in fade-in">
                  <div className="flex items-center justify-between">
                    <button
                      onClick={() => setCompareResult(null)}
                      className="px-3 py-1.5 bg-arctic-soft hover:bg-arctic border border-slopes/30 rounded-lg text-xs font-bold text-mountainside flex items-center gap-1 transition-all"
                    >
                      ← Back to All Alternatives
                    </button>
                    <span className="text-xs text-apres font-bold">Side-by-Side Comparison</span>
                  </div>

                  {/* Product Cards Side by Side */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-emerald-50/40 border border-emerald-200 rounded-xl p-3.5">
                      <span className="text-[10px] font-bold text-emerald-800 uppercase tracking-wider block">
                        Original Recommendation (A)
                      </span>
                      <h4 className="font-bold text-midnight text-sm mt-1">{compareResult.product_a.name}</h4>
                      <p className="text-sm font-extrabold text-midnight mt-0.5">
                        {formatCurrency(compareResult.product_a.price)}
                      </p>
                      <div className="mt-2 text-xs text-emerald-700 font-semibold">
                        Match Score: {compareResult.overall_a_match}%
                      </div>
                    </div>

                    <div className="bg-indigo-50/40 border border-indigo-200 rounded-xl p-3.5">
                      <span className="text-[10px] font-bold text-indigo-800 uppercase tracking-wider block">
                        Alternative Candidate (B)
                      </span>
                      <h4 className="font-bold text-midnight text-sm mt-1">{compareResult.product_b.name}</h4>
                      <p className="text-sm font-extrabold text-midnight mt-0.5">
                        {formatCurrency(compareResult.product_b.price)}
                      </p>
                      <div className="mt-2 text-xs text-indigo-700 font-semibold">
                        Match Score: {compareResult.overall_b_match}%
                      </div>
                    </div>
                  </div>

                  {/* Comparison Attribute Table */}
                  <div className="border border-slopes/30 rounded-xl overflow-hidden bg-white">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-arctic-soft/60 border-b border-slopes/25 text-[11px] font-bold text-apres">
                        <tr>
                          <th className="p-3">Attribute</th>
                          <th className="p-3">{compareResult.product_a.name}</th>
                          <th className="p-3">{compareResult.product_b.name}</th>
                          <th className="p-3">Verdict & Trade-off</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slopes/20">
                        {compareResult.comparisons.map((c, i) => (
                          <tr key={i} className="hover:bg-arctic-soft/20 transition-colors">
                            <td className="p-3 font-semibold text-midnight">{c.label}</td>
                            <td className="p-3 text-mountainside">{c.a_display}</td>
                            <td className="p-3 text-mountainside">{c.b_display}</td>
                            <td className="p-3">
                              <span
                                className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                                  c.verdict === 'b_better'
                                    ? 'bg-indigo-100 text-indigo-800'
                                    : c.verdict === 'a_better'
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : c.verdict === 'similar'
                                    ? 'bg-gray-100 text-gray-700'
                                    : 'bg-amber-100 text-amber-800'
                                }`}
                              >
                                {c.verdict === 'b_better'
                                  ? 'Alternative Better'
                                  : c.verdict === 'a_better'
                                  ? 'Original Better'
                                  : c.verdict === 'similar'
                                  ? 'Similar'
                                  : 'Trade-off'}
                              </span>
                              <span className="text-[11px] text-apres block mt-0.5">{c.summary}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : alternativesData && alternativesData.alternatives.length > 0 ? (
                <div className="space-y-3">
                  <p className="text-xs text-apres font-medium">
                    Found {alternativesData.alternatives.length} viable alternatives ranked by product fit and attributes.
                  </p>
                  <div className="space-y-2.5">
                    {alternativesData.alternatives.map((alt) => (
                      <div
                        key={alt.id}
                        className="bg-arctic-soft/40 border border-slopes/30 rounded-xl p-3.5 flex items-center justify-between gap-3 hover:border-slopes/60 transition-all"
                      >
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h4 className="font-bold text-midnight text-xs">{alt.name}</h4>
                            <span className="px-1.5 py-0.5 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded text-[10px] font-bold">
                              {alt.match_percentage}% Match
                            </span>
                          </div>
                          <p className="text-xs font-bold text-midnight mt-0.5">
                            {formatCurrency(alt.price)}
                          </p>
                          <div className="flex flex-wrap gap-1.5 mt-1.5">
                            {Object.entries(alt.attributes || {})
                              .slice(0, 3)
                              .map(([k, v]) => (
                                <span
                                  key={k}
                                  className="text-[10px] px-1.5 py-0.5 bg-white border border-slopes/20 rounded text-apres"
                                >
                                  {k.replace(/_/g, ' ')}: {String(v)}
                                </span>
                              ))}
                          </div>
                        </div>

                        <button
                          onClick={() => handleCompare(alt)}
                          disabled={isComparing && comparingProductId === alt.id}
                          className="py-1.5 px-3 bg-midnight hover:bg-mountainside text-white font-bold text-xs rounded-lg transition-all flex-shrink-0"
                        >
                          {isComparing && comparingProductId === alt.id ? 'Comparing...' : '⚖️ Compare'}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="py-12 text-center text-apres">
                  <div className="w-14 h-14 bg-arctic-soft rounded-2xl flex items-center justify-center mx-auto mb-3 text-2xl border border-slopes/25">
                    🔄
                  </div>
                  <p className="font-bold text-midnight text-sm">No active AI decision yet</p>
                  <p className="text-xs text-apres mt-1">Run the Buyer Agent or AI Assistant to see alternatives.</p>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: WHAT-IF SIMULATION */}
          {activeTab === 'simulate' && (
            <div className="space-y-5">
              {/* Simulator Form */}
              <form onSubmit={handleRunSimulation} className="bg-arctic-soft/40 border border-slopes/30 rounded-xl p-4 space-y-3.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-midnight uppercase tracking-wider">
                    Modify Constraints & Parameters
                  </span>
                  <span className="text-[10px] text-apres">Simulate without modifying original trace</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-bold text-apres mb-1">Max Budget (₹)</label>
                    <input
                      type="number"
                      value={simBudget}
                      onChange={(e) => setSimBudget(e.target.value)}
                      placeholder="e.g. 80000"
                      className="w-full text-xs p-2.5 rounded-lg border border-slopes/40 bg-white focus:outline-none focus:border-indigo-500 font-semibold"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold text-apres mb-1">Min Budget (₹)</label>
                    <input
                      type="number"
                      value={simMinBudget}
                      onChange={(e) => setSimMinBudget(e.target.value)}
                      placeholder="e.g. 40000"
                      className="w-full text-xs p-2.5 rounded-lg border border-slopes/40 bg-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold text-apres mb-1">Category</label>
                    <input
                      type="text"
                      value={simCategory}
                      onChange={(e) => setSimCategory(e.target.value)}
                      placeholder="e.g. laptops, headphones"
                      className="w-full text-xs p-2.5 rounded-lg border border-slopes/40 bg-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold text-apres mb-1">Brand</label>
                    <input
                      type="text"
                      value={simBrand}
                      onChange={(e) => setSimBrand(e.target.value)}
                      placeholder="e.g. Apple, Sony, Dell"
                      className="w-full text-xs p-2.5 rounded-lg border border-slopes/40 bg-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>

                {/* Custom Constraints List */}
                <div className="pt-2 border-t border-slopes/20">
                  <label className="block text-[11px] font-bold text-apres mb-1">
                    Attribute Constraints (RAM, Battery, ANC, etc.)
                  </label>
                  <div className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={newConstraintKey}
                      onChange={(e) => setNewConstraintKey(e.target.value)}
                      placeholder="key (e.g. ram_gb)"
                      className="flex-1 text-xs p-2 rounded-lg border border-slopes/40 bg-white focus:outline-none"
                    />
                    <select
                      value={newConstraintOp}
                      onChange={(e) => setNewConstraintOp(e.target.value)}
                      className="text-xs p-2 rounded-lg border border-slopes/40 bg-white focus:outline-none"
                    >
                      <option value="gte">&gt;= (at least)</option>
                      <option value="lte">&lt;= (at most)</option>
                      <option value="eq">= (exact)</option>
                    </select>
                    <input
                      type="text"
                      value={newConstraintVal}
                      onChange={(e) => setNewConstraintVal(e.target.value)}
                      placeholder="value (e.g. 16)"
                      className="w-24 text-xs p-2 rounded-lg border border-slopes/40 bg-white focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={handleAddConstraint}
                      className="py-1 px-3 bg-white border border-slopes/40 hover:bg-arctic-soft rounded-lg text-xs font-bold text-midnight transition-all"
                    >
                      + Add
                    </button>
                  </div>

                  {constraints.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {constraints.map((c, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-indigo-50 border border-indigo-200 text-indigo-800 font-semibold"
                        >
                          {c.key} {c.operator === 'gte' ? '≥' : c.operator === 'lte' ? '≤' : '='} {String(c.value)}
                          <button
                            type="button"
                            onClick={() => handleRemoveConstraint(i)}
                            className="text-indigo-400 hover:text-indigo-900 ml-1 font-bold"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-apres mb-1">Simulation Label / Hypothesis</label>
                  <input
                    type="text"
                    value={simLabel}
                    onChange={(e) => setSimLabel(e.target.value)}
                    placeholder="e.g. Test higher budget for 32GB RAM"
                    className="w-full text-xs p-2.5 rounded-lg border border-slopes/40 bg-white focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <button
                  type="submit"
                  disabled={isSimulating}
                  className="w-full py-2.5 bg-midnight hover:bg-mountainside text-white font-bold rounded-xl text-xs transition-all shadow-xs flex items-center justify-center gap-2"
                >
                  {isSimulating ? (
                    <>
                      <div className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Running Simulation Engine...
                    </>
                  ) : (
                    '🚀 Run What-If Simulation'
                  )}
                </button>
              </form>

              {/* Simulation Result Box */}
              {simError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs font-semibold">
                  {simError}
                </div>
              )}

              {activeSimulation && (
                <div className="bg-indigo-50/40 border border-indigo-200 rounded-xl p-4 space-y-3.5 animate-in fade-in">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="px-2 py-0.5 rounded bg-indigo-100 border border-indigo-300 text-indigo-900 text-[10px] font-bold">
                        Simulation #{activeSimulation.simulation_number} Branch
                      </span>
                      <h4 className="text-sm font-bold text-midnight mt-1">{activeSimulation.label}</h4>
                    </div>
                    <span className="text-[11px] font-mono text-apres font-bold">
                      {activeSimulation.simulation_id}
                    </span>
                  </div>

                  {/* Simulated Product Card */}
                  {activeSimulation.result?.simulated_product ? (
                    <div className="bg-white border border-indigo-100 rounded-xl p-3 flex items-center justify-between">
                      <div>
                        <span className="text-[10px] font-bold text-indigo-700 uppercase">Simulated Recommendation</span>
                        <h5 className="text-xs font-bold text-midnight mt-0.5">
                          {activeSimulation.result.simulated_product.name}
                        </h5>
                        <p className="text-xs font-extrabold text-midnight mt-0.5">
                          {formatCurrency(activeSimulation.result.simulated_product.price)}
                        </p>
                      </div>
                      <div className="text-right">
                        <span className="text-lg font-black text-indigo-600">
                          {activeSimulation.result.simulated_product.match_percentage ?? 100}%
                        </span>
                        <span className="text-[10px] text-apres block">Fit Score</span>
                      </div>
                    </div>
                  ) : (
                    <div className="p-3 bg-white border border-slopes/20 rounded-xl text-center text-xs text-apres">
                      No matching products found under these modified constraints.
                    </div>
                  )}

                  {/* Changes Summary */}
                  {activeSimulation.result?.changes && activeSimulation.result.changes.length > 0 && (
                    <div>
                      <span className="text-[11px] font-bold text-midnight uppercase tracking-wider block mb-1">
                        Impact & Changes from Original:
                      </span>
                      <ul className="space-y-1">
                        {activeSimulation.result.changes.map((ch, idx) => (
                          <li key={idx} className="text-xs text-mountainside flex items-center gap-1.5">
                            <span className="text-indigo-500 font-bold">→</span>
                            <span>{ch}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Contract Warnings */}
                  {activeSimulation.contract_warnings && activeSimulation.contract_warnings.length > 0 && (
                    <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl">
                      <span className="text-[11px] font-bold text-amber-800 flex items-center gap-1">
                        <span>⚠️</span> Contract Warning
                      </span>
                      <ul className="mt-1 space-y-0.5">
                        {activeSimulation.contract_warnings.map((w, idx) => (
                          <li key={idx} className="text-xs text-amber-900">
                            • {w}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Apply Actions */}
                  {applySuccessMessage && (
                    <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-xs font-bold">
                      ✅ {applySuccessMessage}
                    </div>
                  )}
                  {applyErrorMessage && (
                    <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 text-xs font-bold">
                      ⛔ {applyErrorMessage}
                    </div>
                  )}

                  {activeSimulation.result?.simulated_product && (
                    <button
                      onClick={() => handleApply(activeSimulation.simulation_id)}
                      disabled={isApplying || activeSimulation.status === 'APPLIED'}
                      className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-emerald-600 text-white font-bold text-xs rounded-xl transition-all shadow-xs"
                    >
                      {activeSimulation.status === 'APPLIED'
                        ? '✓ Simulation Already Applied'
                        : isApplying
                        ? 'Applying Recommendation...'
                        : '✨ Use This Recommendation (Apply to Session)'}
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB 4: SIMULATION HISTORY */}
          {activeTab === 'history' && (
            <div className="space-y-4">
              {isHistoryLoading ? (
                <div className="py-12 text-center text-apres">
                  <div className="inline-block h-8 w-8 border-3 border-slopes border-t-midnight rounded-full animate-spin mb-3" />
                  <p className="text-xs font-semibold">Loading simulation branches...</p>
                </div>
              ) : historyError ? (
                <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-center text-rose-700 text-xs">
                  <p className="font-bold">{historyError}</p>
                </div>
              ) : simulations.length > 0 ? (
                <div className="space-y-3">
                  <p className="text-xs text-apres font-medium">
                    Branch history preserved for decision trace <strong className="text-midnight">{decisionId}</strong>.
                  </p>
                  <div className="space-y-3">
                    {simulations.map((s) => (
                      <div
                        key={s.simulation_id}
                        className="bg-arctic-soft/40 border border-slopes/30 rounded-xl p-4 space-y-2.5"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 bg-midnight text-white text-[10px] font-mono font-bold rounded">
                              #{s.simulation_number}
                            </span>
                            <h4 className="font-bold text-midnight text-xs">{s.label}</h4>
                          </div>
                          <span
                            className={`px-2 py-0.5 text-[10px] font-bold rounded-md border ${
                              s.status === 'APPLIED'
                                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                                : 'bg-arctic border-slopes/40 text-apres'
                            }`}
                          >
                            {s.status}
                          </span>
                        </div>

                        {s.result_summary?.simulated_product && (
                          <div className="text-xs text-mountainside">
                            Simulated Pick:{' '}
                            <strong className="text-midnight">{s.result_summary.simulated_product.name}</strong>{' '}
                            ({formatCurrency(s.result_summary.simulated_product.price)})
                          </div>
                        )}

                        {s.result_summary?.changes && s.result_summary.changes.length > 0 && (
                          <div className="text-[11px] text-apres">
                            {s.result_summary.changes.slice(0, 2).join(' · ')}
                          </div>
                        )}

                        {s.status !== 'APPLIED' && (
                          <div className="pt-2 border-t border-slopes/20 flex justify-end">
                            <button
                              onClick={() => handleApply(s.simulation_id)}
                              disabled={isApplying}
                              className="py-1 px-3 bg-white border border-slopes/40 hover:bg-arctic-soft text-midnight font-bold text-xs rounded-lg transition-all"
                            >
                              Apply This Simulation
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="py-12 text-center text-apres">
                  <div className="w-14 h-14 bg-arctic-soft rounded-2xl flex items-center justify-center mx-auto mb-3 text-2xl border border-slopes/25">
                    📜
                  </div>
                  <p className="font-bold text-midnight text-sm">No active AI decision yet</p>
                  <p className="text-xs text-apres mt-1">Run the Buyer Agent or AI Assistant to create a decision trace.</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slopes/25 bg-arctic-soft/30 flex-shrink-0 flex items-center justify-between">
          <span className="text-[11px] text-apres">
            Original trace remains completely immutable.
          </span>
          <button
            onClick={onClose}
            className="py-2 px-5 bg-white border border-slopes/35 text-mountainside font-semibold rounded-xl hover:bg-arctic-soft text-xs transition-all"
          >
            Close Decision Lab
          </button>
        </div>
      </div>
    </div>
  );
}
