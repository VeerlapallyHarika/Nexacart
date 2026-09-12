'use client';

import { useState } from 'react';
import { CommerceContract, ContractStatus } from '@/lib/types';

interface AICommerceContractPanelProps {
  contract: CommerceContract | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (payload: Partial<CommerceContract>) => Promise<void>;
  onActivate: () => Promise<void>;
  onCancel: () => Promise<void>;
  isBusy: boolean;
  error?: string | null;
}

const STATUS_BADGE: Record<string, string> = {
  ACTIVE: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  DRAFT: 'bg-amber-50 text-amber-800 border-amber-200',
  COMPLETED: 'bg-arctic-soft text-mountainside border-slopes/30',
  CANCELLED: 'bg-rose-50 text-rose-800 border-rose-200',
};

const DISPLAY_ACTIONS: Record<string, string> = {
  search_products: 'Search Products',
  get_product_details: 'View Specs',
  compare_products: 'Compare Items',
  recommend_product: 'Recommend',
  add_to_cart: 'Add to Cart',
  view_cart: 'Inspect Cart',
};

export default function AICommerceContractPanel({
  contract,
  isOpen,
  onClose,
  onSave,
  onActivate,
  onCancel,
  isBusy,
  error,
}: AICommerceContractPanelProps) {
  const [budget, setBudget] = useState<string>(contract?.max_budget?.toString() ?? '');
  const [category, setCategory] = useState<string>(
    (contract?.required_categories ?? []).join(', ')
  );
  const [battery, setBattery] = useState<string>(
    contract?.minimum_battery_hours?.toString() ?? ''
  );

  if (!isOpen) return null;

  const status: ContractStatus = contract?.status ?? 'DRAFT';
  const isActive = status === 'ACTIVE';
  const isDisabled = isBusy;

  const handleSave = async () => {
    let batteryVal: number | undefined = undefined;
    if (battery.trim() !== '') {
      const parsed = parseInt(battery, 10);
      if (!isNaN(parsed) && parsed >= 0) {
        batteryVal = parsed;
      }
    }

    await onSave({
      goal: contract?.goal ?? 'Verified AI-native shopping session',
      max_budget: budget ? Math.max(0, parseFloat(budget)) : undefined,
      currency: 'INR',
      required_categories: category
        ? category.split(',').map((c) => c.trim().toLowerCase()).filter(Boolean)
        : [],
      minimum_battery_hours: batteryVal,
      excluded_conditions: ['refurbished'],
      allowed_actions: [
        'search_products',
        'get_product_details',
        'compare_products',
        'recommend_product',
        'add_to_cart',
        'view_cart',
      ],
    });
  };

  const handleActivate = async () => {
    await handleSave();
    await onActivate();
  };

  return (
    <div className="fixed inset-0 bg-midnight/70 backdrop-blur-xs z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slopes/40 w-full max-w-md max-h-[90vh] flex flex-col overflow-y-auto animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="sticky top-0 bg-arctic-soft/50 flex items-center justify-between p-5 border-b border-slopes/25 flex-shrink-0 z-10">
          <div className="flex items-center gap-2.5">
            <span className="text-xl">🛡️</span>
            <div>
              <h2 className="text-base font-bold text-midnight tracking-tight">AI Commerce Contract</h2>
              <p className="text-xs text-apres">Deterministic safety boundaries</p>
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

        <div className="p-5 space-y-5">
          {/* Status banner */}
          <div className={`rounded-xl p-3.5 border ${isActive ? 'bg-emerald-50/70 border-emerald-200' : 'bg-arctic-soft border-slopes/35'}`}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-midnight uppercase tracking-wider">Contract Status</span>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${STATUS_BADGE[status]}`}>{status}</span>
            </div>
            {isActive && (
              <p className="text-xs text-emerald-800 mt-1.5 font-medium">
                Active: The backend is actively enforcing these rules on all agent actions.
              </p>
            )}
            {!isActive && (
              <p className="text-xs text-apres mt-1.5 font-medium">
                Configure your rules below and activate to enforce deterministic limits.
              </p>
            )}
          </div>

          {error && (
            <div className="rounded-xl p-3.5 bg-rose-50 border border-rose-200 text-xs text-rose-700 font-medium">
              {error}
            </div>
          )}

          {/* Budget / requirements editing */}
          <div className="space-y-3.5">
            <div>
              <label className="block text-xs font-semibold text-midnight uppercase tracking-wider mb-1.5">
                Maximum Budget Limit (₹)
              </label>
              <input
                type="number"
                min={0}
                value={budget}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === '' || parseFloat(val) >= 0) {
                    setBudget(val);
                  }
                }}
                disabled={isDisabled}
                placeholder="e.g. 50000"
                className="w-full px-3.5 py-2.5 bg-arctic-soft/40 border border-slopes/40 rounded-xl text-sm text-midnight placeholder:text-apres/60 focus:outline-none focus:ring-2 focus:ring-midnight disabled:bg-slopes/20 transition-all"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-midnight uppercase tracking-wider mb-1.5">
                Required Category (e.g. laptops, headphones)
              </label>
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={isDisabled}
                placeholder="e.g. smartphones"
                className="w-full px-3.5 py-2.5 bg-arctic-soft/40 border border-slopes/40 rounded-xl text-sm text-midnight placeholder:text-apres/60 focus:outline-none focus:ring-2 focus:ring-midnight disabled:bg-slopes/20 transition-all"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-midnight uppercase tracking-wider mb-1.5">
                Minimum Battery Life (hours)
              </label>
              <input
                type="number"
                min={0}
                value={battery}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === '' || parseInt(val, 10) >= 0) {
                    setBattery(val);
                  }
                }}
                disabled={isDisabled}
                placeholder="e.g. 30"
                className="w-full px-3.5 py-2.5 bg-arctic-soft/40 border border-slopes/40 rounded-xl text-sm text-midnight placeholder:text-apres/60 focus:outline-none focus:ring-2 focus:ring-midnight disabled:bg-slopes/20 transition-all"
              />
            </div>
          </div>

          {/* Summary display */}
          {(contract?.max_budget || contract?.minimum_battery_hours || (contract?.required_categories ?? []).length > 0) && (
            <div className="bg-arctic-soft/70 border border-slopes/35 rounded-xl p-4 space-y-2 text-xs">
              <p className="font-bold text-midnight uppercase tracking-wider mb-2">Active Rules Summary</p>
              {contract?.max_budget != null && (
                <div className="flex justify-between">
                  <span className="text-apres">Budget Ceiling:</span>
                  <span className="font-bold text-midnight">₹{contract.max_budget.toLocaleString('en-IN')}</span>
                </div>
              )}
              {(contract?.required_categories ?? []).length > 0 && (
                <div className="flex justify-between">
                  <span className="text-apres">Category Lock:</span>
                  <span className="font-bold text-midnight">{(contract?.required_categories ?? []).join(', ')}</span>
                </div>
              )}
              {contract?.minimum_battery_hours != null && (
                <div className="flex justify-between">
                  <span className="text-apres">Min Battery:</span>
                  <span className="font-bold text-midnight">≥ {contract.minimum_battery_hours} hrs</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-apres">Condition:</span>
                <span className="font-semibold text-midnight">New Only (No Refurbished)</span>
              </div>
            </div>
          )}

          {/* Permissions */}
          <div className="bg-arctic-soft border border-slopes/40 rounded-xl p-4 text-xs">
            <p className="font-bold text-midnight uppercase tracking-wider mb-2.5">Enforced Guardrails</p>
            <div className="flex flex-wrap gap-1.5 mb-3">
              {(contract?.allowed_actions ?? []).map((action) => (
                <span key={action} className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-white text-mountainside border border-slopes/30 shadow-2xs">
                  ✓ {DISPLAY_ACTIONS[action] || action}
                </span>
              ))}
            </div>
            <p className="text-apres mt-2 flex items-center gap-1.5">
              <span>🔒</span> Agent cannot exceed specified budget or bypass stock checks.
            </p>
            <p className="text-apres mt-1 flex items-center gap-1.5">
              <span>🔒</span> Agent cannot execute checkout without user authorization.
            </p>
          </div>

          {/* Actions */}
          <div className="space-y-2.5 pt-2 border-t border-slopes/20">
            {!isActive && (
              <>
                <button
                  onClick={handleActivate}
                  disabled={isBusy}
                  className="w-full py-3.5 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-xs disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm hover:scale-[1.01]"
                >
                  {isBusy ? 'Activating...' : '🚀 Activate AI Contract'}
                </button>
                <button
                  onClick={handleSave}
                  disabled={isBusy}
                  className="w-full py-3 px-4 bg-arctic-soft border border-slopes/40 text-mountainside font-semibold rounded-xl hover:bg-arctic text-xs transition-all"
                >
                  {isBusy ? 'Saving...' : 'Save Draft'}
                </button>
              </>
            )}

            {isActive && (
              <>
                <button
                  onClick={handleSave}
                  disabled={isBusy}
                  className="w-full py-3.5 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-xs disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm hover:scale-[1.01]"
                >
                  {isBusy ? 'Saving...' : 'Update Contract Rules'}
                </button>
                <button
                  onClick={onCancel}
                  disabled={isBusy}
                  className="w-full py-3 px-4 bg-rose-50 text-rose-700 border border-rose-200 font-semibold rounded-xl hover:bg-rose-100 text-xs transition-all"
                >
                  Cancel Contract
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
