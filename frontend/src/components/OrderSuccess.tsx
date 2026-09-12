'use client';

import { Order } from '@/lib/types';

interface OrderSuccessProps {
  order: Order;
  onClose: () => void;
  onReplay: () => void;
  onTrace: () => void;
}

export default function OrderSuccess({ order, onClose, onReplay, onTrace }: OrderSuccessProps) {
  if (!order) return null;

  return (
    <div className="bg-white border border-slopes/40 rounded-2xl p-6 my-4 shadow-2xl">
      <div className="flex items-center gap-3.5 mb-5 pb-4 border-b border-slopes/25">
        <div className="w-11 h-11 bg-midnight text-white rounded-xl flex items-center justify-center text-xl shadow-xs">
          ✅
        </div>
        <div>
          <h3 className="text-lg font-bold text-midnight tracking-tight">Order Confirmed!</h3>
          <p className="text-xs text-apres">Your AI-assisted purchase has been verified and placed</p>
        </div>
      </div>

      <div className="bg-arctic-soft/50 border border-slopes/25 rounded-xl p-4 mb-4 space-y-2.5 text-xs">
        <div className="flex items-center justify-between">
          <span className="text-apres font-semibold uppercase tracking-wider text-[10px]">Order ID</span>
          <span className="font-mono font-bold text-midnight">{order.order_id}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-apres font-semibold uppercase tracking-wider text-[10px]">Status</span>
          <span className="px-2.5 py-0.5 bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-bold rounded-full">
            {order.status}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-apres font-semibold uppercase tracking-wider text-[10px]">Payment Status</span>
          <span className="px-2.5 py-0.5 bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-bold rounded-full">
            {order.payment_status || 'PAID'}
          </span>
        </div>

        <div className="border-t border-slopes/20 pt-2.5 mt-2">
          <p className="font-bold text-midnight mb-1.5 uppercase tracking-wider text-[10px]">Items Purchased</p>
          {order.items.map((item) => (
            <div key={item.id} className="flex justify-between items-center py-1">
              <span className="text-mountainside font-medium">
                {item.product_name} × {item.quantity}
              </span>
              <span className="font-bold text-midnight">
                ₹{item.subtotal.toLocaleString('en-IN')}
              </span>
            </div>
          ))}
        </div>

        <div className="border-t border-slopes/20 pt-2.5 mt-2">
          <div className="flex justify-between items-center">
            <span className="font-bold text-midnight text-sm">Total Paid</span>
            <span className="text-lg font-extrabold text-midnight">
              ₹{order.total_amount.toLocaleString('en-IN')}
            </span>
          </div>
        </div>
      </div>

      <div className="bg-arctic-soft border border-slopes/35 rounded-xl p-3.5 mb-5 text-xs text-apres flex items-start gap-2.5">
        <span className="text-base mt-0.5">ℹ️</span>
        <p className="leading-relaxed">
          The conversation and validation audit trail for this purchase has been securely saved. You can inspect the step-by-step decision replay at any time.
        </p>
      </div>

      <div className="space-y-2.5">
        <button
          onClick={onReplay}
          className="w-full py-3.5 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-xs transition-all shadow-sm flex items-center justify-center gap-2 hover:scale-[1.01]"
        >
          <span>🎬</span>
          <span>View Purchase Replay</span>
        </button>

        <button
          onClick={onTrace}
          className="w-full py-2.5 px-4 bg-arctic-soft border border-slopes/40 text-mountainside hover:bg-arctic font-semibold rounded-xl text-xs transition-all flex items-center justify-center gap-2"
        >
          <span>🧭</span>
          <span>View Commerce Decision Trace</span>
        </button>

        <button
          onClick={onClose}
          className="w-full py-3 px-4 bg-arctic-soft border border-slopes/40 text-mountainside hover:bg-arctic font-semibold rounded-xl text-xs transition-all"
        >
          Continue Shopping
        </button>
      </div>
    </div>
  );
}
