export interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  currency: string;
  category: string;
  attributes: Record<string, any>;
  stock_quantity: number;
}

export interface Intent {
  category: string | null;
  max_price: number | null;
  min_battery_life: number | null;
  noise_cancellation: boolean | null;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  products?: Product[];
  intent?: Intent;
  selectedProductId?: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  message: string;
  session_id: string;
  intent?: Intent;
  products?: Product[];
}

export interface CartItem {
  id: string;
  product_id: string;
  product_name: string;
  description?: string;
  price: number;
  currency: string;
  quantity: number;
  subtotal: number;
  stock_quantity?: number;
  attributes?: Record<string, any>;
}

export interface Cart {
  cart_id: string | null;
  session_id: string;
  status: string;
  items: CartItem[];
  total: number;
  item_count: number;
  created_at?: string;
  updated_at?: string;
}

export type PaymentStatus = 'PENDING' | 'PROCESSING' | 'SUCCESS' | 'FAILED' | 'CANCELLED';

export interface Payment {
  payment_id: string;
  session_id: string;
  cart_id: string;
  amount: number;
  currency: string;
  payment_method: string;
  status: PaymentStatus;
  provider: string;
  provider_payment_id?: string;
  created_at?: string;
  updated_at?: string;
}

export interface OrderItem {
  id: string;
  product_id: string;
  product_name: string;
  price_at_purchase: number;
  quantity: number;
  subtotal: number;
}

export type OrderStatus = 'CREATED' | 'CONFIRMED' | 'CANCELLED';

export interface Order {
  order_id: string;
  session_id: string;
  cart_id: string;
  payment_id: string;
  total_amount: number;
  currency: string;
  status: OrderStatus;
  items: OrderItem[];
  payment_status?: PaymentStatus;
  created_at?: string;
  updated_at?: string;
}

export type JourneyStage = 'pending' | 'active' | 'completed';

export interface JourneyState {
  intent: JourneyStage;
  discovery: JourneyStage;
  decision: JourneyStage;
  cart: JourneyStage;
  payment: JourneyStage;
}

export type ContractStatus = 'DRAFT' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED';

export interface ContractViolation {
  rule: string;
  message: string;
}

export interface ContractCheckResult {
  allowed: boolean;
  violations: ContractViolation[];
  contract_active: boolean;
}

export interface CommerceContract {
  id: string | null;
  session_id: string;
  status: ContractStatus;
  goal: string | null;
  max_budget: number | null;
  currency: string;
  required_categories: string[];
  required_attributes: Record<string, any>;
  minimum_battery_hours: number | null;
  excluded_conditions: string[];
  allowed_actions: string[];
  created_at?: string;
  updated_at?: string;
}

export type ReplayStatus = 'IN_PROGRESS' | 'COMPLETED' | 'BLOCKED' | 'CANCELLED';

export type ReplayStepType =
  | 'INTENT'
  | 'DISCOVERY'
  | 'CONTRACT_CREATED'
  | 'CONTRACT_CHECK'
  | 'CONTRACT_VIOLATION'
  | 'COMPARISON'
  | 'DECISION'
  | 'CART_ADD'
  | 'CART_UPDATE'
  | 'CART_VERIFIED'
  | 'CHECKOUT_APPROVAL'
  | 'PAYMENT_INITIATED'
  | 'PAYMENT_CONFIRMED'
  | 'ORDER_CONFIRMED'
  | 'PURCHASE_COMPLETE'
  | 'AGENT_GOAL'
  | 'AGENT_RECOMMENDATION';

export interface ReplayStep {
  step: number;
  type: ReplayStepType;
  title: string;
  description: string;
  status: string;
  timestamp?: string;
}

export interface PurchaseReplayData {
  session_id: string;
  status: ReplayStatus;
  total_steps: number;
  steps: ReplayStep[];
  order_id?: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  created_at?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials {
  name: string;
  email: string;
  password: string;
}

export interface BuyerAgentAction {
  step: number;
  action: string;
  input: Record<string, any>;
  output: Record<string, any>;
  timestamp: string;
}

export type BuyerAgentFinalState =
  | 'recommendation_ready'
  | 'ready_for_approval'
  | 'blocked_by_contract'
  | 'max_steps_reached'
  | 'no_matching_products'
  | 'error';

export interface BuyerAgentRunResult {
  run_id: string;
  session_id: string;
  decision_id: string | null;
  goal: string;
  final_state: BuyerAgentFinalState;
  reason: string | null;
  added_product_id: string | null;
  recommended_product_id?: string | null;
  actions: BuyerAgentAction[];
}

// ── Commerce Decision Trace ───────────────────────────────────────────────

export type TraceStatus = 'IN_PROGRESS' | 'COMPLETED' | 'INTERRUPTED' | 'FAILED';

export type TraceActor = 'ai' | 'user' | 'system';

export type TraceEventStatus = 'SUCCESS' | 'PENDING' | 'WARNING' | 'ERROR';

export interface DecisionTraceEvent {
  event_type: string;
  registry_type: string;
  actor: TraceActor;
  status: TraceEventStatus;
  title: string;
  summary: string;
  explanation: Record<string, any> | null;
  ref_audit_event_id: number;
}

export interface DecisionTraceData {
  decision_id: string;
  session_id: string;
  status: TraceStatus;
  goal: string | null;
  summary: string;
  links: {
    product_id: string | null;
    cart_id: string | null;
    payment_id: string | null;
    order_id: string | null;
    user_id: string | null;
  };
  events: DecisionTraceEvent[];
  created_at?: string;
  updated_at?: string;
}

// ─── Decision Lab Types ─────────────────────────────────────
export interface DecisionLabExplanation {
  decision_id: string;
  product: Product;
  match_percentage: number;
  raw_score: number;
  breakdown: Record<string, any>;
  strong_matches: string[];
  trade_offs: string[];
  total_candidates_scanned: number;
  total_candidates_ranked: number;
  contract: { active: boolean; max_budget?: number; passed?: boolean } | null;
}

export interface DecisionLabAlternative {
  id: string;
  name: string;
  price: number;
  currency: string;
  category: string;
  attributes: Record<string, any>;
  stock_quantity: number;
  match_percentage: number;
  score: number;
}

export interface DecisionLabAlternatives {
  decision_id: string;
  original_product: Product;
  alternatives: DecisionLabAlternative[];
  total_candidates: number;
  match_type: string;
}

export interface ProductComparison {
  attribute: string;
  label: string;
  a_value: any;
  b_value: any;
  a_display: string;
  b_display: string;
  verdict: 'similar' | 'a_better' | 'b_better' | 'tradeoff';
  summary: string;
}

export interface DecisionLabCompareResult {
  product_a: Product;
  product_b: Product;
  comparisons: ProductComparison[];
  overall_a_match: number;
  overall_b_match: number;
}

export interface SimulationConstraint {
  key: string;
  value: any;
  operator: string;
}

export interface SimulationResult {
  simulation_id: string;
  decision_id: string;
  simulation_number: number;
  label: string;
  original_constraints: Record<string, any>;
  modified_constraints: Record<string, any>;
  result: {
    original_product: Product | null;
    simulated_product: (Product & { match_percentage?: number; score?: number }) | null;
    alternatives: any[];
    changes: string[];
    total_candidates: number;
    match_type: string;
  };
  contract_warnings: string[];
  contract: { active: boolean; recommendation_blocked?: boolean };
  status: string;
  created_at: string;
}

export interface SimulationSummary {
  simulation_id: string;
  simulation_number: number;
  label: string;
  status: string;
  result_summary: {
    original_product: Product | null;
    simulated_product: (Product & { match_percentage?: number; score?: number }) | null;
    changes: string[];
  };
  contract_warnings: string[];
  created_at: string;
}

export interface ApplySimulationResult {
  success: boolean;
  simulation_id: string;
  product: Product;
  message: string;
}
