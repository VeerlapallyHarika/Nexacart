'use client';

import { Cart, CartItem } from '@/lib/types';

interface CheckoutSummaryProps {
  cart: Cart;
  onApprove: () => void;
  onCancel: () => void;
  isApproving: boolean;
}

export default function CheckoutSummary({
  cart,
  onApprove,
  onCancel,
  isApproving,
}: CheckoutSummaryProps) {
  const items = cart?.items || [];
  const total = cart?.total || 0;
  const isAwaitingApproval = cart?.status === 'AWAITING_APPROVAL';

  if (!isAwaitingApproval) return null;

  return (
    <div className="bg-white border border-slopes/40 rounded-2xl p-6 my-4 shadow-sm text-midnight">
      <div className="flex items-center gap-3.5 mb-5 pb-4 border-b border-slopes/20">
        <div className="w-10 h-10 bg-midnight text-white rounded-xl flex items-center justify-center text-lg shadow-2xs">
          📋
        </div>
        <div>
          <h3 className="font-bold text-midnight text-base">Order Authorization</h3>
          <p className="text-xs text-apres">Please review item specs and total before authorization</p>
        </div>
      </div>

      <div className="space-y-3 mb-5">
        {items.map((item: CartItem) => (
          <div key={item.id} className="flex justify-between items-center bg-arctic-soft/40 border border-slopes/20 rounded-xl p-3 text-xs">
            <div className="flex-1">
              <p className="font-bold text-midnight text-sm">{item.product_name}</p>
              <p className="text-apres mt-0.5">
                ₹{item.price.toLocaleString('en-IN')} × {item.quantity}
              </p>
            </div>
            <p className="font-extrabold text-midnight text-sm">
              ₹{item.subtotal.toLocaleString('en-IN')}
            </p>
          </div>
        ))}
      </div>

      <div className="border-t border-slopes/20 pt-4 mb-5">
        <div className="flex justify-between items-center">
          <span className="text-xs font-semibold text-apres uppercase tracking-wider">Authorized Total</span>
          <span className="text-2xl font-extrabold text-midnight">
            ₹{total.toLocaleString('en-IN')}
          </span>
        </div>
      </div>

      <div className="bg-arctic-soft border border-slopes/35 rounded-xl p-3.5 mb-5 text-xs text-apres flex items-start gap-2.5">
        <span className="text-base mt-0.5">🔒</span>
        <p className="leading-relaxed">
          NexaCart has verified inventory and enforced budget boundaries. Approving will generate the secure payment request.
        </p>
      </div>

      <div className="flex gap-3">
        <button
          onClick={onCancel}
          className="flex-1 py-3 px-4 bg-arctic-soft border border-slopes/40 text-mountainside font-semibold rounded-xl hover:bg-arctic text-xs transition-all"
        >
          Cancel
        </button>
        <button
          onClick={onApprove}
          disabled={isApproving}
          className="flex-1 py-3 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm text-xs hover:scale-[1.01]"
        >
          {isApproving ? 'Authorizing...' : 'Approve & Pay'}
        </button>
      </div>
    </div>
  );
}
