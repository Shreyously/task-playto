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

1. **db** - PostgreSQL 15 database (Supabase in production)
2. **redis** - Redis 7 for Celery message broker and caching
3. **backend** - Django API server (Gunicorn + WhiteNoise, port 8000)
4. **worker** - Celery worker for async payout processing
5. **beat** - Celery beat scheduler for periodic retry tasks

### Django Apps Structure

```
backend/
├── playto/         # Main Django project configuration
├── merchants/      # Merchant management and authentication
├── payouts/        # Payment processing with Celery tasks
├── ledger/         # Immutable financial ledger system
└── migrations/     # Database schema migrations
```

### Data Flow Architecture

```
Client Request
    ↓
Django View (API Layer)
    ↓
Merchant Validation (X-Merchant-ID header)
    ↓
Payout Creation (Service Layer)
    ├── Idempotency Check
    ├── Balance Validation (Ledger)
    ├── Database Transaction
    │   ├── Ledger Entry Creation
    │   ├── Payout Request Creation
    │   └── Audit Log Entry
    └── Celery Task Enqueue
        ↓
    Background Processing (Celery Worker)
        ├── Bank Transfer Simulation
        ├── Status Updates (PENDING → PROCESSING → COMPLETED/FAILED)
        ├── Additional Audit Logging
        └── Error Handling with Retry Logic
    ↓
Response to Client
```

### Key Architecture Patterns

- **Service Layer Pattern**: Business logic separated from views (`payouts/services.py`)
- **Repository Pattern**: Data access abstracted through Django ORM
- **Event-Driven Architecture**: Async payout processing via Celery
- **Append-Only Design**: Immutable ledger and audit logs
- **Idempotency Keys**: Prevent duplicate payment processing
- **State Machine**: Controlled payout status transitions
- **Row-Level Locking**: Prevents concurrent modification issues

### Key Features

- **Ledger System**: Append-only double-entry ledger with immutable entries
- **Idempotency**: 24-hour idempotency keys for safe retries
- **Concurrency Control**: Row-level locking prevents race conditions
- **State Machine**: Payout status transitions (PENDING → PROCESSING → COMPLETED/FAILED)
- **Retry Logic**: Automatic retry every 10 seconds for stuck payouts
- **Audit Trail**: Complete immutable audit logs for all state changes
- **Financial Integrity**: Atomic transactions ensure data consistency

## Database Schema

### Core Models

**Merchant Model** (`merchants/models.py`)
- `id` (UUID, Primary Key)
- `name` (String)
- `email` (String)
- `created_at`, `updated_at` (Timestamps)

**PayoutRequest Model** (`payouts/models.py`)
- `id` (UUID, Primary Key)
- `merchant` (Foreign Key → Merchant)
- `amount_paise` (Integer) - Amount in paise (integer arithmetic)
- `bank_account_id` (String)
- `status` (Enum: PENDING, PROCESSING, COMPLETED, FAILED)
- `idempotency_key` (String, Unique)
- `attempts` (Integer, Default: 0)
- `created_at`, `updated_at` (Timestamps)

**LedgerEntry Model** (`ledger/models.py`)
- `id` (UUID, Primary Key)
- `merchant` (Foreign Key → Merchant)
- `entry_type` (Enum: CREDIT, DEBIT)
- `amount_paise` (Integer)
- `payout` (Foreign Key → PayoutRequest, Optional)
- `created_at` (Timestamp) - **Immutable**

**AuditLog Model** (`payouts/models.py`)
- `id` (UUID, Primary Key)
- `payout` (Foreign Key → PayoutRequest)
- `from_status`, `to_status` (String)
- `reason` (String)
- `created_at` (DateTime) - **Immutable**

**IdempotencyRecord Model** (`payouts/models.py`)
- `id` (UUID, Primary Key)
- `merchant` (Foreign Key → Merchant)
- `key` (String)
- Unique together on (merchant, key)
- `response_body` (JSON)
- `created_at` (Timestamp) - **Auto-expires after 24 hours**

## Authentication & Security

### Merchant Authentication
- **Method**: Custom header-based authentication
- **Header**: `X-Merchant-ID: <merchant-uuid>`
- **Validation**: View-level merchant validation
- **No Traditional Auth**: No username/password for merchants

### Security Features
- **CORS**: Configured for cross-origin requests
- **Idempotency**: Prevents duplicate payment processing
- **UUID Primary Keys**: Prevents enumeration attacks
- **Row-Level Locking**: Database-level concurrency control
- **Audit Trails**: Complete state change logging
- **Production Security**: SSL, CSRF protection, secure cookies

## API Endpoints

### Merchants
- `GET /api/v1/merchants/me` - Get current merchant details
- `GET /api/v1/merchants` - List all merchants (limited info)

### Ledger
- `GET /api/v1/ledger` - Get merchant's financial ledger entries
  - Query params: `?entry_type=CREDIT` (optional filter)

### Payouts
- `POST /api/v1/payouts` - Create new payout request
- `GET /api/v1/payouts` - List merchant's payout requests
- `GET /api/v1/payouts/<uuid>` - Get specific payout details

**Required Headers:**
```
X-Merchant-ID: <merchant-uuid>
Idempotency-Key: <unique-key> (for POST requests)
Content-Type: application/json
```

### API Request/Response Examples

**Create Payout Request:**
```bash
curl -X POST http://localhost:8000/api/v1/payouts \
  -H "X-Merchant-ID: <your-merchant-id>" \
  -H "Idempotency-Key: test-$(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{
    "amount_paise": 5000,
    "bank_account_id": "BANK123"
  }'
```

**Success Response (201 Created):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "merchant": "merchant-uuid",
  "amount_paise": 5000,
  "bank_account_id": "BANK123",
  "status": "PENDING",
  "attempts": 0,
  "created_at": "2026-04-28T10:30:00Z"
}
```

**Error Response - Insufficient Balance (400 Bad Request):**
```json
{
  "error": "Insufficient balance",
  "current_balance": 3000,
  "requested_amount": 5000
}
```

**Duplicate Request Responses:**

**Normal duplicate (already committed) - 200 OK:**
*(Returns the stored response from the original request)*
```json
{
  "payout_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "PENDING",
  "amount_paise": 5000
}
```

**Simultaneous in-flight duplicate (IntegrityError) - 409 Conflict:**
```json
{
  "error": "Duplicate request"
}
```

## Celery Task Processing

### Background Tasks

**Process Payout Task** (`payouts/tasks.py`)
- **Trigger**: Automatic when payout is created
- **Process**:
  1. Validate payout status
  2. Simulate bank transfer (mock API call)
  3. Update payout status (PENDING → PROCESSING → COMPLETED/FAILED)
  4. Create audit log entries
  5. Handle errors with retry logic

**Retry Stuck Payouts Task** (`payouts/tasks.py`)
- **Schedule**: Every 10 seconds via Celery Beat
- **Purpose**: Detect payouts stuck in PROCESSING for more than 30 seconds
- **Logic**:
  1. Find payouts in PROCESSING status where processing_started_at < now - 30s
  2. If attempts >= 3 → mark FAILED, refund merchant balance atomically 
     in same transaction
  3. If attempts < 3 → increment attempts, re-enqueue process_payout 
     with exponential backoff:
     - attempt 1 → countdown 2 seconds
     - attempt 2 → countdown 4 seconds
     - attempt 3 → countdown 8 seconds

> Note: The 10 second polling detects stuck payouts. The exponential 
> backoff controls how far ahead the next retry is scheduled. These work 
> together — polling finds stuck payouts, backoff spaces out the retries.

### Task Configuration
- **Broker**: Redis (localhost:6379)
- **Result Backend**: Redis
- **Worker Concurrency**: 4 (configurable)
- **Task Timeouts**: 30 seconds default
- **Retry Strategy**: Exponential backoff

## Environment Configuration

### Backend Environment Variables (.env)

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/playto_db

# Redis (Celery)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# CORS (Frontend URL)
CORS_ALLOWED_ORIGINS=http://localhost:5173

# Production Settings
# DEBUG=False
# ALLOWED_HOSTS=your-domain.com
# CORS_ALLOWED_ORIGINS=https://your-frontend.com
```

### Frontend Environment Variables (.env)

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## Development Workflow

### Adding New Features

1. **Create New Django App** (if needed):
```bash
docker compose exec backend python manage.py startapp new_app
```

2. **Create Database Models**:
```bash
# Create model in models.py
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
```

3. **Add API Endpoints**:
   - Create views in `views.py`
   - Add URL patterns in `urls.py`
   - Create serializers if needed

4. **Create Celery Tasks** (for async operations):
   - Define task in `tasks.py`
   - Call task from views or services

### Database Management

```bash
# Create migrations after model changes
docker compose exec backend python manage.py makemigrations

# Apply migrations
docker compose exec backend python manage.py migrate

# Show migration status
docker compose exec backend python manage.py showmigrations

# Rollback migration
docker compose exec backend python manage.py migrate app_name previous_migration
```

### Debugging Tips

**View Django Logs:**
```bash
docker compose logs -f backend
```

**View Celery Worker Activity:**
```bash
docker compose logs -f worker
```

**Access Django Shell:**
```bash
docker compose exec backend python manage.py shell
```

**Monitor Redis Activity:**
```bash
docker compose exec redis redis-cli monitor
```

**Check Database Connections:**
```bash
docker compose exec backend python manage.py dbshell
```

### Common Development Tasks

**Create Test Data:**
```bash
docker compose exec backend python manage.py seed
```

**Create Superuser:**
```bash
docker compose exec backend python manage.py createsuperuser
```

**Run Specific Tests:**
```bash
docker compose exec backend python manage.py test payouts.tests
```

**Check Celery Registered Tasks:**
```bash
docker compose exec backend python -c "from celery import current_app; print(current_app.tasks)"
```

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

# Check registered tasks
docker compose exec backend python -c "from playto.celery import app; print(app.tasks)"
```

**Payouts stuck in PROCESSING:**
```bash
# Check beat scheduler logs
docker compose logs -f beat

# Manually trigger retry task
docker compose exec backend python manage.py shell
>>> from payouts.tasks import retry_stuck_payouts
>>> retry_stuck_payouts.delay()
```

**Redis connection issues:**
```bash
# Check Redis status
docker compose ps redis

# Test Redis connection
docker compose exec redis redis-cli ping

# Restart Redis
docker compose restart redis
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

### Implemented Tests

- **Concurrency Test**: Two simultaneous 60,000 paise requests against 
  100,000 paise balance — exactly one succeeds
- **Idempotency Test**: Same idempotency key sent twice — one PayoutRequest 
  created, identical responses returned

### Manual Testing Workflow

**1. Setup Test Environment:**
```bash
# Start services
cd backend
docker compose up -d

# Run migrations
docker compose exec backend python manage.py migrate

# Create test data
docker compose exec backend python manage.py seed
```

**2. Get Merchant ID:**
```bash
curl http://localhost:8000/api/v1/merchants
```

**3. Create Payout Request:**
```bash
curl -X POST http://localhost:8000/api/v1/payouts \
  -H "X-Merchant-ID: <your-merchant-id>" \
  -H "Idempotency-Key: test-$(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{
    "amount_paise": 5000,
    "bank_account_id": "BANK123"
  }'
```

**4. Monitor Payout Processing:**
```bash
# Check payout status
curl http://localhost:8000/api/v1/payouts \
  -H "X-Merchant-ID: <your-merchant-id>"

# Check Celery worker logs
docker compose logs -f worker
```

**5. Verify Ledger Entries:**
```bash
curl http://localhost:8000/api/v1/ledger \
  -H "X-Merchant-ID: <your-merchant-id>"
```

**6. Test Idempotency:**
```bash
# Send same request again with same idempotency key
# Should return 200 OK with original stored response
```

### Load Testing

**Concurrent Request Test:**
```bash
# Install Apache Bench first
# Test 100 concurrent requests
ab -n 100 -c 10 -H "X-Merchant-ID: <merchant-id>" \
   -H "Content-Type: application/json" \
   -p payout.json http://localhost:8000/api/v1/payouts
```

### Performance Monitoring

**Celery Flower** (Optional - for production monitoring):
```bash
# Add to requirements.txt: flower==2.0.1
# Run flower to monitor Celery tasks
docker compose exec backend celery -A playto flower
# Access at http://localhost:5555
```

## Project Structure

```
task-playto/
├── backend/
│   ├── playto/                 # Main Django project
│   │   ├── settings.py         # Configuration management
│   │   ├── urls.py             # Main URL routing
│   │   ├── wsgi.py             # WSGI application entry point
│   │   ├── asgi.py             # ASGI application entry point
│   │   └── celery.py           # Celery configuration
│   ├── merchants/              # Merchant management app
│   │   ├── models.py           # Merchant data models
│   │   ├── views.py            # API views for merchants
│   │   ├── serializers.py      # Data serialization
│   │   ├── urls.py             # App-specific URLs
│   │   └── migrations/         # Database migrations
│   ├── payouts/                # Payout processing app
│   │   ├── models.py           # Payout request models
│   │   ├── views.py            # API views for payouts
│   │   ├── serializers.py      # Data serialization
│   │   ├── services.py         # Business logic services
│   │   ├── tasks.py            # Celery task definitions
│   │   ├── tests.py            # Test files
│   │   ├── urls.py             # App-specific URLs
│   │   └── migrations/         # Database migrations
│   ├── ledger/                 # Financial ledger app
│   │   ├── models.py           # Ledger entry models
│   │   ├── views.py            # API views for ledger
│   │   ├── serializers.py      # Data serialization
│   │   ├── urls.py             # App-specific URLs
│   │   └── migrations/         # Database migrations
│   ├── manage.py               # Django management script
│   ├── requirements.txt        # Python dependencies
│   ├── Dockerfile              # Container build configuration
│   ├── docker-compose.yml      # Service orchestration
│   ├── start.sh                # Application startup script
│   └── .env                    # Environment variables
└── frontend/
    ├── src/
    │   ├── components/         # React components
    │   ├── pages/              # Page components
    │   ├── services/           # API service layer
    │   └── main.jsx            # Application entry point
    ├── package.json            # Node dependencies
    └── vite.config.js          # Vite bundler configuration
```

### Key Files Overview

**Backend Configuration:**
- `playto/settings.py` - Django settings, DB, Celery, CORS configuration
- `playto/celery.py` - Celery app setup, broker configuration
- `docker-compose.yml` - Multi-service orchestration

**Business Logic:**
- `payouts/services.py` - Core payout creation logic, idempotency handling
- `payouts/tasks.py` - Background payout processing, retry logic
- `payouts/models.py` - Payout request, audit log, idempotency models

**API Layer:**
- `*/views.py` - Request handling, merchant validation
- `*/serializers.py` - Data validation, serialization
- `*/urls.py` - Route definitions

**Data Models:**
- `merchants/models.py` - Merchant entity
- `ledger/models.py` - Financial ledger entries
- `payouts/models.py` - Payout requests, audit logs, idempotency records

## Production Deployment

### Architecture Considerations

**Scalability**
- **Web Servers**: Multiple Gunicorn workers behind load balancer
- **Celery Workers**: Scale horizontally based on task queue length
- **Database**: Use managed PostgreSQL (AWS RDS, Google Cloud SQL)
- **Redis**: Use managed Redis (ElastiCache, Redis Cloud)

**Security**
- **Environment Variables**: Never commit `.env` files
- **Secret Key**: Use strong, randomly generated SECRET_KEY
- **Database**: Strong password, SSL connections
- **CORS**: Whitelist only production domains
- **SSL/TLS**: Enable HTTPS for all endpoints

**Monitoring**
- **Application Metrics**: Track request latency, error rates
- **Celery Monitoring**: Use Flower or similar tools
- **Database Monitoring**: Query performance, connection pooling
- **Logging**: Centralized logging (ELK stack, CloudWatch)
- **Alerting**: Set up alerts for failed payouts, high retry rates

### Deployment Checklist

**Backend Configuration:**
```bash
# Set production environment variables
DEBUG=False
SECRET_KEY=<strong-random-key>
DATABASE_URL=<production-postgres-url>
CELERY_BROKER_URL=<production-redis-url>
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CORS_ALLOWED_ORIGINS=https://your-frontend.com
```

**Frontend Configuration:**
```bash
# Build for production
npm run build

# Set production API URL
VITE_API_BASE_URL=https://api.your-domain.com
```

**Infrastructure Setup:**
1. **Database**: Create production PostgreSQL database
2. **Redis**: Set up production Redis instance
3. **Load Balancer**: Configure Nginx/ALB for SSL termination
4. **Celery Workers**: Deploy multiple workers for high availability
5. **Monitoring**: Set up application and infrastructure monitoring

**Deployment Steps:**
```bash
# 1. Pull latest code
git pull origin main

# 2. Build and start backend services
cd backend
docker compose -f docker-compose.prod.yml up -d

# 3. Run migrations
docker compose exec backend python manage.py migrate

# 4. Collect static files
docker compose exec backend python manage.py collectstatic --noinput

# 5. Build and deploy frontend
cd ../frontend
npm run build

# 6. Verify health
curl https://api.your-domain.com/health/
```

### Performance Optimization

**Database Optimization:**
- Index frequently queried fields (merchant_id, status, created_at)
- Use connection pooling (default: 10 connections per worker)
- Enable query caching for read-heavy operations
- Regular database maintenance (vacuum, analyze)

**Application Optimization:**
- Enable Django caching framework
- Use database query optimization (select_related, prefetch_related)
- Implement API response pagination
- Add CDN for static assets

**Celery Optimization:**
- Tune worker concurrency based on CPU cores
- Set appropriate task timeouts
- Configure result backend expiration
- Monitor queue length and scale workers accordingly

## Architecture Decisions

### Why These Patterns?

**Django + DRF**
- Mature ecosystem with built-in admin interface
- Strong ORM for complex database relationships
- Comprehensive security features
- Great for rapid development

**Celery + Redis**
- Reliable async task processing
- Built-in retry mechanisms
- Scalable worker architecture
- Easy monitoring and debugging

**PostgreSQL**
- ACID compliance for financial transactions
- Strong data integrity constraints
- Excellent query optimization
- Supports complex JSON operations

**Append-Only Ledger**
- Complete audit trail
- Regulatory compliance
- Easy reconciliation
- Historical analysis capability

**Idempotency Keys**
- Prevent duplicate payments
- Better user experience (safe retries)
- Network resilience
- Exactly-once processing semantics

### Trade-offs

**Row-Level Locking vs. Optimistic Concurrency**
- **Chosen**: Row-level locking (select_for_update)
- **Reason**: Financial transactions require absolute consistency
- **Trade-off**: Potential performance bottleneck under extreme load
- **Mitigation**: Horizontal scaling, connection pooling

**Monolithic vs. Microservices**
- **Chosen**: Modular monolith (Django apps)
- **Reason**: Simpler deployment, easier development
- **Trade-off**: Shared codebase can become large
- **Mitigation**: Clean separation of concerns, service layer pattern

**Sync vs. Async Processing**
- **Chosen**: Hybrid (Sync API, Async processing)
- **Reason**: Better UX, resilient to external service failures
- **Trade-off**: Added complexity (Celery, Redis)
- **Mitigation**: Robust error handling, monitoring

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
