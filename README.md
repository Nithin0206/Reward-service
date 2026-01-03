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
Max Cashback per Transaction = amount × max_cashback_percentage (default: 10%)
Cashback = min(remaining_daily_limit, calculated_xp, max_cashback_per_transaction)
```

**Example**: For a ₹100 transaction by NEW user (1.5x multiplier):
- XP calculated: 100 × 1 × 1.5 = 150 XP
- Max 10% cashback: 100 × 10% = ₹10
- Actual cashback: min(remaining_limit, 150, 10) = **₹10** ✅

This ensures no transaction can give more than 10% cashback, making it sustainable like real-world apps.

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

**Transaction Type:**
- `PAYMENT` - Payment transaction (only supported type)

**Response:**
```json
{
  "decision_id": "uuid",
  "policy_version": "v1",
  "reward_type": "CHECKOUT",
  "reward_value": 10,
  "xp": 150,
  "reason_codes": ["CASHBACK_GRANTED"],
  "meta": {
    "persona": "NEW",
    "daily_cac_used": 0,
    "daily_cac_limit": 200
  }
}
```

**Note**: For ₹100 transaction, XP is 150 (with 1.5x multiplier) but cashback is capped at ₹10 (10% of amount).

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
- **Cashback Cap**: `max_cashback_percentage` (default: 10% per transaction)
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

**Current Status:** 37/37 tests passing ✅

**Test Categories:**
- Edge Cases (empty, null, zero, max/min values)
- Boundary Cases (off-by-one, exact limits)
- Invalid Cases (incorrect types, negative values)
- Functional Cases (correct business logic)
- Idempotency (duplicate handling)
- Constraints (large inputs, efficiency)

## 🗄️ Redis Keys & Cashback Tracking

- `idem:{txn_id}:{user_id}:{merchant_id}` - Idempotency (24h TTL)
- `persona:{user_id}` - User persona (30 days TTL)
- `txn_count:{user_id}` - Transaction count (30 days TTL)
- `cac:{user_id}:{date}` - **Daily cashback accumulated** (24h TTL)

### Cashback Accumulation Example

```
User: user123, Date: 2024-01-15

Transaction 1: ₹100 → Cashback: ₹10
  CAC = 0 + 10 = 10
  Redis: cac:user123:2024-01-15 = 10

Transaction 2: ₹200 → Cashback: ₹20
  CAC = 10 + 20 = 30
  Redis: cac:user123:2024-01-15 = 30

Transaction 3: ₹500 → Cashback: ₹50
  CAC = 30 + 50 = 80
  Redis: cac:user123:2024-01-15 = 80

... continues until daily limit (e.g., ₹200 for NEW users)

Next day (2024-01-16): CAC resets to 0
```

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

---

## 📋 Assumptions & Design Constraints

### **Business Logic Assumptions**

1. **Transaction Processing**
   - Each transaction is processed exactly once (idempotency key: `txn_id + user_id + merchant_id`)
   - Duplicate transactions return cached response without modifying state
   - Transaction amounts are in rupees and always positive (0.01 to 1,000,000)

2. **Persona Classification**
   - Persona progression is **irreversible** (NEW → RETURNING → POWER only)
   - Transaction count includes all successful PAYMENT transactions
   - Persona can be overridden via mocking (for testing/special cases)
   - Default persona for new users is **NEW**

3. **Daily CAC Limits & Tracking**
   - **CAC (Cashback Amount Claimed)** tracks accumulated cashback per user per day
   - Stored in Redis/cache with key: `cac:{user_id}:{date}` (e.g., `cac:user123:2024-01-15`)
   - CAC resets daily at midnight (based on server timezone)
   - Daily limits are **per persona** and enforced strictly:
     - NEW: ₹200/day
     - RETURNING: ₹150/day
     - POWER: ₹100/day
   - When limit is reached/exceeded, system automatically switches to XP rewards
   - CAC increments with each cashback reward granted (tracked cumulatively)

4. **Reward Calculation**
   - **10% Cashback Cap**: Maximum cashback per transaction is 10% of transaction amount
   - XP is calculated even when cashback is granted (for transparency)
   - Persona multipliers apply to XP calculation, not directly to cashback amount
   - Maximum XP per transaction is capped at `max_xp_per_txn` (default: 500)
   - Cashback is capped by **three limits** (whichever is lowest):
     1. Transaction percentage cap (10% of amount)
     2. Calculated XP value
     3. Remaining daily CAC limit

5. **Feature Flags Priority**
   - `prefer_gold` has higher priority than `prefer_xp`
   - Gold rewards only available to POWER users when `prefer_gold=true`
   - Feature flags can be changed via hot-reload without restart

### **Technical Assumptions**

1. **Caching & State**
   - Redis is the primary cache (shared state across instances)
   - Memory cache fallback is for **development only** (loses data on restart)
   - Cache TTLs: Idempotency (1 day), Persona (30 days), CAC (1 day)
   - No persistent database → data relies on Redis/cache

2. **Concurrency & Race Conditions**
   - Idempotency prevents race conditions for duplicate requests
   - Redis atomic operations ensure consistency
   - Cache writes are fire-and-forget (async background tasks)
   - Multiple instances can run concurrently with Redis

3. **Data Consistency**
   - **Eventually consistent** for cache writes (fire-and-forget)
   - **Strongly consistent** for reads (synchronous)
   - No transactions across multiple cache operations
   - Persona progression is deterministic (transaction count based)

4. **Scalability**
   - Stateless API design (all state in Redis)
   - Horizontal scaling supported with Redis cluster
   - Config hot-reload works across all instances (checks every hour)
   - Single Redis instance is bottleneck for high scale

5. **Input Validation**
   - All inputs validated via Pydantic models
   - Invalid inputs rejected at API layer (400 Bad Request)
   - Empty/whitespace-only strings not allowed
   - Transaction type must be PAYMENT (only supported type)

### **Operational Assumptions**

1. **Deployment**
   - Service runs behind a load balancer in production
   - Redis is highly available (Sentinel/Cluster)
   - Config changes tested in staging before production
   - Health checks monitored by orchestration platform

2. **Error Handling**
   - Redis failures fall back to memory cache (logged as warning)
   - Invalid config falls back to defaults (logged as error)
   - All exceptions caught at API layer (500 Internal Server Error)
   - Request IDs tracked for debugging

3. **Security**
   - No authentication/authorization (assumed handled by API gateway)
   - CORS allows all origins (should be restricted in production)
   - No rate limiting (should be added for production)
   - Admin endpoints (`/admin/reload-config`) should be protected

4. **Monitoring**
   - Health checks expected every 30-60 seconds
   - Request IDs included in all responses for tracing
   - Timing middleware for latency tracking
   - No built-in metrics (Prometheus recommended)

### **Known Limitations**

⚠️ **No audit trail** - Rewards granted are not persisted to database  
⚠️ **No rollback mechanism** - Rewards cannot be reversed after granting  
⚠️ **No rate limiting** - Service vulnerable to abuse without external protection  
⚠️ **Memory cache fallback** - Not suitable for multi-instance production  
⚠️ **Timezone dependency** - Daily reset timing depends on server timezone  
⚠️ **Config caching** - Hot-reload checks every hour (not real-time)

---


