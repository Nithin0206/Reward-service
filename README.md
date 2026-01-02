# Reward Service API

A high-performance FastAPI-based reward decision service that calculates and grants rewards (XP, Cashback, or Gold) to users based on transaction history, persona classification, and daily limits.

## 🚀 Features

- **Reward Types**: XP, Cashback (CHECKOUT), and Gold rewards
- **Persona System**: Automatic classification (NEW → RETURNING → POWER) based on transaction count
- **Persona Mocking**: Support for mocking personas via JSON file, in-memory map, or API endpoint
- **Daily CAC Limits**: Enforces daily cashback limits per persona
- **Redis Caching**: Fast in-memory caching with Redis support and graceful fallback
- **Idempotency**: Prevents duplicate reward processing
- **Async Architecture**: Fully async/await for high concurrency
- **Hot-Reload Config**: Automatic config reloading without server restart (checks every hour)
- **Type Safety**: Transaction types enforced via Enums
- **Health Checks**: Built-in health and readiness endpoints

## 📋 Quick Start

### Prerequisites
- Python 3.9+
- Redis (optional, falls back to memory cache)

### Installation

```bash
# Install dependencies
pip install -r requiements.txt

# Start Redis (optional)
redis-server

# Run the server
uvicorn app.app:app --reload
```

The API will be available at `http://localhost:8000`

## 🎯 Reward Decision Logic

The system uses a hierarchical decision flow:

1. **CAC Limit Check**: If daily cashback limit exceeded → Grant **XP**
2. **Gold Preference**: If `prefer_gold=true` AND persona is **POWER** → Grant **Gold**
3. **XP Preference**: If `prefer_xp=true` → Grant **XP**
4. **Default**: Grant **Cashback** up to remaining daily limit

### Persona Progression
- **NEW**: 0-2 transactions (1.5x multiplier, 200 daily limit)
- **RETURNING**: 3-9 transactions (1.2x multiplier, 150 daily limit)
- **POWER**: 10+ transactions (1.0x multiplier, 100 daily limit)

### XP Calculation
```
XP = min(amount × xp_per_rupee × persona_multiplier, max_xp_per_txn)
```

### Cashback Calculation
```
Cashback = min(remaining_daily_limit, calculated_xp)
```

## 📡 API Endpoints

### POST `/reward/decide`
Calculate and grant reward for a transaction.

**Request:**
```json
{
  "txn_id": "txn_001",
  "user_id": "user_123",
  "merchant_id": "merchant_001",
  "amount": 100.50,
  "txn_type": "PAYMENT",
  "ts": "2024-01-15T10:30:00"
}
```

**Transaction Types (Enum):**
- `PAYMENT` - Regular payment transaction
- `REFUND` - Refund transaction
- `REVERSAL` - Transaction reversal
- `ADJUSTMENT` - Adjustment transaction

**Response:**
```json
{
  "decision_id": "uuid",
  "policy_version": "v1",
  "reward_type": "CHECKOUT",
  "reward_value": 150,
  "xp": 150,
  "reason_codes": ["CASHBACK_GRANTED"],
  "meta": {
    "persona": "NEW",
    "daily_cac_used": 0,
    "daily_cac_limit": 200
  }
}
```

### GET `/health`
Health check endpoint with cache status.

**Response:**
```json
{
  "status": "healthy",
  "service": "Reward Decision Service",
  "cache": "connected",
  "hot_reload": "enabled"
}
```

### POST `/admin/reload-config`
Manually trigger configuration reload without restarting the server.

**Response:**
```json
{
  "status": "success",
  "message": "Configuration reloaded successfully",
  "policy_version": "v1"
}
```

### GET `/docs`
Interactive API documentation (Swagger UI)

### GET `/redoc`
Alternative API documentation (ReDoc)

## ⚙️ Configuration

Edit `app/config.yaml` to customize:

- **Feature Flags**: `prefer_xp`, `prefer_gold`
- **XP Settings**: `xp_per_rupee`, `max_xp_per_txn`
- **Persona Multipliers**: NEW, RETURNING, POWER
- **Daily CAC Limits**: Per persona limits
- **Cache TTLs**: Idempotency, persona, CAC cache durations
- **Redis Settings**: Host, port, connection pool, timeouts
- **Persona Mocking**: Enable/disable, file path, in-memory map

### 🔄 Hot-Reload Configuration

The service automatically checks for config changes every hour. You can also:

**Option 1: Wait for automatic reload** (up to 1 hour)
- Edit `app/config.yaml`
- Changes detected and applied automatically

**Option 2: Manual reload**
```bash
curl -X POST http://localhost:8000/admin/reload-config
```

**Option 3: Restart server**
```bash
# Standard reload
uvicorn app.app:app --reload
```

## 🧪 Testing

Run tests with pytest:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_reward_decision_logic.py

# Run with verbose output
pytest -v
```

**Test Coverage:**
- ✅ Reward decision logic (XP, Cashback, Gold)
- ✅ Idempotency behavior
- ✅ CAC limit enforcement
- ✅ Persona progression (NEW → RETURNING → POWER)
- ✅ Configuration validation
- ✅ Transaction type enum validation

**Current Status:** 21/21 tests passing ✅

## 🗄️ Redis Keys

- `idem:{txn_id}:{user_id}:{merchant_id}` - Idempotency
- `persona:{user_id}` - User persona
- `txn_count:{user_id}` - Transaction count
- `cac:{user_id}:{date}` - Daily cashback usage

## 📦 Project Structure

```
reward service/
├── app/
│   ├── app.py              # FastAPI application
│   ├── config.yaml         # Configuration
│   ├── cache/              # Cache implementations
│   ├── middleware/         # Request middleware
│   ├── models/            # Pydantic models
│   ├── routers/           # API routes
│   ├── services/          # Business logic
│   └── utils/             # Utilities
├── tests/                 # Unit tests
├── clear_redis.py          # Redis cleanup utility
├── load_test.py           # Load testing script
└── README.md
```

## 🔧 Development

```bash
# Run with auto-reload
uvicorn app.app:app --reload

# Run on specific host/port
uvicorn app.app:app --host 0.0.0.0 --port 8000

# Run with Redis
redis-server  # In separate terminal
uvicorn app.app:app --reload

# Clear Redis data
python clear_redis.py

# Run load tests
python load_test.py
```

### Key Design Decisions

✅ **Config-Driven Design**: All business rules in YAML  
✅ **Type Safety**: Enums for reward types, personas, transaction types  
✅ **Async-First**: Full async/await for high concurrency  
✅ **Graceful Degradation**: Falls back to memory cache if Redis unavailable  
✅ **Idempotency**: Safe duplicate request handling  
✅ **Hot-Reload**: No downtime for config changes  
✅ **Comprehensive Logging**: Request ID tracking, timing middleware


