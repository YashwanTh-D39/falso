# Falso — Backend

FastAPI backend for the Falso AI assistant.

## Quick Start

```bash
# 1. Create a virtual environment
python -m venv .venv

# 2. Activate it
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment config
cp ..\.env.example .env         # Windows (copy instead of cp)

# 5. Run the server
uvicorn backend.app.main:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for interactive API docs.

## Project Structure

```
backend/
├── app/
│   ├── main.py          # FastAPI app entry point
│   ├── routes/          # API route handlers
│   ├── services/        # Business logic
│   ├── models/          # Database / ORM models
│   ├── schemas/         # Pydantic request/response schemas
│   ├── middleware/      # Custom ASGI middleware
│   └── utils/           # Helper utilities
└── requirements.txt     # Python dependencies
```

## Configuration

Settings are managed via `config/settings.py` and loaded from a `.env` file. See `.env.example` for available options.
