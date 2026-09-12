# NexaCart — AI-Native Conversational Commerce

**Tagline:** Talk → Discover → Decide → Pay

An AI-powered conversational commerce platform that allows users to shop through natural conversation.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | Python 3.11, FastAPI, SQLAlchemy |
| Database | SQLite (upgradeable to PostgreSQL) |
| AI | OpenAI GPT-4 (Phase 2) |
| Payments | Razorpay Test Mode (Phase 3) |

---

## Project Structure

```
nexacart/
├── frontend/           # Next.js app
├── backend/            # FastAPI app
├── docs/               # Documentation
└── README.md
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn main:app --reload --port 8000
```

Backend runs at: http://localhost:8000

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
```

Frontend runs at: http://localhost:3000

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/products` | List all products |
| GET | `/api/products/{id}` | Get product details |
| POST | `/api/chat` | Send chat message |

---

## Current Features (Phase 1)

- Chat UI with message display
- Product catalog (12 demo products)
- Event logging foundation
- SQLite database

---

## Development Phases

1. **Phase 1** — Foundation ✅ (current)
2. **Phase 2** — Agent Core (CartAgent + OpenAI)
3. **Phase 3** — Checkout Flow (Razorpay)
4. **Phase 4** — AI Buyer Passport
5. **Phase 5** — Replay System
6. **Phase 6** — Polish & Demo

---

## Environment Variables

### Backend (`.env`)

```
DATABASE_URL=sqlite:///./data/nexacart.db
CORS_ORIGINS=["http://localhost:3000"]
```

### Frontend (`.env.local`)

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Documentation

- [Architecture Plan](docs/NEXACART_PLAN.md)
- [Phase 1 Plan](docs/PHASE1_PLAN.md)

---

## License

Hackathon project — Razorpay Buildathon
