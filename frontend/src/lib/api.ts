import { ChatRequest, ChatResponse, Product, Cart, Payment, Order, CommerceContract, ContractCheckResult, PurchaseReplayData, User, AuthResponse, LoginCredentials, RegisterCredentials, BuyerAgentRunResult, DecisionTraceData, DecisionLabExplanation, DecisionLabAlternatives, DecisionLabCompareResult, SimulationResult, SimulationSummary, ApplySimulationResult, SimulationConstraint } from './types';
import { API_BASE_URL } from './constants';

export async function fetchChat(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error('Failed to send message');
  }

  return response.json();
}

export async function fetchProducts(): Promise<Product[]> {
  const response = await fetch(`${API_BASE_URL}/api/products`);

  if (!response.ok) {
    throw new Error('Failed to fetch products');
  }

  return response.json();
}

export async function fetchHealth(): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE_URL}/health`);

  if (!response.ok) {
    throw new Error('Health check failed');
  }

  return response.json();
}

export async function fetchCart(sessionId: string): Promise<Cart> {
  const response = await fetch(`${API_BASE_URL}/api/cart/${sessionId}`);

  if (!response.ok) {
    throw new Error('Failed to fetch cart');
  }

  return response.json();
}

export async function addToCart(
  sessionId: string,
  productId: string,
  quantity: number = 1
): Promise<{ success: boolean; cart_total: number; cart_item_count: number }> {
  const response = await fetch(`${API_BASE_URL}/api/cart/${sessionId}/items`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ product_id: productId, quantity }),
  });

  if (!response.ok) {
    throw new Error('Failed to add item to cart');
  }

  return response.json();
}

export async function updateCartItem(
  sessionId: string,
  itemId: string,
  quantity: number
): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE_URL}/api/cart/${sessionId}/items/${itemId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ quantity }),
  });

  if (!response.ok) {
    throw new Error('Failed to update cart item');
  }

  return response.json();
}

export async function removeCartItem(
  sessionId: string,
  itemId: string
): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE_URL}/api/cart/${sessionId}/items/${itemId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error('Failed to remove cart item');
  }

  return response.json();
}

export async function clearCart(sessionId: string): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE_URL}/api/cart/${sessionId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error('Failed to clear cart');
  }

  return response.json();
}

export async function verifyCart(sessionId: string): Promise<{ verified: boolean; total: number }> {
  const response = await fetch(`${API_BASE_URL}/api/cart/${sessionId}/verify`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error('Failed to verify cart');
  }

  return response.json();
}

export async function requestCheckoutApproval(
  sessionId: string
): Promise<{ success: boolean; status: string }> {
  const response = await fetch(`${API_BASE_URL}/api/cart/${sessionId}/request-approval`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error('Failed to request checkout approval');
  }

  return response.json();
}

export async function approveCheckout(
  sessionId: string
): Promise<{ success: boolean; status: string }> {
  const response = await fetch(`${API_BASE_URL}/api/cart/${sessionId}/approve`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error('Failed to approve checkout');
  }

  return response.json();
}

export async function createPayment(
  sessionId: string
): Promise<{
  success: boolean;
  payment_id: string;
  amount: number;
  currency: string;
  status: string;
  provider?: string;
  razorpay_order_id?: string;
  razorpay_key_id?: string;
  resumed?: boolean;
  already_completed?: boolean;
  order_id?: string;
}> {
  const response = await fetch(`${API_BASE_URL}/api/payment/create?session_id=${sessionId}`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create payment');
  }

  return response.json();
}

export async function confirmPayment(
  paymentId: string
): Promise<{ success: boolean; payment_id: string; status: string; amount: number; currency: string }> {
  const response = await fetch(`${API_BASE_URL}/api/payment/${paymentId}/confirm`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to confirm payment');
  }

  return response.json();
}

export async function verifyRazorpayPayment(
  paymentId: string,
  payload: {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
  }
): Promise<{ success: boolean; payment_id: string; status: string; amount: number; currency: string }> {
  const response = await fetch(`${API_BASE_URL}/api/payment/${paymentId}/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to verify payment');
  }

  return response.json();
}

export async function cancelPayment(
  paymentId: string
): Promise<{ success: boolean; payment_id: string; status: string }> {
  const response = await fetch(`${API_BASE_URL}/api/payment/${paymentId}/cancel`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to cancel payment');
  }

  return response.json();
}

export async function getPayment(
  paymentId: string
): Promise<Payment> {
  const response = await fetch(`${API_BASE_URL}/api/payment/${paymentId}`);

  if (!response.ok) {
    throw new Error('Failed to fetch payment');
  }

  return response.json();
}

export async function getOrders(
  sessionId?: string,
  token?: string | null
): Promise<{ orders: Order[]; count: number }> {
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const url = sessionId
    ? `${API_BASE_URL}/api/orders?session_id=${sessionId}`
    : `${API_BASE_URL}/api/orders`;

  const response = await fetch(url, { headers });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch orders');
  }

  return response.json();
}

export async function getOrder(
  orderId: string,
  token?: string | null
): Promise<Order> {
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}/api/orders/${orderId}`, { headers });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch order');
  }

  return response.json();
}

export async function fetchContract(sessionId: string): Promise<CommerceContract> {
  const response = await fetch(`${API_BASE_URL}/api/contracts/${sessionId}`);

  if (!response.ok) {
    throw new Error('Failed to fetch contract');
  }

  return response.json();
}

export async function createContract(
  sessionId: string,
  payload: Partial<CommerceContract>
): Promise<CommerceContract> {
  const response = await fetch(`${API_BASE_URL}/api/contracts/${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create contract');
  }

  return response.json();
}

export async function updateContract(
  sessionId: string,
  payload: Partial<CommerceContract>
): Promise<CommerceContract> {
  const response = await fetch(`${API_BASE_URL}/api/contracts/${sessionId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update contract');
  }

  return response.json();
}

export async function activateContract(sessionId: string): Promise<CommerceContract> {
  const response = await fetch(`${API_BASE_URL}/api/contracts/${sessionId}/activate`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to activate contract');
  }

  return response.json();
}

export async function cancelContract(sessionId: string): Promise<CommerceContract> {
  const response = await fetch(`${API_BASE_URL}/api/contracts/${sessionId}/cancel`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to cancel contract');
  }

  return response.json();
}

export async function checkContractAction(
  sessionId: string,
  action: string,
  opts: { product_id?: string; max_price?: number; category?: string } = {}
): Promise<ContractCheckResult> {
  const response = await fetch(`${API_BASE_URL}/api/contracts/${sessionId}/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, ...opts }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to check contract action');
  }

  return response.json();
}

export async function fetchPurchaseReplay(sessionId: string): Promise<PurchaseReplayData> {
  const response = await fetch(`${API_BASE_URL}/api/replay/${sessionId}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch purchase replay');
  }

  return response.json();
}

export async function fetchOrderReplay(orderId: string): Promise<PurchaseReplayData> {
  const response = await fetch(`${API_BASE_URL}/api/replay/order/${orderId}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch order replay');
  }

  return response.json();
}

export async function fetchDecisionTrace(sessionId: string): Promise<DecisionTraceData> {
  const response = await fetch(`${API_BASE_URL}/api/decision-traces/session/${sessionId}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch decision trace');
  }

  return response.json();
}

export async function fetchDecisionTraceByDecisionId(decisionId: string): Promise<DecisionTraceData> {
  const response = await fetch(`${API_BASE_URL}/api/decision-traces/${decisionId}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch decision trace');
  }

  return response.json();
}

export async function fetchDecisionTraceByOrder(orderId: string): Promise<DecisionTraceData> {
  const response = await fetch(`${API_BASE_URL}/api/decision-traces/order/${orderId}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch decision trace for order');
  }

  return response.json();
}

export async function registerUser(credentials: RegisterCredentials): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Registration failed');
  }

  return response.json();
}

export async function loginUser(credentials: LoginCredentials): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Login failed');
  }

  return response.json();
}

export async function fetchMe(token: string): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to fetch user profile');
  }

  return response.json();
}

export async function logoutUser(token: string): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    return { success: true };
  }

  return response.json();
}

export async function runBuyerAgent(
  goal: string,
  sessionId?: string,
  approveProductId?: string,
  autoApprove: boolean = false,
  runId?: string
): Promise<BuyerAgentRunResult> {
  const response = await fetch(`${API_BASE_URL}/buyer-agent/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      goal,
      session_id: sessionId,
      approve_product_id: approveProductId,
      auto_approve: autoApprove,
      run_id: runId,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to run buyer agent');
  }

  return response.json();
}

// ─── Decision Lab API ───────────────────────────────────────
export async function fetchDecisionLabExplanation(decisionId: string): Promise<DecisionLabExplanation> {
  const response = await fetch(`${API_BASE_URL}/api/decision-lab/${decisionId}/explain`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to fetch recommendation explanation');
  }
  return response.json();
}

export async function fetchDecisionLabAlternatives(decisionId: string, limit: number = 5): Promise<DecisionLabAlternatives> {
  const response = await fetch(`${API_BASE_URL}/api/decision-lab/${decisionId}/alternatives?limit=${limit}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to fetch alternatives');
  }
  return response.json();
}

export async function compareProducts(productAId: string, productBId: string): Promise<DecisionLabCompareResult> {
  const response = await fetch(`${API_BASE_URL}/api/decision-lab/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_a_id: productAId, product_b_id: productBId }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to compare products');
  }
  return response.json();
}

export async function runSimulation(
  decisionId: string,
  payload: {
    session_id: string;
    label?: string;
    max_price?: number;
    min_price?: number;
    category?: string;
    brand?: string;
    constraints?: SimulationConstraint[];
  }
): Promise<SimulationResult> {
  const response = await fetch(`${API_BASE_URL}/api/decision-lab/${decisionId}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to run simulation');
  }
  return response.json();
}

export async function applySimulation(simulationId: string, sessionId: string): Promise<ApplySimulationResult> {
  const response = await fetch(`${API_BASE_URL}/api/decision-lab/simulations/${simulationId}/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to apply simulation');
  }
  return response.json();
}

export async function fetchSimulations(decisionId: string): Promise<SimulationSummary[]> {
  const response = await fetch(`${API_BASE_URL}/api/decision-lab/${decisionId}/simulations`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to fetch simulations');
  }
  return response.json();
}
