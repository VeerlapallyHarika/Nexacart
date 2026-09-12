import React, { useState, useEffect } from 'react';
import { Order } from '@/lib/types';
import { getOrders } from '@/lib/api';
import LoadingSpinner from '../LoadingSpinner';
import { useAuth } from '@/context/AuthContext';

interface OrdersViewProps {
  sessionId: string | undefined;
  onReplayClick: (sessionId: string) => void;
}

export default function OrdersView({ sessionId, onReplayClick }: OrdersViewProps) {
  const { token, isAuthenticated } = useAuth();
  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadOrders = async () => {
      try {
        setIsLoading(true);
        const data = await getOrders(sessionId, token);
        setOrders(data.orders || []);
      } catch (err: any) {
        console.error('Failed to load orders:', err);
        setError(err?.message || 'Failed to load orders. Please try again later.');
      } finally {
        setIsLoading(false);
      }
    };

    loadOrders();
  }, [sessionId, token]);

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case 'COMPLETED':
      case 'PAID':
      case 'CONFIRMED':
        return 'bg-emerald-50 text-emerald-800 border-emerald-200';
      case 'PENDING':
      case 'CREATED':
        return 'bg-amber-50 text-amber-800 border-amber-200';
      case 'CANCELLED':
        return 'bg-rose-50 text-rose-800 border-rose-200';
      default:
        return 'bg-arctic-soft text-mountainside border-slopes/30';
    }
  };

  return (
    <div className="flex-1 overflow-y-auto bg-arctic-soft p-6 lg:p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8 pb-4 border-b border-slopes/25">
          <h1 className="text-xl font-bold text-midnight tracking-tight">Your Orders</h1>
          <p className="text-apres text-sm mt-1">Verified purchase history with full audit replay</p>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-24">
            <LoadingSpinner />
          </div>
        ) : error ? (
          <div className="bg-white border border-rose-200 text-rose-700 p-6 rounded-2xl text-center shadow-sm">
            {error}
          </div>
        ) : orders.length === 0 ? (
          <div className="bg-white p-12 rounded-2xl border border-slopes/30 text-center shadow-sm max-w-lg mx-auto my-12">
            <div className="w-16 h-16 bg-arctic-soft rounded-2xl flex items-center justify-center mx-auto mb-4 text-3xl border border-slopes/20">
              📦
            </div>
            <h3 className="text-lg font-bold text-midnight mb-1">No orders yet</h3>
            <p className="text-apres text-sm mb-6">Completed purchases in your account will appear here.</p>
          </div>
        ) : (
          <div className="space-y-6">
            {orders.map((order) => (
              <div
                key={order.order_id}
                className="bg-white rounded-2xl border border-slopes/40 shadow-xs hover:border-mountainside/40 transition-all overflow-hidden"
              >
                <div className="bg-arctic-soft/60 px-6 py-4 border-b border-slopes/25 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                  <div>
                    <div className="text-[11px] font-semibold text-apres uppercase tracking-wider mb-0.5">
                      Order ID
                    </div>
                    <div className="font-mono text-xs font-semibold text-midnight">
                      {order.order_id}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] font-semibold text-apres uppercase tracking-wider mb-0.5">
                      Date
                    </div>
                    <div className="text-xs font-medium text-midnight">
                      {order.created_at ? new Date(order.created_at).toLocaleDateString() : 'Recent'}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] font-semibold text-apres uppercase tracking-wider mb-0.5">
                      Total
                    </div>
                    <div className="text-sm font-extrabold text-midnight">
                      ₹{order.total_amount?.toLocaleString('en-IN')}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] font-semibold text-apres uppercase tracking-wider mb-0.5">
                      Status
                    </div>
                    <div className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${getStatusBadge(order.status)}`}>
                      {order.status}
                    </div>
                  </div>
                </div>

                <div className="p-6">
                  <h4 className="text-xs font-bold text-midnight uppercase tracking-wider mb-3">
                    Purchased Items
                  </h4>
                  <ul className="space-y-3 mb-6">
                    {order.items.map((item, idx) => (
                      <li key={idx} className="flex justify-between items-center text-sm py-1 border-b border-slopes/15 last:border-0">
                        <div className="flex items-center gap-3">
                          <span className="w-6 h-6 bg-arctic-soft border border-slopes/25 rounded-md flex items-center justify-center text-xs font-bold text-mountainside">
                            {item.quantity}×
                          </span>
                          <span className="text-midnight font-medium">{item.product_name || item.product_id}</span>
                        </div>
                        <span className="font-bold text-midnight text-sm">
                          ₹{(item.price_at_purchase * item.quantity).toLocaleString('en-IN')}
                        </span>
                      </li>
                    ))}
                  </ul>

                  <div className="flex justify-end pt-4 border-t border-slopes/20">
                    <button
                      onClick={() => onReplayClick(order.session_id || sessionId!)}
                      className="flex items-center gap-2 px-4 py-2 bg-midnight text-white hover:bg-mountainside rounded-xl text-xs font-semibold transition-all shadow-xs hover:scale-[1.02]"
                    >
                      <span>🎬</span>
                      <span>View Purchase Replay</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
