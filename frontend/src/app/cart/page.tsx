'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Cart, CartItem, CommerceContract } from '@/lib/types';
import { fetchCart, updateCartItem, removeCartItem, fetchContract } from '@/lib/api';

function getStoredSessionId(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem('nexacart_session_id');
}

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl border ${ok ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-slate-50 border-slate-200 text-slate-500'}`}>
      <span className={`font-bold text-sm ${ok ? 'text-emerald-600' : 'text-slate-400'}`}>{ok ? '✓' : '○'}</span>
      <span className="text-xs font-semibold">{label}</span>
    </div>
  );
}

export default function CartPage() {
  const router = useRouter();
  const [cart, setCart] = useState<Cart | null>(null);
  const [contract, setContract] = useState<CommerceContract | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);

  const loadCart = useCallback(async () => {
    const sessionId = getStoredSessionId();
    if (!sessionId) {
      setError('No active session. Please log in first.');
      setLoading(false);
      return;
    }
    try {
      const [cartData, contractData] = await Promise.allSettled([
        fetchCart(sessionId),
        fetchContract(sessionId),
      ]);
      if (cartData.status === 'fulfilled') {
        setCart(cartData.value);
        setError(null);
      } else {
        setError('Failed to load cart. Please try again.');
      }
      if (contractData.status === 'fulfilled') {
        setContract(contractData.value);
      }
    } catch {
      setError('Failed to load cart. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadCart(); }, [loadCart]);

  const handleUpdateQuantity = async (itemId: string, newQuantity: number) => {
    const sessionId = getStoredSessionId();
    if (!sessionId) return;
    setIsUpdating(true);
    try {
      await updateCartItem(sessionId, itemId, newQuantity);
      await loadCart();
    } finally {
      setIsUpdating(false);
    }
  };

  const handleRemoveItem = async (itemId: string) => {
    const sessionId = getStoredSessionId();
    if (!sessionId) return;
    setIsUpdating(true);
    try {
      await removeCartItem(sessionId, itemId);
      await loadCart();
    } finally {
      setIsUpdating(false);
    }
  };

  const items = cart?.items || [];
  const total = cart?.total || 0;
  const isEmpty = items.length === 0;
  const isPaid = cart?.status === 'PAID';
  const isApprovedForPayment = cart?.status === 'APPROVED_FOR_PAYMENT';
  const isContractActive = contract?.status === 'ACTIVE';
  const canEdit = !isPaid && !isApprovedForPayment;

  return (
    <div className="min-h-screen bg-arctic-soft">
      {/* Header */}
      <header className="bg-midnight border-b border-mountainside/80 px-6 py-3.5 sticky top-0 z-30 shadow-md">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-3 cursor-pointer group" onClick={() => router.push('/')}>
            <div className="w-10 h-10 bg-mountainside border border-slopes/30 rounded-xl flex items-center justify-center shadow-sm group-hover:border-slopes/60 transition-all">
              <span className="text-white font-bold text-xl tracking-tight">N</span>
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-1.5">
                NexaCart
                <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-accent/20 text-indigo-300 border border-accent/30 hidden sm:inline-block">AI Commerce</span>
              </h1>
            </div>
          </div>
          <nav className="flex items-center gap-1.5">
            <button onClick={() => router.push('/')} className="px-3.5 py-2 text-sm font-medium text-arctic hover:text-white hover:bg-mountainside/60 rounded-xl transition-all">Buyer Agent</button>
            <button onClick={() => router.push('/')} className="px-3.5 py-2 text-sm font-medium text-arctic hover:text-white hover:bg-mountainside/60 rounded-xl transition-all">AI Assistant</button>
          </nav>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-24">
            <div className="w-10 h-10 border-[3px] border-slopes border-t-midnight rounded-full animate-spin mb-4" />
            <p className="text-sm text-apres font-medium">Loading your cart…</p>
          </div>
        ) : error ? (
          <div className="text-center py-24 space-y-4">
            <div className="w-16 h-16 bg-rose-50 border border-rose-200 rounded-2xl flex items-center justify-center mx-auto text-3xl">⚠️</div>
            <p className="text-sm font-semibold text-rose-700">{error}</p>
            <button onClick={loadCart} className="px-5 py-2.5 bg-midnight hover:bg-mountainside text-white text-sm font-semibold rounded-xl transition-all shadow-xs">Retry</button>
          </div>
        ) : isEmpty ? (
          <div className="text-center py-24 space-y-5">
            <div className="w-20 h-20 bg-white border border-slopes/30 rounded-3xl flex items-center justify-center mx-auto text-4xl shadow-2xs">🛒</div>
            <div>
              <h2 className="text-xl font-bold text-midnight">Your cart is empty</h2>
              <p className="text-sm text-apres mt-1.5 max-w-sm mx-auto">Use the Buyer Agent or AI Assistant to discover and add products to your cart.</p>
            </div>
            <button onClick={() => router.push('/')} className="px-6 py-3 bg-midnight hover:bg-mountainside text-white text-sm font-semibold rounded-xl transition-all shadow-xs hover:scale-[1.01]">Start Shopping</button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Page Header */}
            <div className="space-y-1">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-midnight tracking-tight">Review Your Purchase</h1>
              <p className="text-sm text-apres">Your AI-approved purchase is ready for final checkout.</p>
            </div>

            {/* AI Verification Badges */}
            <div className="flex flex-wrap gap-2.5">
              <StatusBadge ok={true} label="Recommendation approved" />
              <StatusBadge ok={isContractActive} label={isContractActive ? 'Commerce Contract verified' : 'No active contract'} />
              <StatusBadge ok={true} label="Requirements satisfied" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Cart Items */}
              <div className="lg:col-span-2 space-y-3">
                {items.map((item: CartItem) => (
                  <div key={item.id} className="bg-white rounded-2xl border border-slopes/25 p-4 sm:p-5 shadow-2xs transition-all hover:shadow-sm">
                    <div className="flex items-start gap-4">
                      {/* Product Image Placeholder */}
                      <div className="w-16 h-16 sm:w-20 sm:h-20 bg-gradient-to-br from-indigo-50 to-violet-50 border border-indigo-100 rounded-xl flex items-center justify-center text-2xl sm:text-3xl shrink-0">📦</div>

                      {/* Product Details */}
                      <div className="flex-1 min-w-0">
                        <h3 className="font-bold text-midnight text-sm sm:text-base leading-snug">{item.product_name}</h3>
                        {item.description && <p className="text-xs text-apres mt-0.5 line-clamp-1">{item.description}</p>}
                        <div className="flex items-center gap-3 mt-2">
                          <span className="text-lg font-extrabold text-midnight">₹{item.price.toLocaleString('en-IN')}</span>
                          <span className="text-xs text-apres">× {item.quantity}</span>
                        </div>
                      </div>

                      {/* Controls */}
                      <div className="flex flex-col items-end gap-2 shrink-0">
                        <span className="text-base font-extrabold text-midnight">₹{item.subtotal.toLocaleString('en-IN')}</span>
                        {canEdit ? (
                          <div className="flex items-center gap-1.5">
                            <button onClick={() => handleUpdateQuantity(item.id, item.quantity - 1)} disabled={isUpdating} className="w-7 h-7 flex items-center justify-center bg-arctic-soft border border-slopes/35 hover:bg-arctic text-midnight font-bold rounded-lg transition-all text-xs shadow-2xs disabled:opacity-50">-</button>
                            <span className="w-6 text-center text-xs font-bold text-midnight">{item.quantity}</span>
                            <button onClick={() => handleUpdateQuantity(item.id, item.quantity + 1)} disabled={isUpdating} className="w-7 h-7 flex items-center justify-center bg-arctic-soft border border-slopes/35 hover:bg-arctic text-midnight font-bold rounded-lg transition-all text-xs shadow-2xs disabled:opacity-50">+</button>
                            <button onClick={() => handleRemoveItem(item.id)} disabled={isUpdating} className="w-7 h-7 flex items-center justify-center text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-200 rounded-lg transition-all text-xs ml-1 disabled:opacity-50" title="Remove item">
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                            </button>
                          </div>
                        ) : (
                          <span className="text-xs font-semibold text-apres bg-arctic-soft px-2.5 py-1 rounded-md border border-slopes/20">Qty: {item.quantity}</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}

                {/* Why This Was Selected */}
                <div className="bg-white rounded-2xl border border-slopes/25 p-4 sm:p-5 shadow-2xs">
                  <h3 className="text-xs font-bold text-midnight uppercase tracking-wider mb-3 flex items-center gap-2">
                    <span className="p-1 rounded-md bg-indigo-100 text-indigo-700 text-[10px]">💡</span>
                    Why this was selected
                  </h3>
                  <div className="space-y-2 text-xs text-apres-dark leading-relaxed">
                    <div className="flex items-start gap-2">
                      <span className="text-emerald-600 font-bold mt-0.5">✓</span>
                      <span>Matches your requested product and specifications</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-emerald-600 font-bold mt-0.5">✓</span>
                      <span>Best available match from the catalog within your criteria</span>
                    </div>
                    {isContractActive && (
                      <div className="flex items-start gap-2">
                        <span className="text-emerald-600 font-bold mt-0.5">✓</span>
                        <span>Fully compliant with your active AI Commerce Contract</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Order Summary */}
              <div className="lg:col-span-1">
                <div className="bg-white rounded-2xl border border-slopes/25 shadow-2xs overflow-hidden sticky top-24">
                  <div className="px-5 py-4 bg-arctic-soft/40 border-b border-slopes/15">
                    <h2 className="text-sm font-bold text-midnight uppercase tracking-wider">Order Summary</h2>
                  </div>
                  <div className="p-5 space-y-4">
                    {/* Item breakdown */}
                    <div className="space-y-2.5">
                      {items.map((item) => (
                        <div key={item.id} className="flex items-center justify-between text-xs">
                          <span className="text-apres truncate max-w-[160px]">{item.product_name} × {item.quantity}</span>
                          <span className="font-medium text-midnight shrink-0 ml-2">₹{item.subtotal.toLocaleString('en-IN')}</span>
                        </div>
                      ))}
                    </div>

                    {/* Subtotal */}
                    <div className="pt-3 border-t border-slopes/15">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-apres">Subtotal</span>
                        <span className="font-medium text-midnight">₹{total.toLocaleString('en-IN')}</span>
                      </div>
                    </div>

                    {/* Total */}
                    <div className="pt-3 border-t border-slopes/20">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-bold text-midnight">Total</span>
                        <span className="text-xl font-extrabold text-midnight">₹{total.toLocaleString('en-IN')}</span>
                      </div>
                    </div>

                    {/* Action */}
                    <div className="pt-2 space-y-2.5">
                      {isPaid ? (
                        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-center">
                          <p className="text-xs font-bold text-emerald-900">Order Confirmed</p>
                          <p className="text-[11px] text-emerald-700 mt-0.5">Your order has been placed successfully!</p>
                        </div>
                      ) : (
                        <button
                          onClick={() => router.push('/checkout')}
                          className="w-full py-3.5 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-sm transition-all shadow-sm hover:scale-[1.01] flex items-center justify-center gap-2"
                        >
                          <span>Proceed to Checkout</span>
                          <span className="text-emerald-400">→</span>
                        </button>
                      )}
                      <button onClick={() => router.push('/')} className="w-full py-3 px-4 bg-arctic-soft border border-slopes/40 text-mountainside font-semibold rounded-xl text-sm hover:bg-arctic hover:border-slopes/60 transition-all">
                        Continue Shopping
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
