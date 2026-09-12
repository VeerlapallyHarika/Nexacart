declare global {
  interface Window {
    Razorpay: any;
  }
}

export interface RazorpayCheckoutOptions {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description: string;
  order_id: string;
  handler: (response: RazorpayCheckoutResponse) => void;
  prefill?: {
    name?: string;
    email?: string;
    contact?: string;
  };
  theme?: {
    color?: string;
  };
  modal?: {
    ondismiss?: () => void;
  };
}

export interface RazorpayCheckoutResponse {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export interface RazorpayCheckoutResult {
  dismissed: boolean;
  response?: RazorpayCheckoutResponse;
}

let razorpayScriptLoaded = false;
let razorpayScriptPromise: Promise<boolean> | null = null;

export function loadRazorpayScript(): Promise<boolean> {
  if (razorpayScriptLoaded) {
    return Promise.resolve(true);
  }

  if (razorpayScriptPromise) {
    return razorpayScriptPromise;
  }

  razorpayScriptPromise = new Promise((resolve) => {
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.onload = () => {
      razorpayScriptLoaded = true;
      resolve(true);
    };
    script.onerror = () => {
      razorpayScriptPromise = null;
      resolve(false);
    };
    document.body.appendChild(script);
  });

  return razorpayScriptPromise;
}

export function openRazorpayCheckout(options: RazorpayCheckoutOptions): Promise<RazorpayCheckoutResult> {
  return new Promise((resolve, reject) => {
    if (!window.Razorpay) {
      reject(new Error('Razorpay SDK not loaded'));
      return;
    }

    let settled = false;

    const rzp = new window.Razorpay({
      key: options.key,
      amount: options.amount,
      currency: options.currency,
      name: options.name,
      description: options.description,
      order_id: options.order_id,
      handler: (response: RazorpayCheckoutResponse) => {
        if (settled) return;
        settled = true;
        if (options.handler) {
          options.handler(response);
        }
        resolve({ dismissed: false, response });
      },
      prefill: options.prefill,
      theme: options.theme,
    });

    rzp.on('payment.failed', (response: { error: { description: string } }) => {
      if (settled) return;
      settled = true;
      reject(new Error(response.error?.description || 'Payment failed'));
    });

    rzp.on('payment.dismiss', () => {
      if (settled) return;
      settled = true;
      if (options.modal?.ondismiss) {
        options.modal.ondismiss();
      }
      resolve({ dismissed: true });
    });

    rzp.open();
  });
}
