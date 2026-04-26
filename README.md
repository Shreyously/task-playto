# PlayTo - Payout Processing System

A Django + React payout processing system with ledger balance management, idempotency, and retry logic.

## Prerequisites

- Docker Desktop installed and running
- Node.js 18+ installed
- Git

## Quick Start

### 1. Start Backend Services

```bash
cd backend

# Create .env file
cp .env.example .env

# Start all services (PostgreSQL, Redis, Django API, Celery Worker, Celery Beat)
docker compose up -d

# Run database migrations
docker compose exec backend python manage.py migrate

# Create test merchant and initial balance
docker compose exec backend python manage.py seed
```

**Services will run on:**
- Django API: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### 2. Start Frontend

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start development server
npm run dev
```

**Frontend will run on:** http://localhost:5173

## System Architecture

### Backend Services (Docker Compose)

1. **db** - PostgreSQL 15 database
2. **redis** - Redis 7 for Celery message broker
3. **backend** - Django API server (port 8000)
4. **worker** - Celery worker for async tasks
5. **beat** - Celery beat scheduler for periodic tasks

### Key Features

- **Ledger System**: Append-only double-entry ledger
- **Idempotency**: 24-hour idempotency keys for safe retries
- **Concurrency Control**: Row-level locking prevents race conditions
- **State Machine**: Payout status transitions (PENDING → PROCESSING → COMPLETED/FAILED)
- **Retry Logic**: Automatic retry with exponential backoff for stuck payouts
- **Audit Trail**: Immutable audit logs

## API Endpoints

### Merchants
- `GET /api/v1/merchants/me` - Get current merchant
- `GET /api/v1/merchants` - List all merchants

### Ledger
- `GET /api/v1/ledger` - Get merchant ledger entries

### Payouts
- `POST /api/v1/payouts` - Create payout request
- `GET /api/v1/payouts` - List merchant payouts
- `GET /api/v1/payouts/<uuid>` - Get payout details

**Required Headers:**
```
X-Merchant-ID: <merchant-uuid>
Idempotency-Key: <unique-key>
Content-Type: application/json
```

## Development Commands

### Backend
```bash
# View logs
docker compose logs -f

# View specific service logs
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f beat

# Restart services
docker compose restart

# Stop all services
docker compose down

# Run tests
docker compose exec backend python manage.py test

# Create Django admin
docker compose exec backend python manage.py createsuperuser

# Open Django shell
docker compose exec backend python manage.py shell
```

### Frontend
```bash
cd frontend

# Run development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Troubleshooting

### Backend Issues

**Port 8000 already in use:**
```bash
# Check what's using port 8000
netstat -ano | findstr :8000  # Windows
lsof -i :8000                  # Mac/Linux

# Kill the process or change port in docker-compose.yml
```

**Database connection errors:**
```bash
# Restart database
docker compose restart db

# Re-run migrations
docker compose exec backend python manage.py migrate
```

### Celery Worker Issues

**Tasks not processing:**
```bash
# Check worker logs
docker compose logs -f worker

# Restart worker
docker compose restart worker
```

### Frontend Issues

**Port 5173 already in use:**
```bash
# Kill existing process or run on different port
npm run dev -- --port 3000
```

**API connection issues:**
- Ensure backend is running on http://localhost:8000
- Check CORS settings in backend/playto/settings.py

## Testing

### Backend Tests
```bash
cd backend
docker compose exec backend python manage.py test
```

Tests include:
- Concurrent payout handling (race conditions)
- Idempotency (duplicate requests)
- Ledger balance consistency

### Manual Testing

1. Create a payout request:
```bash
curl -X POST http://localhost:8000/api/v1/payouts \
  -H "X-Merchant-ID: <your-merchant-id>" \
  -H "Idempotency-Key: test-$(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"amount_paise": 5000, "bank_account_id": "BANK123"}'
```

2. Check payout status:
```bash
curl http://localhost:8000/api/v1/payouts \
  -H "X-Merchant-ID: <your-merchant-id>"
```

## Project Structure

```
task-playto/
├── backend/
│   ├── playto/           # Django settings
│   ├── merchants/        # Merchant app
│   ├── ledger/           # Ledger app
│   ├── payouts/          # Payout app with Celery tasks
│   ├── docker-compose.yml
│   └── Dockerfile
└── frontend/
    ├── src/
    │   ├── components/   # React components
    │   ├── pages/        # Page components
    │   └── main.jsx      # Entry point
    └── package.json
```

## Production Deployment

For production deployment:
1. Set `DEBUG=False` in backend/.env
2. Use strong `SECRET_KEY`
3. Configure proper CORS origins
4. Use production database (AWS RDS, etc.)
5. Use production Redis (ElastiCache, etc.)
6. Build frontend: `npm run build`
7. Use production WSGI server (Gunicorn)
8. Set up proper monitoring and logging

## License

MIT
