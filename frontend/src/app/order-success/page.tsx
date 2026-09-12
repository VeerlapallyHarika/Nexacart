'use client';

import { useState, useEffect, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Order } from '@/lib/types';
import { getOrder, getOrders } from '@/lib/api';

function getStoredSessionId(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem('nexacart_session_id');
}

function OrderSuccessContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const orderId = searchParams.get('order_id');

  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOrder = useCallback(async () => {
    const sessionId = getStoredSessionId();
    try {
      if (orderId) {
        const data = await getOrder(orderId);
        setOrder(data);
      } else if (sessionId) {
        const data = await getOrders(sessionId);
        if (data.orders.length > 0) {
          setOrder(data.orders[0]);
        }
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load order details.');
    } finally {
      setLoading(false);
    }
  }, [orderId]);

  useEffect(() => { loadOrder(); }, [loadOrder]);

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
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-20">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="w-10 h-10 border-[3px] border-slopes border-t-midnight rounded-full animate-spin mb-4" />
            <p className="text-sm text-apres font-medium">Loading order details…</p>
          </div>
        ) : error ? (
          <div className="text-center py-20 space-y-4">
            <div className="w-16 h-16 bg-rose-50 border border-rose-200 rounded-2xl flex items-center justify-center mx-auto text-3xl">⚠️</div>
            <p className="text-sm font-semibold text-rose-700">{error}</p>
            <button onClick={() => router.push('/')} className="px-5 py-2.5 bg-midnight hover:bg-mountainside text-white text-sm font-semibold rounded-xl transition-all shadow-xs">Go Home</button>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Success Header */}
            <div className="text-center space-y-4">
              <div className="w-20 h-20 bg-emerald-100 border-2 border-emerald-300 rounded-full flex items-center justify-center mx-auto">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <h1 className="text-2xl sm:text-3xl font-extrabold text-midnight tracking-tight">Purchase Successful</h1>
                <p className="text-sm text-apres mt-1.5">Your order has been confirmed and recorded.</p>
              </div>
            </div>

            {/* Verification Badges */}
            <div className="flex flex-wrap justify-center gap-2.5">
              <div className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800">
                <span className="text-emerald-600 font-bold text-sm">✓</span>
                <span className="text-xs font-semibold">Payment verified</span>
              </div>
              <div className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800">
                <span className="text-emerald-600 font-bold text-sm">✓</span>
                <span className="text-xs font-semibold">Order confirmed</span>
              </div>
              <div className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800">
                <span className="text-emerald-600 font-bold text-sm">✓</span>
                <span className="text-xs font-semibold">Commerce decision recorded</span>
              </div>
            </div>

            {/* Order Details */}
            {order && (
              <div className="bg-white rounded-2xl border border-slopes/25 shadow-2xs overflow-hidden">
                <div className="px-5 py-4 bg-arctic-soft/40 border-b border-slopes/15">
                  <h2 className="text-sm font-bold text-midnight uppercase tracking-wider">Order Details</h2>
                </div>
                <div className="p-5 space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-[10px] font-bold text-apres uppercase tracking-wider">Order ID</p>
                      <p className="text-sm font-mono font-bold text-midnight mt-0.5">{order.order_id}</p>
                    </div>
                    <div>
                      <p className="text-[10px] font-bold text-apres uppercase tracking-wider">Status</p>
                      <span className="inline-block px-2.5 py-0.5 rounded-full bg-emerald-100 border border-emerald-200 text-emerald-800 text-[11px] font-bold mt-0.5">
                        {order.status}
                      </span>
                    </div>
                  </div>

                  {/* Items */}
                  <div className="pt-3 border-t border-slopes/15">
                    <p className="text-[10px] font-bold text-apres uppercase tracking-wider mb-2">Items</p>
                    <div className="space-y-2">
                      {order.items.map((item) => (
                        <div key={item.id} className="flex items-center justify-between text-xs">
                          <span className="text-apres-dark">{item.product_name} × {item.quantity}</span>
                          <span className="font-medium text-midnight">₹{item.subtotal.toLocaleString('en-IN')}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Total */}
                  <div className="pt-3 border-t border-slopes/20">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-bold text-midnight">Total Paid</span>
                      <span className="text-xl font-extrabold text-midnight">₹{order.total_amount.toLocaleString('en-IN')}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => router.push('/')}
                className="flex-1 py-3.5 px-4 bg-midnight hover:bg-mountainside text-white font-semibold rounded-xl text-sm transition-all shadow-sm hover:scale-[1.01] flex items-center justify-center gap-2"
              >
                <span>Continue Shopping</span>
                <span className="text-emerald-400">→</span>
              </button>
              <button
                onClick={() => router.push('/')}
                className="flex-1 py-3.5 px-4 bg-arctic-soft border border-slopes/40 text-mountainside font-semibold rounded-xl text-sm hover:bg-arctic hover:border-slopes/60 transition-all flex items-center justify-center gap-2"
              >
                <span>🔄</span>
                <span>New Purchase</span>
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default function OrderSuccessPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-arctic-soft flex flex-col items-center justify-center">
        <div className="w-10 h-10 border-[3px] border-slopes border-t-midnight rounded-full animate-spin mb-4" />
        <p className="text-sm text-apres font-medium">Loading…</p>
      </div>
    }>
      <OrderSuccessContent />
    </Suspense>
  );
}
