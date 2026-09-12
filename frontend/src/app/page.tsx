'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { ChatMessage, Product, JourneyState, Cart, Order, CommerceContract, PurchaseReplayData, DecisionTraceData } from '@/lib/types';
import { fetchChat, fetchCart, addToCart, updateCartItem, removeCartItem, verifyCart, requestCheckoutApproval, approveCheckout, createPayment, confirmPayment, cancelPayment, getOrders, fetchContract, createContract, updateContract, activateContract, cancelContract, fetchPurchaseReplay, verifyRazorpayPayment, fetchDecisionTrace } from '@/lib/api';
import { loadRazorpayScript, openRazorpayCheckout } from '@/lib/razorpay';
import Header from '@/components/Header';
import CartPanel from '@/components/CartPanel';
import AICommerceContractPanel from '@/components/AICommerceContractPanel';
import PurchaseReplay from '@/components/PurchaseReplay';
import OrderSuccess from '@/components/OrderSuccess';
import DecisionTracePanel from '@/components/DecisionTracePanel';
import DecisionLabPanel from '@/components/DecisionLabPanel';

import HomeView from '@/components/views/HomeView';
import DiscoverView from '@/components/views/DiscoverView';
import AssistantView from '@/components/views/AssistantView';
import OrdersView from '@/components/views/OrdersView';
import BuyerAgentView from '@/components/views/BuyerAgentView';
import LoginView from '@/components/views/LoginView';
import RegisterView from '@/components/views/RegisterView';
import { useAuth } from '@/context/AuthContext';

const initialJourneyState: JourneyState = {
  intent: 'pending',
  discovery: 'pending',
  decision: 'pending',
  cart: 'pending',
  payment: 'pending',
};

type ViewType = 'home' | 'discover' | 'assistant' | 'orders' | 'buyer' | 'cart' | 'login' | 'register';

export default function Home() {
  const { isAuthenticated, isLoading: isAuthLoading, user } = useAuth();
  const [currentView, setCurrentView] = useState<ViewType>('home');
  const [authNotice, setAuthNotice] = useState<string | null>(null);

  // Automatically transition authenticated users to Buyer Agent if on public/auth pages
  useEffect(() => {
    if (!isAuthLoading && isAuthenticated) {
      if (currentView === 'home' || currentView === 'discover' || currentView === 'login' || currentView === 'register') {
        setCurrentView('buyer');
      }
    }
  }, [isAuthenticated, isAuthLoading, currentView]);
  const [targetAfterAuth, setTargetAfterAuth] = useState<ViewType | 'cart' | 'contract' | 'replay' | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | undefined>(() => {
    if (typeof window !== 'undefined') {
      return sessionStorage.getItem('nexacart_session_id') || undefined;
    }
    return undefined;
  });
  const sessionIdRef = useRef(sessionId);
  const razorpayPaymentIdRef = useRef<string | null>(null);
  const razorpayCheckoutInProgressRef = useRef(false);
  const paymentSubmitLockRef = useRef(false);
  const [isLoading, setIsLoading] = useState(false);
  const [journeyState, setJourneyState] = useState<JourneyState>(initialJourneyState);
  const [cart, setCart] = useState<Cart | null>(null);
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isRequestingApproval, setIsRequestingApproval] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [paymentId, setPaymentId] = useState<string | null>(null);
  const [paymentProvider, setPaymentProvider] = useState<string | undefined>(undefined);
  const [isProcessingPayment, setIsProcessingPayment] = useState(false);
  const [razorpayCheckout, setRazorpayCheckout] = useState<{
    orderId: string;
    keyId: string;
    amount: number;
    currency: string;
  } | null>(null);
  const [completedOrder, setCompletedOrder] = useState<Order | null>(null);
  const [contract, setContract] = useState<CommerceContract | null>(null);
  const [isContractOpen, setIsContractOpen] = useState(false);
  const [isContractBusy, setIsContractBusy] = useState(false);
  const [contractError, setContractError] = useState<string | null>(null);
  const [replay, setReplay] = useState<PurchaseReplayData | null>(null);
  const [isReplayOpen, setIsReplayOpen] = useState(false);
  const [isReplayLoading, setIsReplayLoading] = useState(false);
  const [replayError, setReplayError] = useState<string | null>(null);

  const [trace, setTrace] = useState<DecisionTraceData | null>(null);
  const [isTraceOpen, setIsTraceOpen] = useState(false);
  const [isTraceLoading, setIsTraceLoading] = useState(false);
  const [traceError, setTraceError] = useState<string | null>(null);

  const [isLabOpen, setIsLabOpen] = useState(false);
  const [labDecisionId, setLabDecisionId] = useState<string | null>(null);

  const prevIsAuthenticatedRef = useRef(isAuthenticated);

  // Centralised reset for every session-dependent piece of state.  Called when
  // the session changes (new session, logout, demo reset, auto-advance after
  // payment) so that no stale decision, trace, cart, or messages leak across
  // shopping decisions.
  const resetSessionState = useCallback(() => {
    setMessages([]);
    setCart(null);
    setCompletedOrder(null);
    setPaymentId(null);
    setPaymentProvider(undefined);
    setContract(null);
    setJourneyState(initialJourneyState);
    setIsProcessingPayment(false);
    setRazorpayCheckout(null);
    razorpayPaymentIdRef.current = null;
    razorpayCheckoutInProgressRef.current = false;
    // Decision / trace / lab state must also reset — they belong to the old
    // session's decision and must not carry over.
    setLabDecisionId(null);
    setIsLabOpen(false);
    setTrace(null);
    setIsTraceOpen(false);
    setTraceError(null);
    setIsTraceLoading(false);
  }, []);

  useEffect(() => {
    sessionIdRef.current = sessionId;
    if (sessionId) {
      sessionStorage.setItem('nexacart_session_id', sessionId);
    }
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId) {
      const newId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      setSessionId(newId);
    }
  }, []);

  useEffect(() => {
    const wasAuthenticated = prevIsAuthenticatedRef.current;
    prevIsAuthenticatedRef.current = isAuthenticated;

    if (wasAuthenticated && !isAuthenticated) {
      sessionStorage.removeItem('nexacart_session_id');
      const freshId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      setSessionId(freshId);
      resetSessionState();
    }
  }, [isAuthenticated, resetSessionState]);

  const traceRequestRef = useRef(0);
  const labRequestRef = useRef(0);

  const handleOpenReplay = async (targetSessionId?: string) => {
    const sid = targetSessionId ?? sessionId;
    if (!sid) return;
    setIsReplayOpen(true);
    setIsReplayLoading(true);
    setReplayError(null);
    setReplay(null);
    try {
      const data = await fetchPurchaseReplay(sid);
      setReplay(data);
    } catch (error: any) {
      const msg = error?.message || '';
      if (msg.includes('Failed to fetch') || msg.includes('NetworkError')) {
        setReplayError('Cannot reach the backend server. Please ensure the backend is running on port 8000.');
      } else {
        setReplayError(msg || 'Unable to load the purchase replay. Please try again.');
      }
    } finally {
      setIsReplayLoading(false);
    }
  };

  const handleOpenTrace = async (targetSessionId?: string) => {
    const sid = targetSessionId ?? sessionId;
    if (!sid) return;
    const reqId = ++traceRequestRef.current;
    setIsTraceOpen(true);
    setIsTraceLoading(true);
    setTraceError(null);
    setTrace(null);
    try {
      const data = await fetchDecisionTrace(sid);
      if (reqId !== traceRequestRef.current) return;
      setTrace(data);
    } catch (error: any) {
      if (reqId !== traceRequestRef.current) return;
      const msg = error?.message || '';
      if (msg.includes('Failed to fetch') || msg.includes('NetworkError')) {
        setTraceError('Cannot reach the backend server. Please ensure the backend is running on port 8000.');
      } else if (msg.includes('No decision trace')) {
        setTraceError('No decision trace yet for this session. Start a conversation or run the buyer agent first.');
      } else {
        setTraceError(msg || 'Unable to load the decision trace. Please try again.');
      }
    } finally {
      if (reqId === traceRequestRef.current) {
        setIsTraceLoading(false);
      }
    }
  };

  const handleCloseTrace = () => {
    setIsTraceOpen(false);
    setTraceError(null);
  };

  const handleOpenLab = async (targetSessionId?: string) => {
    const sid = targetSessionId ?? sessionId;
    if (!sid) return;
    const reqId = ++labRequestRef.current;
    try {
      const traceData = await fetchDecisionTrace(sid);
      if (reqId !== labRequestRef.current) return;
      if (traceData?.decision_id) {
        setLabDecisionId(traceData.decision_id);
        setIsLabOpen(true);
      }
    } catch (error) {
      if (reqId !== labRequestRef.current) return;
      console.error('Failed to get decision trace for Decision Lab:', error);
    }
  };

  const handleCloseLab = () => {
    setIsLabOpen(false);
  };

  const loadCart = async (sid?: string) => {
    const targetId = sid ?? sessionId;
    if (!targetId) return;
    try {
      const cartData = await fetchCart(targetId);
      if (sessionIdRef.current !== targetId) return;
      setCart(cartData);
    } catch (error) {
      if (sessionIdRef.current !== targetId) return;
      console.error('Failed to load cart:', error);
      setCart({
        cart_id: null,
        session_id: targetId,
        status: 'ACTIVE',
        items: [],
        total: 0,
        item_count: 0,
      });
    }
  };

  const loadContract = async (sid?: string) => {
    const targetId = sid ?? sessionId;
    if (!targetId) return;
    try {
      const contractData = await fetchContract(targetId);
      if (sessionIdRef.current !== targetId) return;
      setContract(contractData);
    } catch (error) {
      if (sessionIdRef.current !== targetId) return;
      console.error('Failed to load contract:', error);
      setContract(null);
    }
  };

  useEffect(() => {
    if (sessionId) {
      loadCart(sessionId);
      loadContract(sessionId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const handleContractSave = async (payload: Partial<CommerceContract>) => {
    if (!sessionId) return;
    setIsContractBusy(true);
    setContractError(null);
    try {
      let updated;
      if (contract?.id) {
        updated = await updateContract(sessionId, payload);
      } else {
        updated = await createContract(sessionId, payload);
      }
      setContract(updated);
    } catch (error: any) {
      const msg = error?.message || 'Failed to save contract';
      setContractError(msg);
      console.error('Failed to save contract:', error);
    } finally {
      setIsContractBusy(false);
    }
  };

  const handleContractActivate = async () => {
    if (!sessionId) return;
    setIsContractBusy(true);
    setContractError(null);
    try {
      if (!contract?.id) {
        const payload = {
          goal: contract?.goal ?? 'Buy wireless headphones',
          max_budget: undefined,
          currency: 'INR',
          required_categories: [],
          minimum_battery_hours: undefined,
          excluded_conditions: ['refurbished'],
          allowed_actions: [
            'search_products',
            'get_product_details',
            'compare_products',
            'recommend_product',
            'add_to_cart',
            'view_cart',
          ],
        };
        await createContract(sessionId, payload);
      }
      const updated = await activateContract(sessionId);
      setContract(updated);
      const activeMessage: ChatMessage = {
        id: (Date.now() + 9).toString(),
        role: 'assistant',
        content: '🛡️ Your AI Commerce Contract is now ACTIVE. I will follow these rules:\n\n' +
          (updated.max_budget != null ? `• Maximum budget: ₹${updated.max_budget.toLocaleString('en-IN')}\n` : '') +
          ((updated.required_categories ?? []).length > 0 ? `• Category: ${(updated.required_categories ?? []).join(', ')}\n` : '') +
          (updated.minimum_battery_hours != null ? `• Battery: at least ${updated.minimum_battery_hours} hours\n` : '') +
          '\nI cannot exceed these limits, and I can never approve payment or charge you directly.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, activeMessage]);
    } catch (error: any) {
      const msg = error?.message || 'Failed to activate contract';
      setContractError(msg);
      console.error('Failed to activate contract:', error);
    } finally {
      setIsContractBusy(false);
    }
  };

  const handleContractCancel = async () => {
    if (!sessionId) return;
    setIsContractBusy(true);
    setContractError(null);
    try {
      const updated = await cancelContract(sessionId);
      setContract(updated);
      const cancelMessage: ChatMessage = {
        id: (Date.now() + 10).toString(),
        role: 'assistant',
        content: 'Your AI Commerce Contract has been cancelled. I will no longer enforce these rules.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, cancelMessage]);
    } catch (error: any) {
      const msg = error?.message || 'Failed to cancel contract';
      setContractError(msg);
      console.error('Failed to cancel contract:', error);
    } finally {
      setIsContractBusy(false);
    }
  };

  const startNewPurchase = useCallback(() => {
    const newId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    setSessionId(newId);
    resetSessionState();
  }, [resetSessionState]);

  const handleSend = async (content: string) => {
    let activeSessionId = sessionId;

    if (cart?.status === 'PAID' || completedOrder) {
      activeSessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      setSessionId(activeSessionId);
      resetSessionState();
    }

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await fetchChat({ message: content, session_id: activeSessionId });
      setSessionId(response.session_id);

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.message,
        timestamp: new Date(),
        products: response.products,
        intent: response.intent,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      if (response.products && response.products.length > 0) {
        setJourneyState((prev) => ({
          ...prev,
          intent: 'completed',
          discovery: 'completed',
          decision: 'active',
        }));
      } else if (response.intent) {
        setJourneyState((prev) => ({
          ...prev,
          intent: 'completed',
          discovery: 'completed',
        }));
      }
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleProductSelect = useCallback(async (product: Product) => {
    setMessages((prev) => {
      const lastAssistantIndex = prev.findLastIndex(
        (m) => m.role === 'assistant' && m.products
      );
      if (lastAssistantIndex === -1) return prev;

      const updated = [...prev];
      updated[lastAssistantIndex] = {
        ...updated[lastAssistantIndex],
        selectedProductId: product.id,
      };
      return updated;
    });

    if (sessionId) {
      try {
        await addToCart(sessionId, product.id, 1);
        await loadCart();

        const cartMessage: ChatMessage = {
          id: (Date.now() + 2).toString(),
          role: 'assistant',
          content: `Added ${product.name} to your cart! You can view your cart or continue shopping.`,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, cartMessage]);

        setJourneyState((prev) => ({
          ...prev,
          decision: 'completed',
          cart: 'active',
        }));
      } catch (error) {
        console.error('Failed to add to cart:', error);
      }
    }
  }, [sessionId]);

  const handleRemoveItem = async (itemId: string) => {
    if (!sessionId) return;
    try {
      await removeCartItem(sessionId, itemId);
      await loadCart();
    } catch (error) {
      console.error('Failed to remove item:', error);
    }
  };

  const handleUpdateQuantity = async (itemId: string, quantity: number) => {
    if (!sessionId) return;
    try {
      await updateCartItem(sessionId, itemId, quantity);
      await loadCart();
    } catch (error) {
      console.error('Failed to update quantity:', error);
    }
  };

  const handleVerifyCart = async () => {
    if (!sessionId) return;
    setIsVerifying(true);
    try {
      const result = await verifyCart(sessionId);
      await loadCart();

      if (result.verified) {
        const verifyMessage: ChatMessage = {
          id: (Date.now() + 3).toString(),
          role: 'assistant',
          content: 'Your cart has been verified! All items are available and prices are correct. Would you like to proceed to checkout?',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, verifyMessage]);
      } else {
        const errorMessage: ChatMessage = {
          id: (Date.now() + 3).toString(),
          role: 'assistant',
          content: 'There was an issue verifying your cart. Some items may be out of stock or prices may have changed.',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      }
    } catch (error) {
      console.error('Failed to verify cart:', error);
    } finally {
      setIsVerifying(false);
    }
  };

  const handleRequestApproval = async () => {
    if (!sessionId) return;
    setIsRequestingApproval(true);
    try {
      const result = await requestCheckoutApproval(sessionId);
      await loadCart();

      if (result.success) {
        const approvalMessage: ChatMessage = {
          id: (Date.now() + 4).toString(),
          role: 'assistant',
          content: 'Your cart is ready for checkout! Please review the order summary and confirm to proceed to payment.',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, approvalMessage]);

        setJourneyState((prev) => ({
          ...prev,
          cart: 'completed',
          payment: 'active',
        }));
      }
    } catch (error) {
      console.error('Failed to request approval:', error);
    } finally {
      setIsRequestingApproval(false);
    }
  };

  const handleApproveCheckout = async () => {
    if (!sessionId) return;
    setIsApproving(true);
    try {
      const result = await approveCheckout(sessionId);
      await loadCart();

      if (result.success) {
        const paymentMessage: ChatMessage = {
          id: (Date.now() + 5).toString(),
          role: 'assistant',
          content: 'Your order has been approved! Click "Proceed to Payment" in the cart panel to complete your purchase.',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, paymentMessage]);
      }
    } catch (error) {
      console.error('Failed to approve checkout:', error);
    } finally {
      setIsApproving(false);
    }
  };

  const handleCreatePayment = async () => {
    if (!sessionId) return;

    // Guard against duplicate submissions (double-click / rapid retry). The
    // backend is the source of truth, but this prevents the user from firing
    // many overlapping create calls at once.
    if (paymentSubmitLockRef.current) return;
    paymentSubmitLockRef.current = true;

    setIsProcessingPayment(true);
    try {
      const result = await createPayment(sessionId);
      await loadCart();

      // Already paid: never open a new charge. Point the user at the order.
      if (result.already_completed) {
        setJourneyState((prev) => ({ ...prev, payment: 'completed' }));

        if (result.order_id) {
          const orderMessage: ChatMessage = {
            id: (Date.now() + 6).toString(),
            role: 'assistant',
            content: `This order has already been paid for (Order #${result.order_id}). You will not be charged again.`,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, orderMessage]);
        } else {
          const orderMessage: ChatMessage = {
            id: (Date.now() + 6).toString(),
            role: 'assistant',
            content: 'This order has already been paid for. You will not be charged again.',
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, orderMessage]);
        }

        if (sessionId) {
          try {
            const orders = await getOrders(sessionId);
            if (orders && orders.orders.length > 0) {
              setCompletedOrder(orders.orders[0]);
            }
          } catch (err) {
            console.error('Failed to load order:', err);
          }
        }
        return;
      }

      if (result.success) {
        setPaymentId(result.payment_id);
        setPaymentProvider(result.provider);

        if (result.resumed) {
          // Resume an existing PENDING/PROCESSING payment instead of starting a
          // fresh one. Reuse the same Razorpay order when available.
          if (result.provider === 'razorpay' && result.razorpay_order_id) {
            const scriptLoaded = await loadRazorpayScript();
            if (!scriptLoaded) {
              throw new Error('Failed to load Razorpay checkout. Please try again.');
            }

            setRazorpayCheckout({
              orderId: result.razorpay_order_id,
              keyId: result.razorpay_key_id!,
              amount: result.amount,
              currency: result.currency,
            });

            const paymentMessage: ChatMessage = {
              id: (Date.now() + 6).toString(),
              role: 'assistant',
              content: `Resuming your previous payment of ₹${result.amount}. Opening Razorpay checkout...`,
              timestamp: new Date(),
            };
            setMessages((prev) => [...prev, paymentMessage]);
          } else {
            const paymentMessage: ChatMessage = {
              id: (Date.now() + 6).toString(),
              role: 'assistant',
              content: `Resuming your previous payment (Payment ID: ${result.payment_id}). Click "Confirm Payment" to complete the simulated payment.`,
              timestamp: new Date(),
            };
            setMessages((prev) => [...prev, paymentMessage]);
          }
          return;
        }

        if (result.provider === 'razorpay' && result.razorpay_order_id) {
          const scriptLoaded = await loadRazorpayScript();
          if (!scriptLoaded) {
            throw new Error('Failed to load Razorpay checkout. Please try again.');
          }

          setRazorpayCheckout({
            orderId: result.razorpay_order_id,
            keyId: result.razorpay_key_id!,
            amount: result.amount,
            currency: result.currency,
          });

          const paymentMessage: ChatMessage = {
            id: (Date.now() + 6).toString(),
            role: 'assistant',
            content: `Payment of ₹${result.amount} ready. Opening Razorpay checkout...`,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, paymentMessage]);
        } else {
          const paymentMessage: ChatMessage = {
            id: (Date.now() + 6).toString(),
            role: 'assistant',
            content: `Payment initiated! Payment ID: ${result.payment_id}. Click "Confirm Payment" to complete the simulated payment.`,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, paymentMessage]);
        }
      }
    } catch (error) {
      console.error('Failed to create payment:', error);
      const errorMessage: ChatMessage = {
        id: (Date.now() + 6).toString(),
        role: 'assistant',
        content: (error as Error)?.message || 'Failed to create payment. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsProcessingPayment(false);
      paymentSubmitLockRef.current = false;
    }
  };

  const handleConfirmPayment = async () => {
    if (!paymentId) return;
    setIsProcessingPayment(true);
    try {
      const result = await confirmPayment(paymentId);
      await loadCart();

      if (result.success) {
        const successMessage: ChatMessage = {
          id: (Date.now() + 7).toString(),
          role: 'assistant',
          content: 'Payment successful! Your order has been confirmed. Thank you for shopping with NexaCart!',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, successMessage]);

        setJourneyState((prev) => ({
          ...prev,
          payment: 'completed',
        }));

        setPaymentId(null);
        setPaymentProvider(undefined);

        if (sessionId) {
          try {
            const orders = await getOrders(sessionId);
            if (orders && orders.orders.length > 0) {
              setCompletedOrder(orders.orders[0]);
            }
          } catch (err) {
            console.error('Failed to load order after payment:', err);
          }
        }
      }
    } catch (error) {
      console.error('Failed to confirm payment:', error);
      const errorMessage: ChatMessage = {
        id: (Date.now() + 7).toString(),
        role: 'assistant',
        content: 'Payment failed. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsProcessingPayment(false);
    }
  };

  const handleRetryRazorpay = async () => {
    if (!sessionId) return;
    // Reset the submit lock so handleCreatePayment can run again
    paymentSubmitLockRef.current = false;
    razorpayCheckoutInProgressRef.current = false;
    await handleCreatePayment();
  };

  const handleRazorpayCheckout = async () => {
    const currentPaymentId = razorpayPaymentIdRef.current;
    if (!razorpayCheckout || !currentPaymentId) return;
    if (razorpayCheckoutInProgressRef.current) return;
    razorpayCheckoutInProgressRef.current = true;
    setIsProcessingPayment(true);

    try {
      const result = await openRazorpayCheckout({
        key: razorpayCheckout.keyId,
        amount: razorpayCheckout.amount * 100,
        currency: razorpayCheckout.currency,
        name: 'NexaCart',
        description: 'Purchase from NexaCart',
        order_id: razorpayCheckout.orderId,
        handler: async (paymentResponse) => {
          try {
            const verifyResult = await verifyRazorpayPayment(currentPaymentId, {
              razorpay_order_id: paymentResponse.razorpay_order_id,
              razorpay_payment_id: paymentResponse.razorpay_payment_id,
              razorpay_signature: paymentResponse.razorpay_signature,
            });

            await loadCart();

            if (verifyResult.success) {
              const successMessage: ChatMessage = {
                id: (Date.now() + 7).toString(),
                role: 'assistant',
                content: 'Payment verified successfully! Your order has been confirmed. Thank you for shopping with NexaCart!',
                timestamp: new Date(),
              };
              setMessages((prev) => [...prev, successMessage]);

              setJourneyState((prev) => ({
                ...prev,
                payment: 'completed',
              }));

        setPaymentId(null);
        setPaymentProvider(undefined);
        setRazorpayCheckout(null);
        razorpayCheckoutInProgressRef.current = false;

              if (sessionId) {
                try {
                  const orders = await getOrders(sessionId);
                  if (orders && orders.orders.length > 0) {
                    setCompletedOrder(orders.orders[0]);
                  }
                } catch (err) {
                  console.error('Failed to load order after payment:', err);
                }
              }
            }
          } catch (verifyError: any) {
            console.error('Payment verification failed:', verifyError);
            const errorMessage: ChatMessage = {
              id: (Date.now() + 7).toString(),
              role: 'assistant',
              content: verifyError?.message || 'Payment verification failed. Please contact support.',
              timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorMessage]);
            setRazorpayCheckout(null);
            razorpayCheckoutInProgressRef.current = false;
          } finally {
            setIsProcessingPayment(false);
          }
        },
        modal: {
          ondismiss: () => {
            setIsProcessingPayment(false);
            razorpayCheckoutInProgressRef.current = false;
            setRazorpayCheckout(null);
            const dismissMessage: ChatMessage = {
              id: (Date.now() + 7).toString(),
              role: 'assistant',
              content: 'Payment cancelled. You can retry when ready.',
              timestamp: new Date(),
            };
            setMessages((prev) => [...prev, dismissMessage]);
          },
        },
      });

      if (result.dismissed) {
        setIsProcessingPayment(false);
        razorpayCheckoutInProgressRef.current = false;
      }
    } catch (error: any) {
      console.error('Razorpay checkout error:', error);
      const errorMessage: ChatMessage = {
        id: (Date.now() + 7).toString(),
        role: 'assistant',
        content: error?.message || 'Failed to open payment checkout. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      setRazorpayCheckout(null);
      setIsProcessingPayment(false);
      razorpayCheckoutInProgressRef.current = false;
    }
  };

  useEffect(() => {
    if (razorpayCheckout && paymentId) {
      razorpayPaymentIdRef.current = paymentId;
      handleRazorpayCheckout();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [razorpayCheckout, paymentId]);

  const handleCancelPayment = async () => {
    if (!paymentId) return;
    try {
      await cancelPayment(paymentId);
      setPaymentId(null);
      await loadCart();

      const cancelMessage: ChatMessage = {
        id: (Date.now() + 8).toString(),
        role: 'assistant',
        content: 'Payment cancelled.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, cancelMessage]);
    } catch (error) {
      console.error('Failed to cancel payment:', error);
    }
  };

  const handleCloseOrderSuccess = () => {
    setCompletedOrder(null);
  };

  const [demoResetKey, setDemoResetKey] = useState(0);

  const handleResetDemo = useCallback(() => {
    const newId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    setSessionId(newId);
    resetSessionState();
    setDemoResetKey((k) => k + 1);
  }, [resetSessionState]);

  const handleNavigate = (view: ViewType) => {
    if (!isAuthenticated) {
      if (view === 'assistant' || view === 'orders' || view === 'buyer' || view === 'cart') {
        setAuthNotice(
          view === 'cart'
            ? 'Please log in to access your cart.'
            : view === 'assistant'
            ? 'Please log in to continue shopping with AI.'
            : view === 'buyer'
            ? 'Please log in to run the autonomous Buyer Agent.'
            : 'Please log in to view your orders.'
        );
        setTargetAfterAuth(view);
        setCurrentView('login');
        return;
      }
    } else {
      // Authenticated users enter the commerce workflow directly
      if (view === 'home' || view === 'discover') {
        setCurrentView('assistant');
        return;
      }
      if (view === 'cart') {
        window.location.href = '/cart';
        return;
      }
    }
    setAuthNotice(null);
    setCurrentView(view);
  };

  const handleProtectedCartClick = () => {
    if (!isAuthenticated) {
      setAuthNotice('Please log in to access your cart and proceed to checkout.');
      setTargetAfterAuth('cart');
      setCurrentView('login');
      return;
    }
    window.location.href = '/cart';
  };

  const handleProtectedContractClick = () => {
    if (!isAuthenticated) {
      setAuthNotice('Please log in to configure your AI Commerce Contract.');
      setTargetAfterAuth('contract');
      setCurrentView('login');
      return;
    }
    setIsContractOpen(true);
  };

  const handleProtectedReplayClick = (targetSessionId?: string) => {
    if (!isAuthenticated) {
      setAuthNotice('Please log in to view purchase replays.');
      setTargetAfterAuth('replay');
      setCurrentView('login');
      return;
    }
    handleOpenReplay(targetSessionId);
  };

  const handleProtectedLabClick = (targetSessionId?: string) => {
    if (!isAuthenticated) {
      setAuthNotice('Please log in to explore the AI Decision Lab.');
      setCurrentView('login');
      return;
    }
    handleOpenLab(targetSessionId);
  };

  const handleAuthSuccess = () => {
    setAuthNotice(null);
    const target = targetAfterAuth;
    setTargetAfterAuth(null);

    if (target === 'cart') {
      window.location.href = '/cart';
    } else if (target === 'contract') {
      setIsContractOpen(true);
      setCurrentView('assistant');
    } else if (target === 'replay') {
      handleOpenReplay();
      setCurrentView('assistant');
    } else if (target === 'orders') {
      setCurrentView('orders');
    } else if (target === 'buyer') {
      setCurrentView('buyer');
    } else {
      setCurrentView('assistant');
    }
  };

  const handleAddToCart = async (productId: string) => {
    if (!isAuthenticated) {
      setAuthNotice('Please log in to add items to your cart.');
      setTargetAfterAuth('cart');
      setCurrentView('login');
      return;
    }

    if (sessionId) {
      try {
        await addToCart(sessionId, productId, 1);
        await loadCart();
        setIsCartOpen(true);
      } catch (error) {
        console.error('Failed to add to cart:', error);
      }
    }
  };

  return (
    <div className="flex flex-col h-screen bg-arctic-soft overflow-hidden">
      <Header 
        cart={cart} 
        currentView={currentView}
        onNavigate={handleNavigate}
        onCartClick={handleProtectedCartClick} 
        onContractClick={handleProtectedContractClick} 
        onResetDemo={handleResetDemo}
        contract={contract}
      />
      
      <div className="flex flex-1 overflow-hidden">
        {currentView === 'home' && (
          <HomeView onNavigate={handleNavigate} />
        )}
        
        {currentView === 'discover' && (
          <DiscoverView onAddToCart={handleAddToCart} />
        )}
        
        {currentView === 'assistant' && (
          <AssistantView 
            messages={messages} 
            isLoading={isLoading} 
            journeyState={journeyState} 
            onSend={handleSend} 
            onProductSelect={handleProductSelect} 
          />
        )}
        
        {currentView === 'orders' && (
          <OrdersView 
            sessionId={sessionId} 
            onReplayClick={handleProtectedReplayClick} 
          />
        )}

        {currentView === 'buyer' && (
          <BuyerAgentView
            key={demoResetKey}
            sessionId={sessionId}
            onNavigateToCart={() => { loadCart(); window.location.href = '/cart'; }}
            onOpenReplay={handleProtectedReplayClick}
            onOpenTrace={() => handleOpenTrace()}
            onOpenLab={() => handleOpenLab()}
            onDecisionCreated={(decisionId) => {
              setLabDecisionId(decisionId);
            }}
          />
        )}

        {currentView === 'cart' && (
          <div className="flex-1 overflow-y-auto">
            {/* Cart page is rendered via /cart route - this is a fallback for SPA navigation */}
            <div className="flex flex-col items-center justify-center h-full py-20 text-center space-y-4">
              <div className="w-16 h-16 bg-white border border-slopes/30 rounded-2xl flex items-center justify-center mx-auto text-3xl shadow-2xs">
                🛒
              </div>
              <div>
                <h2 className="text-lg font-bold text-midnight">Loading Cart…</h2>
                <p className="text-sm text-apres mt-1">Redirecting to your cart page.</p>
              </div>
            </div>
          </div>
        )}

        {currentView === 'login' && (
          <LoginView 
            onNavigate={setCurrentView as (view: 'home' | 'discover' | 'assistant' | 'orders' | 'login' | 'register') => void}
            notice={authNotice}
            onSuccessRedirect={handleAuthSuccess}
          />
        )}

        {currentView === 'register' && (
          <RegisterView 
            onNavigate={setCurrentView as (view: 'home' | 'discover' | 'assistant' | 'orders' | 'login' | 'register') => void}
            notice={authNotice}
            onSuccessRedirect={handleAuthSuccess}
          />
        )}
      </div>

      <CartPanel
        cart={cart}
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        onRemoveItem={handleRemoveItem}
        onUpdateQuantity={handleUpdateQuantity}
        onVerifyCart={handleVerifyCart}
        onRequestApproval={handleRequestApproval}
        onApproveCheckout={handleApproveCheckout}
        onCreatePayment={handleCreatePayment}
        onConfirmPayment={handleConfirmPayment}
        onCancelPayment={handleCancelPayment}
        onRetryRazorpay={handleRetryRazorpay}
        isVerifying={isVerifying}
        isRequestingApproval={isRequestingApproval}
        isApproving={isApproving}
        isProcessingPayment={isProcessingPayment}
        paymentId={paymentId}
        paymentProvider={paymentProvider}
        onReplay={() => handleOpenReplay()}
      />
      <AICommerceContractPanel
        contract={contract}
        isOpen={isContractOpen}
        onClose={() => { setIsContractOpen(false); setContractError(null); }}
        onSave={handleContractSave}
        onActivate={handleContractActivate}
        onCancel={handleContractCancel}
        isBusy={isContractBusy}
        error={contractError}
      />
      {completedOrder && (
        <div className="fixed inset-0 bg-black/50 z-40 flex items-center justify-center p-4 overflow-y-auto">
          <div className="w-full max-w-md max-h-[90vh] overflow-y-auto">
            <OrderSuccess
              order={completedOrder}
              onClose={handleCloseOrderSuccess}
              onReplay={() => handleOpenReplay()}
              onTrace={() => handleOpenTrace()}
            />
          </div>
        </div>
      )}
      <PurchaseReplay
        replay={replay}
        isLoading={isReplayLoading}
        isOpen={isReplayOpen}
        onClose={() => setIsReplayOpen(false)}
        error={replayError}
      />
      <DecisionTracePanel
        trace={trace}
        isLoading={isTraceLoading}
        isOpen={isTraceOpen}
        error={traceError}
        onClose={handleCloseTrace}
        onOpenReplay={() => { setIsTraceOpen(false); handleOpenReplay(); }}
      />
      <DecisionLabPanel
        decisionId={labDecisionId}
        sessionId={sessionId}
        isOpen={isLabOpen}
        onClose={handleCloseLab}
        onApplied={() => {
          loadCart();
          setIsCartOpen(true);
        }}
      />
    </div>
  );
}
