'use client';

import { useState } from 'react';
import {
  DecisionTraceData,
  DecisionTraceEvent,
  TraceStatus,
  TraceActor,
  TraceEventStatus,
} from '@/lib/types';

interface DecisionTracePanelProps {
  trace: DecisionTraceData | null;
  isLoading: boolean;
  isOpen: boolean;
  error: string | null;
  onClose: () => void;
  onOpenReplay: () => void;
}

const STATUS_META: Record<TraceStatus, { label: string; icon: string; classes: string }> = {
  COMPLETED: { label: 'Purchase Complete', icon: '🎉', classes: 'bg-emerald-50 border-emerald-200 text-emerald-800' },
  INTERRUPTED: { label: 'Interrupted — resumable', icon: '⏸️', classes: 'bg-amber-50 border-amber-200 text-amber-800' },
  FAILED: { label: 'Failed', icon: '⛔', classes: 'bg-rose-50 border-rose-200 text-rose-800' },
  IN_PROGRESS: { label: 'In Progress', icon: '⏳', classes: 'bg-amber-50 border-amber-200 text-amber-800' },
};

const ACTOR_META: Record<TraceActor, { label: string; icon: string; classes: string }> = {
  ai: { label: 'AI', icon: '🤖', classes: 'bg-indigo-50 border-indigo-200 text-indigo-700' },
  user: { label: 'You', icon: '👤', classes: 'bg-emerald-50 border-emerald-200 text-emerald-700' },
  system: { label: 'System', icon: '⚙️', classes: 'bg-arctic-soft border-slopes/40 text-mountainside' },
};

const EVENT_STATUS_CLASSES: Record<TraceEventStatus, { badge: string; node: string }> = {
  SUCCESS: { badge: 'bg-emerald-50 border-emerald-200 text-emerald-700', node: 'bg-emerald-100 border-emerald-300 text-emerald-700' },
  PENDING: { badge: 'bg-amber-50 border-amber-200 text-amber-700', node: 'bg-amber-100 border-amber-300 text-amber-700' },
  WARNING: { badge: 'bg-amber-50 border-amber-200 text-amber-700', node: 'bg-amber-100 border-amber-300 text-amber-700' },
  ERROR: { badge: 'bg-rose-50 border-rose-200 text-rose-700', node: 'bg-rose-100 border-rose-300 text-rose-700' },
};

const EVENT_ICON: Record<string, string> = {
  USER_MESSAGE: '💬',
  INTENT_EXTRACTED: '🧠',
  BUYER_GOAL_UNDERSTOOD: '🧠',
  BUYER_AGENT_STEP: '🤖',
  BUYER_AGENT_ERROR: '🛑',
  PRODUCT_RECOMMENDED: '⭐',
  PRODUCT_REJECTED_BY_CONTRACT: '🚫',
  PRODUCT_ADDED_TO_CART: '🛒',
  CONTRACT_CREATED: '🛡️',
  CONTRACT_UPDATED: '🛡️',
  CONTRACT_ACTIVATED: '🛡️',
  CONTRACT_CHECK: '✅',
  CONTRACT_VIOLATION: '🚫',
  CONTRACT_ACTION_BLOCKED: '🛡️',
  CART_ITEM_UPDATED: '🛒',
  CART_VERIFIED: '✔️',
  CHECKOUT_APPROVAL_REQUESTED: '👤',
  USER_APPROVED_CHECKOUT: '👤',
  PAYMENT_CREATED: '💳',
  PAYMENT_RESUMED: '💳',
  PAYMENT_PROCESSING: '⏳',
  PAYMENT_SUCCESS: '💰',
  PAYMENT_VERIFIED: '💰',
  PAYMENT_FAILED: '❌',
  PAYMENT_CANCELLED: '⏹️',
  ORDER_CREATED: '📦',
  ORDER_CONFIRMED: '📦',
  PURCHASE_COMPLETED: '🎉',
};

function formatExplanation(event: DecisionTraceEvent): string {
  const e = event.explanation;
  if (!e) return '';
  const lines: string[] = [];

  if (e.type === 'recommendation') {
    if (Array.isArray(e.strong_matches) && e.strong_matches.length)
      lines.push(`Why it fits: ${e.strong_matches.join(' · ')}`);
    if (Array.isArray(e.trade_offs) && e.trade_offs.length)
      lines.push(`Trade-offs: ${e.trade_offs.join(' · ')}`);
  } else if (e.type === 'contract_check' && e.passed) {
    lines.push(`Checked: ${(e.checked_fields ?? []).join(', ')}`);
  } else if (e.type === 'contract_block') {
    const v = (e.violations ?? []) as string[];
    if (v.length) lines.push(`Violations: ${v.join(' · ')}`);
  } else if (e.type === 'intent') {
    if (e.category) lines.push(`Category: ${e.category}`);
    if (e.max_price != null) lines.push(`Budget: up to ₹${Number(e.max_price).toLocaleString('en-IN')}`);
  } else if (e.type === 'discovery') {
    if (e.product_count != null) lines.push(`Candidates found: ${e.product_count}`);
  } else if (e.type === 'payment') {
    if (e.amount != null) lines.push(`Amount: ₹${Number(e.amount).toLocaleString('en-IN')}`);
    if (e.status) lines.push(`Status: ${e.status}`);
  } else if (e.type === 'order') {
    if (e.order_id) lines.push(`Order ID: ${e.order_id}`);
  } else if (e.type === 'selection') {
    if (e.product_name) lines.push(`Selected: ${e.product_name}`);
  } else if (e.type === 'agent_goal') {
    if (e.category) lines.push(`Category: ${e.category}`);
    if (e.max_price != null) lines.push(`Budget: up to ₹${Number(e.max_price).toLocaleString('en-IN')}`);
    if (e.active_contract) lines.push('Active AI Commerce Contract in effect');
  }

  // Fall back to raw JSON for anything not explicitly modelled so no details are hidden.
  if (lines.length === 0) {
    try {
      return JSON.stringify(e, null, 2);
    } catch {
      return '';
    }
  }
  return lines.join('\n');
}

function DecisionEventRow({ event }: { event: DecisionTraceEvent }) {
  const [open, setOpen] = useState(false);
  const actorMeta = ACTOR_META[event.actor] ?? ACTOR_META.system;
  const statusMeta = EVENT_STATUS_CLASSES[event.status] ?? EVENT_STATUS_CLASSES.SUCCESS;
  const explanation = formatExplanation(event);
  const hasDetails = Boolean(explanation) || (event.explanation && Object.keys(event.explanation).length > 0);
  const icon = EVENT_ICON[event.event_type] ?? '•';

  return (
    <div className="relative pl-9">
      <span
        className={`absolute left-0 top-1.5 flex items-center justify-center w-7 h-7 rounded-xl border text-xs ${statusMeta.node}`}
      >
        {icon}
      </span>
      <div className="ml-1 bg-arctic-soft/50 border border-slopes/25 rounded-xl p-3.5">
        <div className="flex items-center justify-between gap-2">
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[10px] font-bold ${actorMeta.classes}`}
          >
            <span>{actorMeta.icon}</span>
            {actorMeta.label}
          </span>
          <span
            className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-bold border ${statusMeta.badge}`}
          >
            {event.status}
          </span>
        </div>
        <p className="font-bold text-midnight text-xs mt-1.5">{event.title}</p>
        <p className="text-xs mt-0.5 leading-relaxed text-apres whitespace-pre-line">
          {event.summary}
        </p>

        {hasDetails && open && (
          <div className="mt-2 pt-2 border-t border-slopes/20">
            <p className="text-[10px] font-bold text-apres uppercase tracking-wider mb-1">
              Technical details
            </p>
            <pre className="text-[11px] leading-relaxed text-mountainside bg-white border border-slopes/20 rounded-lg p-2.5 font-mono whitespace-pre-wrap break-words">
              {explanation}
            </pre>
          </div>
        )}

        {hasDetails && (
          <button
            onClick={() => setOpen((o) => !o)}
            className="mt-2 text-[11px] font-semibold text-mountainside hover:text-midnight underline underline-offset-2"
          >
            {open ? 'Hide technical details' : 'Show technical details'}
          </button>
        )}
      </div>
    </div>
  );
}

export default function DecisionTracePanel({
  trace,
  isLoading,
  isOpen,
  error,
  onClose,
  onOpenReplay,
}: DecisionTracePanelProps) {
  if (!isOpen) return null;

  const status = trace?.status ?? 'IN_PROGRESS';
  const statusMeta = STATUS_META[status];
  const events = trace?.events ?? [];

  return (
    <div className="fixed inset-0 bg-midnight/70 backdrop-blur-xs z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slopes/40 w-full max-w-lg max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-5 border-b border-slopes/25 bg-arctic-soft/40 flex-shrink-0">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <span className="text-xl">🧭</span>
              <div>
                <h2 className="text-base font-bold text-midnight tracking-tight">Commerce Decision Trace</h2>
                <p className="text-xs text-apres">One explainable journey across every AI commerce system</p>
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

          {trace && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              <span className="px-2.5 py-1 rounded-lg border border-mountainside/40 bg-midnight text-arctic font-mono text-xs font-bold">
                {trace.decision_id}
              </span>
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[10px] font-bold ${statusMeta.classes}`}
              >
                {statusMeta.icon} {statusMeta.label}
              </span>
            </div>
          )}

          {trace?.goal && (
            <p className="mt-2.5 text-xs text-midnight font-medium leading-relaxed">
              <span className="font-bold text-apres uppercase tracking-wider text-[10px]">Goal · </span>
              {trace.goal}
            </p>
          )}
          {trace && (
            <p className="mt-1 text-xs text-apres">{trace.summary}</p>
          )}
        </div>

        {isLoading ? (
          <div className="flex-1 flex items-center justify-center p-12">
            <div className="text-center text-apres">
              <div className="inline-block h-8 w-8 border-3 border-slopes border-t-midnight rounded-full animate-spin mb-3" />
              <p className="text-xs font-semibold">Loading decision trace...</p>
            </div>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-rose-700">
            <p className="font-bold text-sm">Could not load decision trace</p>
            <p className="text-xs text-apres mt-1">{error}</p>
          </div>
        ) : trace && events.length === 0 ? (
          <div className="p-10 text-center text-apres">
            <div className="w-14 h-14 bg-arctic-soft rounded-2xl flex items-center justify-center mx-auto mb-3 text-2xl border border-slopes/25">
              🧭
            </div>
            <p className="font-bold text-midnight text-sm">No decision steps recorded yet</p>
            <p className="text-xs text-apres mt-1">Start a conversation or run the buyer agent to build the trace.</p>
          </div>
        ) : trace ? (
          <>
            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
              {events.map((event, i) => (
                <div key={event.ref_audit_event_id ?? i} className="relative">
                  {i < events.length - 1 && (
                    <span className="absolute left-[13px] top-8 bottom-[-16px] w-0.5 bg-slopes/30" />
                  )}
                  <DecisionEventRow event={event} />
                </div>
              ))}
            </div>

            <div className="border-t border-slopes/25 p-5 bg-arctic-soft/30 flex-shrink-0 space-y-2.5">
              <button
                onClick={onOpenReplay}
                className="w-full py-3 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-xs transition-all shadow-sm hover:scale-[1.01]"
              >
                🎬 View Purchase Replay
              </button>
              <button
                onClick={onClose}
                className="w-full py-2.5 px-3 bg-white border border-slopes/35 text-mountainside font-semibold rounded-xl hover:bg-arctic-soft text-xs transition-all"
              >
                Close
              </button>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
