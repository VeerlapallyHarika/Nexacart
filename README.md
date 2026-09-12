# 🛒 NexaCart

**NexaCart** is an **AI-native, explainable agentic commerce platform** that uses AI to understand a user's shopping goal, discover and evaluate products, explain recommendations, enforce purchasing constraints, and safely execute transactions with **explicit human approval**.

## 🚀 Live Application

* **Live Website:** https://nexacart-beta.vercel.app
* **Backend API:** https://nexacart-backend-bham.onrender.com
* **API Documentation:** https://nexacart-backend-bham.onrender.com/docs

---

## ✨ Features

### 🤖 AI-Powered Shopping

* AI Shopping Assistant
* AI Buyer Agent
* Intelligent product discovery and ranking
* Explainable AI recommendations
* Product comparison and evaluation
* What-if purchase simulations

### 🔐 Safe & Controlled Purchasing

* Commerce Contracts
* Configurable purchasing constraints
* Human approval before purchase
* Contract verification before transaction execution
* Secure checkout flow

### 🛍️ Commerce

* Smart Cart
* Checkout
* Razorpay payment integration
* Order management
* Purchase history

### 🔎 Explainability & Auditing

* Commerce Decision Trace
* Purchase Replay
* AI Decision Lab
* Recommendation reasoning
* Alternative products considered
* Decision history

### 👤 Platform

* Authentication
* Session management
* User-specific shopping workflows

---

## 🔄 AI Commerce Flow

```text
User Goal
    ↓
AI Shopping Assistant
    ↓
Product Discovery
    ↓
AI Buyer Agent
    ↓
Product Evaluation
    ↓
AI Recommendation
    ↓
Human Approval
    ↓
Commerce Contract Verification
    ↓
Smart Cart
    ↓
Checkout
    ↓
Razorpay Payment
    ↓
Order Creation
    ↓
Decision Trace / Purchase Replay
```

---

## 🛡️ Core Principle

> **AI recommends → Human approves → Contract verifies → Transaction executes**

NexaCart is designed so that the AI agent **cannot independently complete a purchase**.

A transaction requires:

1. AI-generated recommendation
2. User review
3. Explicit human approval
4. Commerce Contract verification
5. Payment processing
6. Order creation

This creates a controlled and auditable agentic commerce workflow.

---

## 🧠 Explainable AI

NexaCart provides transparency into how purchasing decisions are made.

Users can inspect:

* Why a product was recommended
* Product attributes that matched the shopping goal
* Alternative products considered
* Product comparisons
* Recommendation criteria
* What-if purchase simulations
* Previous purchasing decisions
* Commerce Decision Trace
* Commerce Contract verification

The goal is to make AI-driven purchasing **understandable, controllable, and auditable**.

---

## 📋 Commerce Contracts

Users can define purchasing constraints that the AI Buyer Agent must respect.

Examples include:

* Maximum budget
* Product category
* Required product attributes
* Purchasing conditions
* Approval requirements

Before a purchase proceeds, the recommendation is evaluated against the defined Commerce Contract.

```text
Shopping Goal
      ↓
AI Recommendation
      ↓
Contract Validation
      ↓
Meets Constraints?
   ↙          ↘
 Yes           No
  ↓             ↓
Approval     Reject / Revise
  ↓
Checkout
```

---

## 💳 Payment Flow

NexaCart integrates **Razorpay** for payment processing.

```text
Cart
  ↓
Checkout Approval
  ↓
Create Payment
  ↓
Razorpay Checkout
  ↓
Payment Verification
  ↓
Order Creation
```

> **Note:** Razorpay is currently configured in **Test Mode** for development and demonstration.

---

## 🧰 Tech Stack

### Frontend

* Next.js
* React
* TypeScript
* Tailwind CSS

### Backend

* Python
* FastAPI
* SQLAlchemy
* SQLite

### AI

* OpenAI API

### Payments

* Razorpay

### Deployment

* **Vercel** — Frontend
* **Render** — Backend

---

## 📁 Project Structure

```text
NexaCart/
│
├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
│
├── backend/
│   ├── routes/
│   ├── services/
│   ├── models/
│   ├── seed/
│   ├── main.py
│   └── requirements.txt
│
└── README.md
```

---

## 🌐 Using the Live Application

1. Open the **Live Website**.
2. Create an account or log in.
3. Explore products through **Discover**.
4. Describe your shopping goal to the **AI Shopping Assistant**.
5. Review the AI Buyer's recommendation.
6. Inspect the recommendation reasoning and alternative products.
7. Review the applicable Commerce Contract.
8. Explicitly approve the purchase.
9. Review the Smart Cart.
10. Proceed to Checkout.
11. Complete payment using **Razorpay Test Mode**.
12. View the resulting order.
13. Explore the **Commerce Decision Trace** and **Purchase Replay**.

---

# 💻 Local Development

## 1. Clone the Repository

```bash
git clone https://github.com/VeerlapallyHarika/Nexacart.git
cd Nexacart
```

## 2. Backend Setup

```bash
cd backend
python -m venv venv
```

### Activate the Virtual Environment

**Windows:**

```bash
venv\Scripts\activate
```

**macOS / Linux:**

```bash
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment Variables

Create a `.env` file inside the `backend` directory:

```env
DATABASE_URL=sqlite:///./data/nexacart.db

OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=your_openai_model

RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
PAYMENT_PROVIDER=razorpay

CORS_ORIGINS=http://localhost:3000
```

> Never commit API keys, payment secrets, or other sensitive credentials to GitHub.

### Run the Backend

```bash
uvicorn main:app --reload
```

Backend:

```text
http://localhost:8000
```

API Documentation:

```text
http://localhost:8000/docs
```

---

## 3. Frontend Setup

Open another terminal:

```bash
cd frontend
npm install
```

Create `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Run the development server:

```bash
npm run dev
```

Open:

```text
http://localhost:3000
```

---

# 🧪 Testing

## Backend Tests

```bash
cd backend
pytest
```

## Frontend Production Build

```bash
cd frontend
npm run build
```

---

# ☁️ Deployment

NexaCart is deployed using:

| Component | Platform   |
| --------- | ---------- |
| Frontend  | Vercel     |
| Backend   | Render     |
| Database  | SQLite     |
| Payments  | Razorpay   |
| AI        | OpenAI API |

The production Next.js frontend communicates with the deployed FastAPI backend through the configured API URL.

Environment variables and API secrets are stored outside the source code.

---

# 🔮 Future Improvements

* Real-time merchant and product integrations
* PostgreSQL for production-grade persistent storage
* Advanced AI purchasing policies
* Additional payment providers
* Multi-agent shopping workflows
* Personalized buyer profiles
* Expanded purchase analytics
* Real-time inventory and price tracking
* Advanced agent evaluation and benchmarking

---

## 🎯 Vision

NexaCart aims to demonstrate how **AI agents can participate in commerce without removing human control**.

Instead of allowing an autonomous agent to directly make purchases, NexaCart introduces a controlled pipeline where:

```text
AI Intelligence
      +
Human Control
      +
Policy Enforcement
      +
Transaction Safety
      =
Trustworthy Agentic Commerce
```

**NexaCart — AI that shops with you, not instead of you.**
