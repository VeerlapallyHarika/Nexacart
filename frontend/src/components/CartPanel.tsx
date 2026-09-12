'use client';

import { Cart, CartItem } from '@/lib/types';
import { PaymentInfo, PaymentActions } from './PaymentPanel';
import { formatCartStatus } from '@/lib/utils';

interface CartPanelProps {
  cart: Cart | null;
  isOpen: boolean;
  onClose: () => void;
  onRemoveItem: (itemId: string) => void;
  onUpdateQuantity: (itemId: string, quantity: number) => void;
  onVerifyCart: () => void;
  onRequestApproval: () => void;
  onApproveCheckout: () => void;
  onCreatePayment: () => void;
  onConfirmPayment: () => void;
  onCancelPayment: () => void;
  onRetryRazorpay: () => void;
  onReplay: () => void;
  isVerifying: boolean;
  isRequestingApproval: boolean;
  isApproving: boolean;
  isProcessingPayment: boolean;
  paymentId: string | null;
  paymentProvider?: string;
}

export default function CartPanel({
  cart,
  isOpen,
  onClose,
  onRemoveItem,
  onUpdateQuantity,
  onVerifyCart,
  onRequestApproval,
  onApproveCheckout,
  onCreatePayment,
  onConfirmPayment,
  onCancelPayment,
  onRetryRazorpay,
  onReplay,
  isVerifying,
  isRequestingApproval,
  isApproving,
  isProcessingPayment,
  paymentId,
  paymentProvider,
}: CartPanelProps) {
  if (!isOpen) return null;

  const items = cart?.items || [];
  const total = cart?.total || 0;
  const isEmpty = items.length === 0;
  const isVerified = cart?.status === 'VERIFIED';
  const isAwaitingApproval = cart?.status === 'AWAITING_APPROVAL';
  const isApprovedForPayment = cart?.status === 'APPROVED_FOR_PAYMENT';
  const isPaid = cart?.status === 'PAID';

  return (
    <div className="fixed inset-0 bg-midnight/70 backdrop-blur-xs z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slopes/40 w-full max-w-md max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header - fixed */}
        <div className="flex items-center justify-between p-5 border-b border-slopes/25 bg-arctic-soft/40 flex-shrink-0">
          <div>
            <h2 className="text-lg font-bold text-midnight tracking-tight">Shopping Cart</h2>
            <p className="text-xs text-apres">Deterministic state verification</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-arctic-soft text-apres hover:text-midnight rounded-xl transition-all border border-transparent hover:border-slopes/30"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {isEmpty ? (
            <div className="text-center py-12 text-apres">
              <div className="w-16 h-16 bg-arctic-soft rounded-2xl flex items-center justify-center mx-auto mb-4 text-3xl border border-slopes/20">
                🛒
              </div>
              <p className="font-bold text-midnight text-base">Your cart is empty</p>
              <p className="text-xs text-apres mt-1">Discover items in catalog or use the AI Assistant!</p>
            </div>
          ) : (
            <>
              {/* Cart items */}
              <div className="space-y-2.5">
                {items.map((item: CartItem) => (
                  <div
                    key={item.id}
                    className="flex items-start gap-3.5 p-3.5 bg-arctic-soft/50 border border-slopes/25 rounded-xl transition-all"
                  >
                    <div className="flex-1 min-w-0">
                      <h3 className="font-bold text-midnight text-sm truncate">{item.product_name}</h3>
                      <p className="text-xs text-apres mt-0.5">
                        ₹{item.price.toLocaleString('en-IN')} × {item.quantity}
                      </p>
                      <p className="text-xs font-bold text-midnight mt-1.5">
                        Subtotal: ₹{item.subtotal.toLocaleString('en-IN')}
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {!isPaid && !isApprovedForPayment && (
                        <>
                          <button
                            onClick={() => onUpdateQuantity(item.id, item.quantity - 1)}
                            className="w-7 h-7 flex items-center justify-center bg-white border border-slopes/35 hover:bg-arctic text-midnight font-bold rounded-lg transition-all text-xs shadow-2xs"
                          >
                            -
                          </button>
                          <span className="w-6 text-center text-xs font-bold text-midnight">{item.quantity}</span>
                          <button
                            onClick={() => onUpdateQuantity(item.id, item.quantity + 1)}
                            className="w-7 h-7 flex items-center justify-center bg-white border border-slopes/35 hover:bg-arctic text-midnight font-bold rounded-lg transition-all text-xs shadow-2xs"
                          >
                            +
                          </button>
                          <button
                            onClick={() => onRemoveItem(item.id)}
                            className="w-7 h-7 flex items-center justify-center text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-200 rounded-lg transition-all text-xs ml-1"
                            title="Remove item"
                          >
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              className="h-3.5 w-3.5"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                              />
                            </svg>
                          </button>
                        </>
                      )}
                      {(isPaid || isApprovedForPayment) && (
                        <span className="text-xs font-semibold text-apres bg-white px-2 py-1 rounded-md border border-slopes/20">
                          Qty: {item.quantity}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Payment info */}
              {isApprovedForPayment && paymentId && (
                <PaymentInfo cart={cart} paymentId={paymentId} provider={paymentProvider} />
              )}

              {/* Paid confirmation */}
              {isPaid && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4 text-center">
                  <p className="text-emerald-900 font-bold text-sm">Order Confirmed</p>
                  <p className="text-xs text-emerald-700 mt-0.5">
                    Your order has been placed and verified successfully!
                  </p>
                </div>
              )}

              {/* Awaiting approval notice */}
              {isAwaitingApproval && (
                <div className="bg-amber-50 border border-amber-200 rounded-2xl p-3.5 text-center">
                  <p className="text-amber-900 font-bold text-xs">Awaiting User Checkout Approval</p>
                  <p className="text-[11px] text-amber-700 mt-0.5">
                    Review and confirm to authorize payment creation.
                  </p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Sticky footer with actions */}
        {!isEmpty && (
          <div className="border-t border-slopes/25 p-5 bg-arctic-soft/30 flex-shrink-0 space-y-3">
            {/* Total */}
            <div className="flex justify-between items-center">
              <span className="text-xs font-semibold text-apres uppercase tracking-wider">Cart Total</span>
              <span className="text-xl font-extrabold text-midnight">
                ₹{total.toLocaleString('en-IN')}
              </span>
            </div>

            {/* Status */}
            {cart?.status && (
              <div className="text-xs text-apres flex justify-between items-center">
                <span>Verification State:</span>
                <span
                  key={cart.status}
                  className="font-semibold text-midnight bg-white px-2.5 py-0.5 rounded-full border border-slopes/25 text-[11px] animate-highlight-flash"
                >
                  {formatCartStatus(cart.status)}
                </span>
              </div>
            )}

            {/* Action buttons */}
            {isApprovedForPayment && paymentId && paymentProvider !== 'razorpay' && (
              <PaymentActions
                total={total}
                isProcessing={isProcessingPayment}
                onConfirmPayment={onConfirmPayment}
                onCancel={onCancelPayment}
              />
            )}

            {isApprovedForPayment && paymentId && paymentProvider === 'razorpay' && (
              <div className="space-y-2.5">
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-center">
                  <p className="text-xs font-bold text-emerald-900">Razorpay checkout handles payment</p>
                  <p className="text-[11px] text-emerald-700 mt-0.5">
                    Use the checkout window or click below to retry.
                  </p>
                </div>
                <div className="flex gap-2.5">
                  <button
                    onClick={onCancelPayment}
                    disabled={isProcessingPayment}
                    className="flex-1 py-3 px-4 bg-arctic-soft border border-slopes/40 text-mountainside font-semibold rounded-xl hover:bg-arctic hover:border-slopes/60 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-xs"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={onRetryRazorpay}
                    disabled={isProcessingPayment}
                    className="flex-1 py-3 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm text-xs hover:scale-[1.01]"
                  >
                    {isProcessingPayment ? (
                      <span className="flex items-center justify-center gap-2">
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Processing...
                      </span>
                    ) : (
                      `Retry ₹${total.toLocaleString('en-IN')}`
                    )}
                  </button>
                </div>
              </div>
            )}

            {isApprovedForPayment && !paymentId && (
              <button
                onClick={onCreatePayment}
                disabled={isProcessingPayment}
                className="w-full py-3.5 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm hover:scale-[1.01]"
              >
                {isProcessingPayment ? 'Initializing Gateway...' : 'Proceed to Payment'}
              </button>
            )}

            {!isVerified && !isAwaitingApproval && !isApprovedForPayment && !isPaid && (
              <button
                onClick={onVerifyCart}
                disabled={isVerifying}
                className="w-full py-3.5 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm hover:scale-[1.01]"
              >
                {isVerifying ? 'Verifying inventory & pricing...' : 'Verify Cart'}
              </button>
            )}

            {isVerified && (
              <button
                onClick={onRequestApproval}
                disabled={isRequestingApproval}
                className="w-full py-3.5 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm hover:scale-[1.01]"
              >
                {isRequestingApproval ? 'Requesting Approval...' : 'Proceed to Checkout'}
              </button>
            )}

            {isAwaitingApproval && (
              <button
                onClick={onApproveCheckout}
                disabled={isApproving}
                className="w-full py-3.5 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm hover:scale-[1.01]"
              >
                {isApproving ? 'Authorizing...' : 'Approve Checkout'}
              </button>
            )}

            {isPaid && (
              <button
                onClick={onReplay}
                className="w-full py-3.5 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-sm transition-all shadow-sm hover:scale-[1.01] flex items-center justify-center gap-2"
              >
                <span>🎬</span>
                <span>Replay My Purchase</span>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
