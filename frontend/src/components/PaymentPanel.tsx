'use client';

import { Cart } from '@/lib/types';

interface PaymentInfoProps {
  cart: Cart;
  paymentId: string | null;
  provider?: string;
}

export function PaymentInfo({ cart, paymentId, provider }: PaymentInfoProps) {
  const items = cart?.items || [];
  const total = cart?.total || 0;
  const isRazorpay = provider === 'razorpay';

  return (
    <div className="bg-arctic-soft/70 border border-slopes/40 rounded-2xl p-4">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-9 h-9 bg-midnight rounded-xl flex items-center justify-center flex-shrink-0 text-white shadow-xs">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
            />
          </svg>
        </div>
        <div>
          <h3 className="font-bold text-midnight text-sm">
            {isRazorpay ? 'Razorpay Gateway' : 'Simulated Payment Gateway'}
          </h3>
          <p className="text-xs text-apres">
            {isRazorpay ? 'Secure payment via Razorpay Test Mode' : 'Instant deterministic simulation — no real money charged'}
          </p>
        </div>
      </div>

      <div className="bg-white border border-slopes/30 rounded-xl p-3.5 mb-3 shadow-2xs">
        <div className="flex items-center justify-between mb-2 text-xs">
          <span className="text-apres">Payment Method</span>
          <span className="font-semibold text-midnight">
            {isRazorpay ? 'Razorpay' : 'Simulated Sandbox'}
          </span>
        </div>
        <div className="flex items-center justify-between mb-2 text-xs">
          <span className="text-apres">Order Items</span>
          <span className="font-semibold text-midnight">{items.length} item(s)</span>
        </div>
        <div className="border-t border-slopes/20 pt-2 mt-2">
          <div className="flex justify-between items-center">
            <span className="text-xs font-semibold text-apres">Total Payable</span>
            <span className="text-lg font-extrabold text-midnight">
              ₹{total.toLocaleString('en-IN')}
            </span>
          </div>
        </div>
      </div>

      {isRazorpay ? (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 mb-3">
          <div className="flex items-start gap-2">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4 text-emerald-600 mt-0.5 flex-shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
            <div>
              <p className="text-xs font-bold text-emerald-900">Razorpay Test Mode</p>
              <p className="text-xs text-emerald-700 mt-0.5">
                Use test credentials or card 4111 1111 1111 1111 for verification.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-arctic-soft border border-slopes/40 rounded-xl p-3 mb-3">
          <div className="flex items-start gap-2">
            <span className="text-xs mt-0.5">⚡</span>
            <div>
              <p className="text-xs font-bold text-midnight">Demo Sandbox Mode</p>
              <p className="text-xs text-apres mt-0.5">
                Simulated transaction with instant deterministic verification.
              </p>
            </div>
          </div>
        </div>
      )}

      {paymentId && (
        <div className="bg-arctic-soft/50 border border-slopes/25 rounded-xl p-2.5">
          <p className="text-[10px] font-semibold text-apres uppercase tracking-wider">Payment Reference</p>
          <p className="text-xs font-mono text-midnight break-all font-medium mt-0.5">{paymentId}</p>
        </div>
      )}
    </div>
  );
}

interface PaymentActionsProps {
  total: number;
  isProcessing: boolean;
  onConfirmPayment: () => void;
  onCancel: () => void;
}

export function PaymentActions({
  total,
  isProcessing,
  onConfirmPayment,
  onCancel,
}: PaymentActionsProps) {
  return (
    <div className="flex gap-2.5">
      <button
        onClick={onCancel}
        disabled={isProcessing}
        className="flex-1 py-3 px-4 bg-arctic-soft border border-slopes/40 text-mountainside font-semibold rounded-xl hover:bg-arctic hover:border-slopes/60 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-xs"
      >
        Cancel
      </button>
      <button
        onClick={onConfirmPayment}
        disabled={isProcessing}
        className="flex-1 py-3 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm text-xs hover:scale-[1.01]"
      >
        {isProcessing ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            Processing...
          </span>
        ) : (
          `Pay ₹${total.toLocaleString('en-IN')}`
        )}
      </button>
    </div>
  );
}

interface PaymentPanelProps {
  cart: Cart;
  paymentId: string | null;
  isProcessing: boolean;
  onConfirmPayment: () => void;
  onCancel: () => void;
}

export default function PaymentPanel({
  cart,
  paymentId,
  isProcessing,
  onConfirmPayment,
  onCancel,
}: PaymentPanelProps) {
  const total = cart?.total || 0;
  const isReadyForPayment = cart?.status === 'APPROVED_FOR_PAYMENT';

  if (!isReadyForPayment) return null;

  return (
    <div className="space-y-4">
      <PaymentInfo cart={cart} paymentId={paymentId} />
      <PaymentActions
        total={total}
        isProcessing={isProcessing}
        onConfirmPayment={onConfirmPayment}
        onCancel={onCancel}
      />
    </div>
  );
}
