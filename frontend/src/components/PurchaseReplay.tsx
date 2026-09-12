'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { PurchaseReplayData, ReplayStatus, ReplayStepType } from '@/lib/types';

interface PurchaseReplayProps {
  replay: PurchaseReplayData | null;
  isLoading: boolean;
  isOpen: boolean;
  onClose: () => void;
  error: string | null;
}

const STEP_ICONS: Record<ReplayStepType, string> = {
  INTENT: '💬',
  DISCOVERY: '🔍',
  CONTRACT_CREATED: '🛡️',
  CONTRACT_CHECK: '✅',
  CONTRACT_VIOLATION: '🚫',
  COMPARISON: '⚖️',
  DECISION: '🎯',
  CART_ADD: '🛒',
  CART_UPDATE: '🔄',
  CART_VERIFIED: '✔️',
  CHECKOUT_APPROVAL: '👤',
  PAYMENT_INITIATED: '💳',
  PAYMENT_CONFIRMED: '💰',
  ORDER_CONFIRMED: '📦',
  PURCHASE_COMPLETE: '🎉',
  AGENT_GOAL: '🧠',
  AGENT_RECOMMENDATION: '⭐',
};

const STATUS_META: Record<ReplayStatus, { label: string; icon: string; classes: string }> = {
  COMPLETED: { label: 'Purchase Complete', icon: '🎉', classes: 'bg-emerald-50 border-emerald-200 text-emerald-800' },
  BLOCKED: { label: 'Blocked by Safety Contract', icon: '🛡️', classes: 'bg-rose-50 border-rose-200 text-rose-800' },
  CANCELLED: { label: 'Cancelled Session', icon: '⏹️', classes: 'bg-arctic-soft border-slopes/30 text-mountainside' },
  IN_PROGRESS: { label: 'Session in Progress', icon: '⏳', classes: 'bg-amber-50 border-amber-200 text-amber-800' },
};

export default function PurchaseReplay({
  replay,
  isLoading,
  isOpen,
  onClose,
  error,
}: PurchaseReplayProps) {
  const [visibleCount, setVisibleCount] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const bodyRef = useRef<HTMLDivElement>(null);

  const total = replay?.steps.length ?? 0;

  useEffect(() => {
    if (isOpen && replay) {
      setVisibleCount(0);
      setCurrentIndex(0);
      setIsPlaying(false);
    }
  }, [isOpen, replay]);

  const autoPlay = useCallback(() => {
    if (!total) return;
    setIsPlaying(true);
    setVisibleCount(0);
    setCurrentIndex(0);
  }, [total]);

  useEffect(() => {
    if (!isPlaying || !total) return;
    if (currentIndex >= total) {
      setIsPlaying(false);
      return;
    }
    const timer = setTimeout(() => {
      setVisibleCount(currentIndex + 1);
      setCurrentIndex((i) => i + 1);
    }, 700);
    return () => clearTimeout(timer);
  }, [isPlaying, currentIndex, total]);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [visibleCount]);

  if (!isOpen) return null;

  const status = replay?.status ?? 'IN_PROGRESS';
  const statusMeta = STATUS_META[status];
  const visibleSteps = (replay?.steps ?? []).slice(0, isPlaying ? visibleCount : total);

  const goTo = (i: number) => {
    setIsPlaying(false);
    setCurrentIndex(i);
    setVisibleCount(i + 1);
  };

  return (
    <div className="fixed inset-0 bg-midnight/70 backdrop-blur-xs z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slopes/40 w-full max-w-lg max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slopes/25 bg-arctic-soft/40 flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <span className="text-xl">🎬</span>
            <div>
              <h2 className="text-base font-bold text-midnight tracking-tight">Purchase Replay</h2>
              <p className="text-xs text-apres">Step-by-step audit of AI decision journey</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-arctic text-apres hover:text-midnight rounded-xl transition-all border border-transparent hover:border-slopes/30"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {isLoading ? (
          <div className="flex-1 flex items-center justify-center p-12">
            <div className="text-center text-apres">
              <div className="inline-block h-8 w-8 border-3 border-slopes border-t-midnight rounded-full animate-spin mb-3" />
              <p className="text-xs font-semibold">Loading purchase audit trail...</p>
            </div>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-rose-700">
            <p className="font-bold text-sm">Could not load replay</p>
            <p className="text-xs text-apres mt-1">{error}</p>
          </div>
        ) : replay && total === 0 ? (
          <div className="p-10 text-center text-apres">
            <div className="w-14 h-14 bg-arctic-soft rounded-2xl flex items-center justify-center mx-auto mb-3 text-2xl border border-slopes/25">
              🎬
            </div>
            <p className="font-bold text-midnight text-sm">No journey steps recorded yet</p>
            <p className="text-xs text-apres mt-1">Start a conversation and browse products to generate events.</p>
          </div>
        ) : replay ? (
          <>
            {/* Status banner */}
            <div className="px-5 pt-5">
              <div className={`flex items-center gap-3 rounded-xl p-3.5 border ${statusMeta.classes}`}>
                <span className="text-xl">{statusMeta.icon}</span>
                <div>
                  <p className="font-bold text-xs uppercase tracking-wider">{statusMeta.label}</p>
                  <p className="text-[11px] opacity-85 mt-0.5">
                    {total} step{total === 1 ? '' : 's'} recorded · Session <span className="font-mono">{replay.session_id.substring(0, 16)}</span>
                  </p>
                </div>
              </div>
            </div>

            {/* Timeline */}
            <div ref={bodyRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
              {visibleSteps.map((step, i) => (
                <div key={step.step} className="relative pl-9">
                  {/* Connecting line */}
                  {i < visibleSteps.length - 1 && (
                    <span className="absolute left-[13px] top-7 bottom-[-16px] w-0.5 bg-slopes/30" />
                  )}
                  {/* Node */}
                  <span
                    className={`absolute left-0 top-0 flex items-center justify-center w-7 h-7 rounded-xl border text-xs shadow-2xs ${
                      step.status === 'BLOCKED'
                        ? 'bg-rose-50 border-rose-400 text-rose-700'
                        : 'bg-midnight border-mountainside text-white'
                    }`}
                  >
                    {STEP_ICONS[step.type] ?? '•'}
                  </span>
                  <div className="ml-1 bg-arctic-soft/50 border border-slopes/25 rounded-xl p-3.5">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[10px] font-bold text-apres uppercase tracking-wider">
                        Step {step.step}
                      </p>
                      <span
                        className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-bold border ${
                          step.status === 'BLOCKED'
                            ? 'bg-rose-50 border-rose-200 text-rose-700'
                            : 'bg-emerald-50 border-emerald-200 text-emerald-700'
                        }`}
                      >
                        {step.status === 'BLOCKED' ? 'Blocked' : 'Verified'}
                      </span>
                    </div>
                    <p className="font-bold text-midnight text-xs mt-1">
                      {step.title}
                    </p>
                    <p
                      className={`text-xs mt-1 leading-relaxed ${
                        step.status === 'BLOCKED' ? 'text-rose-700 font-medium' : 'text-apres'
                      }`}
                    >
                      {step.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            {/* Controls */}
            <div className="border-t border-slopes/25 p-5 bg-arctic-soft/30 flex-shrink-0 space-y-3">
              {!isPlaying && visibleCount < total && (
                <button
                  onClick={autoPlay}
                  className="w-full py-3 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-xs transition-all shadow-sm hover:scale-[1.01]"
                >
                  ▶ Auto-Play Journey
                </button>
              )}

              <div className="flex items-center gap-2">
                <button
                  onClick={() => goTo(Math.max(0, currentIndex - 1))}
                  disabled={currentIndex <= 0}
                  className="flex-1 py-2 px-3 bg-white border border-slopes/35 text-mountainside font-semibold rounded-xl hover:bg-arctic-soft disabled:opacity-40 text-xs transition-all"
                >
                  ← Previous Step
                </button>
                <button
                  onClick={() => goTo(Math.min(total - 1, currentIndex + 1))}
                  disabled={currentIndex >= total - 1}
                  className="flex-1 py-2 px-3 bg-white border border-slopes/35 text-mountainside font-semibold rounded-xl hover:bg-arctic-soft disabled:opacity-40 text-xs transition-all"
                >
                  Next Step →
                </button>
              </div>

              {replay.status === 'BLOCKED' && (
                <p className="text-[11px] text-rose-600 text-center font-medium">
                  This journey was securely halted to prevent contract budget / category violation.
                </p>
              )}
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
