# Operability Analysis — Monitoring, Logging, Observability

**Project:** Neuroca  
**Generated:** 2025-11-06  
**Commit:** 563c5ce81e92499cf83c4f674f6dc1ebf86a4906

---

## Executive Summary

Neuroca has **foundational observability infrastructure** in place with Prometheus metrics, structured logging (Loguru), and OpenTelemetry tracing hooks. However, production-grade operability requires enhancements in distributed tracing implementation, alert configuration, and operational runbooks.

**Operability Score:** **3.5/5.0** (Good foundation; needs production hardening)

---

## 1. Logging

### 1.1 Current Implementation

**Framework:** Loguru

**Strengths:**
- ✅ Structured logging with JSON output
- ✅ Automatic contextual information (timestamps, levels, module names)
- ✅ Async-safe logging
- ✅ Log rotation configured

**Configuration:**

```python
# Typical logging setup (inferred from codebase)
from loguru import logger

logger.add(
    "logs/neuroca_{time}.log",
    rotation="500 MB",
    retention="10 days",
    compression="zip",
    level="INFO"
)
```

### 1.2 Log Levels & Usage

| Level | Usage | Current Coverage |
|-------|-------|------------------|
| **DEBUG** | Detailed debugging information | ✅ Comprehensive |
| **INFO** | General operational events | ✅ Good |
| **WARNING** | Potential issues, degraded performance | ⚠️ Inconsistent |
| **ERROR** | Error conditions, exceptions | ✅ Good |
| **CRITICAL** | System failures | ⚠️ Sparse |

### 1.3 Log Content Analysis

**Current Log Patterns:**

```python
# Good examples found in codebase
logger.info(f"Memory added to {tier}", memory_id=mem_id, tier=tier.value)
logger.error(f"Failed to consolidate memory", memory_id=mem_id, error=str(e))
logger.debug(f"Search results: {len(results)} memories found", query_hash=hash)
```

**Strengths:**
- ✅ Contextual data as structured fields
- ✅ Correlation IDs present in some areas
- ✅ Error stack traces included

**Gaps:**
- ❌ **No consistent correlation ID** across request lifecycle
- ❌ **PII/sensitive data** not sanitized
- ⚠️ **Log volume** not optimized (debug logs in production)
- ❌ **No log sampling** for high-volume operations

### 1.4 Recommendations

**Immediate (P0):**

1. **Implement request correlation IDs:**
   ```python
   # Add middleware to generate correlation ID
   from contextvars import ContextVar
   
   correlation_id = ContextVar("correlation_id", default=None)
   
   @app.middleware("http")
   async def add_correlation_id(request, call_next):
       cid = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
       correlation_id.set(cid)
       logger.bind(correlation_id=cid)
       response = await call_next(request)
       response.headers["X-Correlation-ID"] = cid
       return response
   ```

2. **Log sanitization:**
   ```python
   # Sanitize secrets, PII, and tokens
   def sanitize_log_data(data):
       sensitive_fields = ["password", "token", "api_key", "secret"]
       if isinstance(data, dict):
           return {k: "***REDACTED***" if k.lower() in sensitive_fields else v 
                   for k, v in data.items()}
       return data
   ```

3. **Dynamic log levels:**
   ```python
   # Environment-based log level
   LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
   logger.configure(handlers=[{"sink": sys.stdout, "level": LOG_LEVEL}])
   ```

**Short-term (P1):**

1. **Structured logging schema:**
   - Standardize log message format
   - Include: `timestamp`, `level`, `service`, `correlation_id`, `user_id`, `action`, `duration_ms`, `status`

2. **Log aggregation:**
   - Forward logs to ELK/Loki/CloudWatch
   - Implement log indexing for fast queries
   - Set up log retention policies (30 days hot, 1 year cold)

3. **Log sampling:**
   - Sample debug logs (1 in 100) in production
   - Always log errors and warnings

---

## 2. Metrics

### 2.1 Current Implementation

**Framework:** Prometheus Client

**Instrumentation Points:**

| Component | Metrics | Status |
|-----------|---------|--------|
| **API Service** | Request count, latency, errors | ✅ Implemented |
| **Memory Manager** | Operations per tier, consolidation stats | ⚠️ Partial |
| **Backend Adapters** | Backend operations, cache hits | ⚠️ Partial |
| **Background Workers** | Job duration, success/failure | ⚠️ Partial |
| **Database** | Query latency, connection pool | ❌ Missing |

### 2.2 Recommended Metrics

**Application Metrics:**

```python
from prometheus_client import Counter, Histogram, Gauge, Summary

# API metrics
api_requests_total = Counter(
    "neuroca_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"]
)

api_request_duration = Histogram(
    "neuroca_api_request_duration_seconds",
    "API request duration",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

# Memory operations
memory_operations_total = Counter(
    "neuroca_memory_operations_total",
    "Total memory operations",
    ["operation", "tier", "status"]
)

memory_operation_duration = Histogram(
    "neuroca_memory_operation_duration_seconds",
    "Memory operation duration",
    ["operation", "tier"]
)

# Memory tier stats
memory_tier_size = Gauge(
    "neuroca_memory_tier_size_items",
    "Number of items in memory tier",
    ["tier"]
)

memory_tier_capacity_used = Gauge(
    "neuroca_memory_tier_capacity_used_percent",
    "Capacity utilization percentage",
    ["tier"]
)

# Consolidation metrics
consolidation_duration = Histogram(
    "neuroca_consolidation_duration_seconds",
    "Consolidation process duration"
)

consolidation_items_processed = Counter(
    "neuroca_consolidation_items_processed_total",
    "Total items processed by consolidation",
    ["source_tier", "target_tier", "status"]
)

# LLM integration
llm_requests_total = Counter(
    "neuroca_llm_requests_total",
    "Total LLM API requests",
    ["provider", "status"]
)

llm_request_duration = Histogram(
    "neuroca_llm_request_duration_seconds",
    "LLM API request duration",
    ["provider"]
)

llm_tokens_used = Counter(
    "neuroca_llm_tokens_used_total",
    "Total tokens consumed",
    ["provider", "type"]  # type: prompt or completion
)

# Vector search metrics
vector_search_duration = Histogram(
    "neuroca_vector_search_duration_seconds",
    "Vector search duration",
    ["tier", "collection"]
)

vector_search_results = Summary(
    "neuroca_vector_search_results_count",
    "Number of results returned",
    ["tier"]
)
```

**Infrastructure Metrics:**

```python
# Database connection pool
db_connections_active = Gauge(
    "neuroca_db_connections_active",
    "Active database connections",
    ["database"]
)

db_connections_idle = Gauge(
    "neuroca_db_connections_idle",
    "Idle database connections",
    ["database"]
)

# Redis metrics
redis_operations_total = Counter(
    "neuroca_redis_operations_total",
    "Total Redis operations",
    ["operation", "status"]
)

redis_operation_duration = Histogram(
    "neuroca_redis_operation_duration_seconds",
    "Redis operation duration",
    ["operation"]
)

# Milvus metrics
milvus_operations_total = Counter(
    "neuroca_milvus_operations_total",
    "Total Milvus operations",
    ["operation", "collection", "status"]
)

milvus_operation_duration = Histogram(
    "neuroca_milvus_operation_duration_seconds",
    "Milvus operation duration",
    ["operation", "collection"]
)
```

### 2.3 Metrics Endpoint

**Current:** `/metrics` endpoint available via Prometheus client

**Recommendations:**
1. Add `/metrics/health` endpoint with aggregated health status
2. Implement metric push to Prometheus Pushgateway for batch jobs
3. Add metric cardinality limits to prevent explosion

---

## 3. Tracing

### 3.1 Current Implementation

**Framework:** OpenTelemetry

**Status:** ⚠️ **Hooks present but incomplete**

**Current Coverage:**
- ✅ OpenTelemetry SDK imported
- ✅ OTLP exporter configured
- ⚠️ Instrumentation incomplete
- ❌ No distributed tracing across services

### 3.2 Recommended Tracing Implementation

**Automatic Instrumentation:**

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# Setup tracer provider
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Export to OTLP collector
otlp_exporter = OTLPSpanExporter(endpoint="http://otel-collector:4317")
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Auto-instrument frameworks
FastAPIInstrumentor.instrument_app(app)
RedisInstrumentor().instrument()
SQLAlchemyInstrumentor().instrument(engine=engine)
HTTPXClientInstrumentor().instrument()
```

**Manual Instrumentation for Critical Paths:**

```python
@tracer.start_as_current_span("memory.add")
async def add_memory(self, content: str, tier: MemoryTier, metadata: dict):
    span = trace.get_current_span()
    span.set_attribute("memory.tier", tier.value)
    span.set_attribute("memory.content_length", len(content))
    
    # Add memory logic
    with tracer.start_as_current_span("memory.embedding.generate"):
        embedding = await self.generate_embedding(content)
    
    with tracer.start_as_current_span("memory.backend.store"):
        memory_id = await self.backend.store(memory_item)
    
    span.set_attribute("memory.id", str(memory_id))
    return memory_id
```

### 3.3 Trace Sampling

**Strategy:**
- Production: Sample 10% of traces (reduce overhead)
- Development: Sample 100%
- Errors: Always trace (100%)

```python
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

sampler = ParentBasedTraceIdRatio(0.1)  # 10% sampling
trace.set_tracer_provider(TracerProvider(sampler=sampler))
```

### 3.4 Trace Context Propagation

**Ensure trace context propagates across:**
1. HTTP requests (via `traceparent` header)
2. Background jobs (via message queue headers)
3. Database queries (via SQLAlchemy instrumentation)

---

## 4. Health Checks

### 4.1 Current Implementation

**Endpoints:**
- `/health` — Basic liveness check
- `/ready` — Readiness check (partial)

**Current Health Checks:**
- ✅ API service responsiveness
- ⚠️ Database connectivity (partial)
- ❌ Redis connectivity
- ❌ Milvus connectivity
- ❌ Dependency health aggregation

### 4.2 Recommended Health Check Implementation

```python
from fastapi import APIRouter, Response, status

router = APIRouter(prefix="/health")

@router.get("/live")
async def liveness():
    """Liveness probe - is the service running?"""
    return {"status": "healthy"}

@router.get("/ready")
async def readiness(response: Response):
    """Readiness probe - can the service handle traffic?"""
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
        "milvus": await check_milvus(),
    }
    
    all_healthy = all(checks.values())
    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    
    response.status_code = status_code
    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks
    }

@router.get("/startup")
async def startup(response: Response):
    """Startup probe - has initialization completed?"""
    # Check if memory manager is initialized, backends are ready, etc.
    initialized = await check_initialization()
    
    response.status_code = status.HTTP_200_OK if initialized else status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "started" if initialized else "starting"}

async def check_database():
    try:
        async with db.session() as session:
            await session.execute("SELECT 1")
        return True
    except Exception:
        return False

async def check_redis():
    try:
        await redis_client.ping()
        return True
    except Exception:
        return False

async def check_milvus():
    try:
        milvus_client.list_collections()
        return True
    except Exception:
        return False
```

### 4.3 Kubernetes Health Probes

```yaml
# Recommended probe configuration
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

startupProbe:
  httpGet:
    path: /health/startup
    port: 8000
  initialDelaySeconds: 0
  periodSeconds: 5
  timeoutSeconds: 5
  failureThreshold: 30  # Allow up to 150s for startup
```

---

## 5. Alerting

### 5.1 Recommended Alerts

**Critical (P0) — Page on-call:**

```yaml
# Prometheus alert rules
groups:
  - name: neuroca_critical
    interval: 30s
    rules:
      - alert: ServiceDown
        expr: up{job="neuroca-api"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Neuroca API service is down"
          
      - alert: HighErrorRate
        expr: rate(neuroca_api_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected (>5%)"
          
      - alert: DatabaseConnectionFailure
        expr: neuroca_db_connections_active == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool exhausted"
          
      - alert: MemoryCapacityExhausted
        expr: neuroca_memory_tier_capacity_used_percent > 95
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Memory tier {{ $labels.tier }} at >95% capacity"
```

**Warning (P1) — Notify team:**

```yaml
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(neuroca_api_request_duration_seconds_bucket[5m])) > 2.0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "API p95 latency >2s"
          
      - alert: ConsolidationBacklog
        expr: neuroca_consolidation_items_pending > 10000
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Consolidation backlog growing"
          
      - alert: LLMRateLimitApproaching
        expr: rate(neuroca_llm_requests_total[1h]) > 900
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Approaching LLM API rate limit (900/hour)"
```

### 5.2 Alert Routing

**Recommended channels:**
- **Critical:** PagerDuty/OpsGenie → On-call engineer
- **Warning:** Slack/Email → Team channel
- **Info:** Slack → Monitoring channel

---

## 6. Configuration Management

### 6.1 Current Approach

**Method:** Environment variables + `.env` files

**Strengths:**
- ✅ 12-factor app compliance
- ✅ Pydantic validation
- ✅ Type-safe configuration

**Configuration Schema:**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    
    # Database settings
    database_url: str
    db_pool_size: int = 20
    db_max_overflow: int = 40
    
    # Redis settings
    redis_url: str
    redis_max_connections: int = 50
    
    # Memory settings
    stm_ttl_seconds: int = 3600
    mtm_capacity: int = 10000
    ltm_consolidation_threshold: float = 0.7
    
    # LLM settings
    llm_provider: str = "openai"
    llm_api_key: str
    llm_model: str = "gpt-4"
    
    # Observability
    log_level: str = "INFO"
    metrics_enabled: bool = True
    tracing_enabled: bool = True
    tracing_sample_rate: float = 0.1
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

### 6.2 Feature Flags

**Current State:** ❌ Not implemented

**Recommendation: Implement feature flag system:**

```python
from typing import Dict
import os

class FeatureFlags:
    def __init__(self):
        self.flags: Dict[str, bool] = {
            "enable_gpu_embeddings": self._parse_bool("FF_GPU_EMBEDDINGS", False),
            "enable_query_cache": self._parse_bool("FF_QUERY_CACHE", True),
            "enable_distributed_consolidation": self._parse_bool("FF_DIST_CONSOLIDATION", False),
            "enable_experimental_decay": self._parse_bool("FF_EXP_DECAY", False),
        }
    
    def is_enabled(self, flag: str) -> bool:
        return self.flags.get(flag, False)
    
    @staticmethod
    def _parse_bool(key: str, default: bool) -> bool:
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")

feature_flags = FeatureFlags()
```

---

## 7. Operational Runbooks

### 7.1 Common Operations

**Memory Tier Capacity Management:**

```bash
# Check memory tier utilization
curl http://localhost:8000/metrics | grep neuroca_memory_tier_capacity

# Trigger manual consolidation
curl -X POST http://localhost:8000/admin/consolidate

# Adjust STM TTL (requires restart or hot reload)
export STM_TTL_SECONDS=7200
```

**Database Maintenance:**

```bash
# Check database size
psql -U neuroca -c "SELECT pg_size_pretty(pg_database_size('neuroca'));"

# Vacuum analyze
psql -U neuroca -c "VACUUM ANALYZE;"

# Check slow queries
psql -U neuroca -c "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"
```

**Redis Maintenance:**

```bash
# Check Redis memory usage
redis-cli INFO memory

# Check key count by tier
redis-cli KEYS "stm:*" | wc -l
redis-cli KEYS "cache:*" | wc -l

# Flush cache (use with caution)
redis-cli FLUSHDB
```

### 7.2 Incident Response

**High Error Rate:**
1. Check Grafana dashboard for error patterns
2. Query logs for error details: `grep ERROR logs/neuroca_*.log | tail -100`
3. Check external dependency health (LLM API, Milvus)
4. Review recent deployments
5. Roll back if necessary

**High Latency:**
1. Check Prometheus for slow endpoints
2. Query traces in Jaeger for slow operations
3. Check database slow query log
4. Check Milvus query performance
5. Scale horizontally if needed

**Memory Capacity Exhausted:**
1. Trigger manual consolidation
2. Adjust TTL settings
3. Increase tier capacity limits
4. Review memory growth rate
5. Consider vertical scaling

---

## 8. Summary & Prioritized Actions

### Immediate (P0)

1. ✅ **Implement correlation IDs** for distributed tracing
2. ✅ **Add log sanitization** for secrets/PII
3. ✅ **Complete health check** endpoints (Redis, Milvus)
4. ✅ **Set up Prometheus alerts** for critical metrics

### Short-term (P1)

1. **Complete OpenTelemetry instrumentation** across all services
2. **Implement comprehensive metrics** for all tiers and operations
3. **Set up log aggregation** (ELK/Loki)
4. **Create operational runbooks** for common scenarios

### Long-term (P2)

1. **Distributed tracing** with Jaeger/Tempo
2. **Feature flag system** for safe rollouts
3. **Automated alerting** with PagerDuty integration
4. **Performance profiling** dashboard in Grafana

---

_End of Operability Analysis_
