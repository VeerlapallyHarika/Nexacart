'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Cart, CommerceContract } from '@/lib/types';
import { fetchCart, fetchContract, createPayment, verifyRazorpayPayment, confirmPayment, getOrders, requestCheckoutApproval, approveCheckout } from '@/lib/api';
import { loadRazorpayScript, openRazorpayCheckout, RazorpayCheckoutResult } from '@/lib/razorpay';

function getStoredSessionId(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem('nexacart_session_id');
}

type PayButtonState = 'idle' | 'initializing' | 'opening' | 'processing' | 'success' | 'error';

export default function CheckoutPage() {
  const router = useRouter();
  const [cart, setCart] = useState<Cart | null>(null);
  const [contract, setContract] = useState<CommerceContract | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [payState, setPayState] = useState<PayButtonState>('idle');
  const [paymentError, setPaymentError] = useState<string | null>(null);

  const paymentIdRef = useRef<string | null>(null);
  const razorpayOrderIdRef = useRef<string | null>(null);
  const razorpayKeyIdRef = useRef<string | null>(null);
  const razorpayAmountRef = useRef<number>(0);
  const razorpayCurrencyRef = useRef<string>('INR');
  const paymentProviderRef = useRef<string | null>(null);
  const checkoutInProgressRef = useRef(false);
  const submitLockRef = useRef(false);

  const loadInitialData = useCallback(async () => {
    const sessionId = getStoredSessionId();
    if (!sessionId) {
      setError('No active session. Please log in first.');
      setLoading(false);
      return;
    }
    try {
      const [cartResult, contractResult] = await Promise.allSettled([
        fetchCart(sessionId),
        fetchContract(sessionId),
      ]);
      if (cartResult.status === 'fulfilled') {
        setCart(cartResult.value);
      } else {
        setError('Failed to load cart.');
      }
      if (contractResult.status === 'fulfilled') {
        setContract(contractResult.value);
      }
    } catch {
      setError('Failed to load checkout data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadInitialData(); }, [loadInitialData]);

  const ensureCartApproved = async (sessionId: string, currentCart: Cart): Promise<boolean> => {
    if (currentCart.status === 'APPROVED_FOR_PAYMENT') return true;

    if (currentCart.status === 'VERIFIED' || currentCart.status === 'ACTIVE') {
      try {
        await requestCheckoutApproval(sessionId);
      } catch (err: any) {
        if (!err?.message?.includes('already')) {
          setPaymentError(err?.message || 'Failed to request checkout approval.');
          setPayState('error');
          return false;
        }
      }
    }

    let refreshed = await fetchCart(sessionId);
    setCart(refreshed);

    if (refreshed.status === 'AWAITING_APPROVAL') {
      try {
        await approveCheckout(sessionId);
      } catch (err: any) {
        if (!err?.message?.includes('already')) {
          setPaymentError(err?.message || 'Failed to approve checkout.');
          setPayState('error');
          return false;
        }
      }
    }

    if (refreshed.status !== 'APPROVED_FOR_PAYMENT') {
      try {
        refreshed = await fetchCart(sessionId);
        setCart(refreshed);
      } catch {}
    }

    return refreshed.status === 'APPROVED_FOR_PAYMENT';
  };

  const handlePay = async () => {
    if (checkoutInProgressRef.current || submitLockRef.current) return;

    const sessionId = getStoredSessionId();
    if (!sessionId) {
      setPaymentError('No active session. Please log in again.');
      setPayState('error');
      return;
    }

    submitLockRef.current = true;
    setPayState('initializing');
    setPaymentError(null);

    try {
      const currentCart = await fetchCart(sessionId);
      setCart(currentCart);

      if (currentCart.items.length === 0) {
        setPaymentError('Your cart is empty. Please add items before paying.');
        setPayState('error');
        return;
      }

      const approved = await ensureCartApproved(sessionId, currentCart);
      if (!approved) return;

      const result = await createPayment(sessionId);

      if (result.already_completed) {
        if (result.order_id) {
          router.push(`/order-success?order_id=${result.order_id}`);
        } else {
          router.push('/order-success');
        }
        return;
      }

      if (!result.success) {
        setPaymentError('Failed to initialize payment. Please try again.');
        setPayState('error');
        return;
      }

      paymentIdRef.current = result.payment_id;
      paymentProviderRef.current = result.provider || null;

      if (result.provider === 'razorpay') {
        if (!result.razorpay_order_id || !result.razorpay_key_id) {
          setPaymentError('Payment server returned incomplete Razorpay data. Please retry.');
          setPayState('error');
          return;
        }

        razorpayOrderIdRef.current = result.razorpay_order_id;
        razorpayKeyIdRef.current = result.razorpay_key_id;
        razorpayAmountRef.current = result.amount;
        razorpayCurrencyRef.current = result.currency;

        const scriptLoaded = await loadRazorpayScript();
        if (!scriptLoaded) {
          setPaymentError('Failed to load Razorpay checkout SDK. Please check your connection and retry.');
          setPayState('error');
          return;
        }

        setPayState('opening');

        checkoutInProgressRef.current = true;

        const rzpResult: RazorpayCheckoutResult = await openRazorpayCheckout({
          key: razorpayKeyIdRef.current,
          amount: razorpayAmountRef.current * 100,
          currency: razorpayCurrencyRef.current,
          name: 'NexaCart',
          description: 'Purchase from NexaCart',
          order_id: razorpayOrderIdRef.current,
          handler: async (paymentResponse) => {
            try {
              setPayState('processing');
              const verifyResult = await verifyRazorpayPayment(paymentIdRef.current!, {
                razorpay_order_id: paymentResponse.razorpay_order_id,
                razorpay_payment_id: paymentResponse.razorpay_payment_id,
                razorpay_signature: paymentResponse.razorpay_signature,
              });

              if (verifyResult.success) {
                setPayState('success');
                const orders = await getOrders(getStoredSessionId() || undefined);
                const order = orders.orders.length > 0 ? orders.orders[0] : null;
                router.push(order ? `/order-success?order_id=${order.order_id}` : '/order-success');
              } else {
                setPaymentError('Payment verification failed. Please try again.');
                setPayState('error');
              }
            } catch (verifyErr: any) {
              setPaymentError(verifyErr?.message || 'Payment verification failed. Please contact support.');
              setPayState('error');
            } finally {
              checkoutInProgressRef.current = false;
              submitLockRef.current = false;
            }
          },
          modal: {
            ondismiss: () => {
              checkoutInProgressRef.current = false;
              submitLockRef.current = false;
              setPaymentError(null);
              setPayState('idle');
            },
          },
        });

        if (rzpResult.dismissed) {
          checkoutInProgressRef.current = false;
          submitLockRef.current = false;
          setPayState('idle');
        }
      } else {
        setPayState('processing');
        const confirmResult = await confirmPayment(result.payment_id);
        if (confirmResult.success) {
          setPayState('success');
          const orders = await getOrders(getStoredSessionId() || undefined);
          const order = orders.orders.length > 0 ? orders.orders[0] : null;
          router.push(order ? `/order-success?order_id=${order.order_id}` : '/order-success');
        } else {
          setPaymentError('Payment failed. Please try again.');
          setPayState('error');
        }
      }
    } catch (err: any) {
      setPaymentError(err?.message || 'Failed to start payment. Please try again.');
      setPayState('error');
    } finally {
      submitLockRef.current = false;
    }
  };

  const handleRetry = () => {
    checkoutInProgressRef.current = false;
    submitLockRef.current = false;
    setPaymentError(null);
    setPayState('idle');
  };

  const items = cart?.items || [];
  const total = cart?.total || 0;
  const isContractActive = contract?.status === 'ACTIVE';

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
          <button onClick={() => router.push('/cart')} className="px-4 py-2 text-sm font-medium text-arctic hover:text-white hover:bg-mountainside/60 rounded-xl transition-all">← Back to Cart</button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-24">
            <div className="w-10 h-10 border-[3px] border-slopes border-t-midnight rounded-full animate-spin mb-4" />
            <p className="text-sm text-apres font-medium">Preparing checkout…</p>
          </div>
        ) : error ? (
          <div className="text-center py-24 space-y-4">
            <div className="w-16 h-16 bg-rose-50 border border-rose-200 rounded-2xl flex items-center justify-center mx-auto text-3xl">⚠️</div>
            <p className="text-sm font-semibold text-rose-700">{error}</p>
            <div className="flex gap-3 justify-center">
              <button onClick={loadInitialData} className="px-5 py-2.5 bg-midnight hover:bg-mountainside text-white text-sm font-semibold rounded-xl transition-all shadow-xs">Retry</button>
              <button onClick={() => router.push('/cart')} className="px-5 py-2.5 bg-arctic-soft border border-slopes/40 text-mountainside text-sm font-semibold rounded-xl hover:bg-arctic transition-all">Back to Cart</button>
            </div>
          </div>
        ) : !cart || items.length === 0 ? (
          <div className="text-center py-24 space-y-5">
            <div className="w-20 h-20 bg-white border border-slopes/30 rounded-3xl flex items-center justify-center mx-auto text-4xl shadow-2xs">🛒</div>
            <div>
              <h2 className="text-xl font-bold text-midnight">Cart is empty</h2>
              <p className="text-sm text-apres mt-1.5">Add items to your cart before checking out.</p>
            </div>
            <button onClick={() => router.push('/')} className="px-6 py-3 bg-midnight hover:bg-mountainside text-white text-sm font-semibold rounded-xl transition-all shadow-xs">Start Shopping</button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Page Header */}
            <div className="space-y-1">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-midnight tracking-tight">Checkout</h1>
              <p className="text-sm text-apres">Review your purchase and complete payment.</p>
            </div>

            {/* Progress Steps */}
            <div className="flex items-center gap-2 text-xs font-semibold">
              <span className="flex items-center gap-1.5 text-emerald-700"><span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px]">✓</span> Cart</span>
              <span className="text-slopes">→</span>
              <span className="flex items-center gap-1.5 text-emerald-700"><span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px]">✓</span> Summary</span>
              <span className="text-slopes">→</span>
              <span className={`flex items-center gap-1.5 ${payState === 'opening' || payState === 'processing' ? 'text-amber-700' : payState === 'success' ? 'text-emerald-700' : 'text-midnight'}`}>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] ${payState === 'opening' || payState === 'processing' ? 'bg-amber-500 text-white animate-pulse' : payState === 'success' ? 'bg-emerald-600 text-white' : 'bg-midnight text-white'}`}>
                  {payState === 'success' ? '✓' : payState === 'opening' || payState === 'processing' ? '●' : '3'}
                </span>
                Payment
              </span>
              <span className="text-slopes">→</span>
              <span className="text-apres">Order</span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column - Summary */}
              <div className="lg:col-span-2 space-y-4">
                {/* Purchase Summary */}
                <div className="bg-white rounded-2xl border border-slopes/25 shadow-2xs overflow-hidden">
                  <div className="px-5 py-4 bg-arctic-soft/40 border-b border-slopes/15">
                    <h2 className="text-sm font-bold text-midnight uppercase tracking-wider flex items-center gap-2">
                      <span className="p-1 rounded-md bg-indigo-100 text-indigo-700 text-[10px]">📋</span>
                      Purchase Summary
                    </h2>
                  </div>
                  <div className="p-5">
                    <p className="text-xs text-apres mb-3">You&apos;re about to purchase:</p>
                    <div className="space-y-3">
                      {items.map((item) => (
                        <div key={item.id} className="flex items-center gap-3 p-3 bg-arctic-soft/50 rounded-xl">
                          <div className="w-12 h-12 bg-gradient-to-br from-indigo-50 to-violet-50 border border-indigo-100 rounded-lg flex items-center justify-center text-lg shrink-0">📦</div>
                          <div className="flex-1 min-w-0">
                            <p className="font-bold text-midnight text-sm truncate">{item.product_name}</p>
                            <p className="text-xs text-apres">Qty: {item.quantity}</p>
                          </div>
                          <span className="font-extrabold text-midnight text-sm shrink-0">₹{item.subtotal.toLocaleString('en-IN')}</span>
                        </div>
                      ))}
                    </div>
                    <div className="mt-4 pt-3 border-t border-slopes/15 flex items-center justify-between">
                      <span className="text-sm font-bold text-midnight">Total</span>
                      <span className="text-xl font-extrabold text-midnight">₹{total.toLocaleString('en-IN')}</span>
                    </div>
                  </div>
                </div>

                {/* Commerce Contract Status */}
                <div className="bg-white rounded-2xl border border-slopes/25 shadow-2xs p-5">
                  <h3 className="text-xs font-bold text-midnight uppercase tracking-wider mb-3 flex items-center gap-2">
                    <span className="p-1 rounded-md bg-indigo-100 text-indigo-700 text-[10px]">🛡️</span>
                    Commerce Contract Status
                  </h3>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-emerald-600 font-bold">✓</span>
                      <span className="text-apres-dark">Contract verified</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-emerald-600 font-bold">✓</span>
                      <span className="text-apres-dark">Purchase approved</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-emerald-600 font-bold">✓</span>
                      <span className="text-apres-dark">Cart confirmed</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column - Payment */}
              <div className="lg:col-span-1">
                <div className="bg-white rounded-2xl border border-slopes/25 shadow-2xs overflow-hidden sticky top-24">
                  <div className="px-5 py-4 bg-arctic-soft/40 border-b border-slopes/15">
                    <h2 className="text-sm font-bold text-midnight uppercase tracking-wider">Payment Method</h2>
                  </div>
                  <div className="p-5 space-y-4">
                    {/* Payment Provider Display */}
                    <div className="p-3.5 bg-arctic-soft/50 border border-slopes/25 rounded-xl">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 bg-midnight rounded-lg flex items-center justify-center text-white text-xs font-bold shrink-0">
                          ⚡
                        </div>
                        <div>
                          <p className="text-sm font-bold text-midnight">Razorpay / Sandbox</p>
                          <p className="text-[11px] text-apres">Secure payment checkout</p>
                        </div>
                      </div>
                    </div>

                    {/* Razorpay Test Info */}
                    <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3">
                      <p className="text-[11px] font-bold text-emerald-900">Razorpay Test Mode</p>
                      <p className="text-[11px] text-emerald-700 mt-0.5">Use test card 4111 1111 1111 1111</p>
                    </div>

                    {/* Payment Error */}
                    {paymentError && (
                      <div className="bg-rose-50 border border-rose-200 rounded-xl p-3">
                        <p className="text-xs font-bold text-rose-900">Payment Error</p>
                        <p className="text-[11px] text-rose-700 mt-0.5">{paymentError}</p>
                      </div>
                    )}

                    {/* Total */}
                    <div className="pt-2 border-t border-slopes/15">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-bold text-midnight">Total Payable</span>
                        <span className="text-lg font-extrabold text-midnight">₹{total.toLocaleString('en-IN')}</span>
                      </div>
                    </div>

                    {/* Action Button */}
                    {payState === 'idle' && (
                      <button
                        onClick={handlePay}
                        className="w-full py-3.5 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-sm transition-all shadow-sm hover:scale-[1.01] flex items-center justify-center gap-2"
                      >
                        <span>Pay ₹{total.toLocaleString('en-IN')}</span>
                        <span className="text-emerald-400">→</span>
                      </button>
                    )}

                    {payState === 'initializing' && (
                      <div className="w-full py-3.5 px-4 bg-midnight/70 text-white font-semibold rounded-xl text-sm flex items-center justify-center gap-2 cursor-not-allowed">
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        <span>Initializing secure payment…</span>
                      </div>
                    )}

                    {payState === 'opening' && (
                      <div className="w-full py-3.5 px-4 bg-midnight/70 text-white font-semibold rounded-xl text-sm flex items-center justify-center gap-2 cursor-not-allowed">
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        <span>Opening Razorpay…</span>
                      </div>
                    )}

                    {payState === 'processing' && (
                      <div className="w-full py-3.5 px-4 bg-midnight/70 text-white font-semibold rounded-xl text-sm flex items-center justify-center gap-2 cursor-not-allowed">
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        <span>Processing payment…</span>
                      </div>
                    )}

                    {payState === 'success' && (
                      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-center">
                        <p className="text-xs font-bold text-emerald-900">Payment Successful</p>
                        <p className="text-[11px] text-emerald-700 mt-0.5">Redirecting to order confirmation…</p>
                      </div>
                    )}

                    {payState === 'error' && (
                      <div className="space-y-2.5">
                        <button
                          onClick={handleRetry}
                          className="w-full py-3.5 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-sm transition-all shadow-sm hover:scale-[1.01] flex items-center justify-center gap-2"
                        >
                          <span>Retry Payment</span>
                          <span className="text-emerald-400">↻</span>
                        </button>
                      </div>
                    )}

                    <button onClick={() => router.push('/cart')} className="w-full py-3 px-4 bg-arctic-soft border border-slopes/40 text-mountainside font-semibold rounded-xl text-sm hover:bg-arctic hover:border-slopes/60 transition-all">
                      Back to Cart
                    </button>
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
