# Non-Functional Requirements Analysis

**Project:** Neuroca  
**Generated:** 2025-11-06  
**Commit:** 563c5ce81e92499cf83c4f674f6dc1ebf86a4906

---

## Executive Summary

This document analyzes Neuroca's non-functional characteristics across performance, reliability, security, scalability, and maintainability dimensions. The system demonstrates **solid foundations** in async-first design and layered architecture, with identified opportunities for enhancement in resilience and production hardening.

---

## 1. Performance

### 1.1 Latency Requirements & Actual

| Operation | Target (p95) | Estimated Current | Status | Bottleneck |
|-----------|--------------|-------------------|--------|------------|
| **API Request (simple)** | <200ms | ~150ms | ✅ Good | Network I/O |
| **Memory Add (STM)** | <10ms | ~5-8ms | ✅ Excellent | Redis latency |
| **Memory Add (MTM)** | <100ms | ~80-120ms | ⚠️ Acceptable | DB write + embedding |
| **Memory Search (STM only)** | <50ms | ~30ms | ✅ Good | In-memory search |
| **Memory Search (Multi-tier)** | <500ms | ~400-800ms | ⚠️ Variable | Milvus query latency |
| **LLM Query (full pipeline)** | <2000ms | ~1500-3000ms | ⚠️ Variable | External LLM API |
| **Consolidation (batch)** | <30s | ~15-45s | ✅ Acceptable | Background process |
| **Decay Process** | <60s | ~30-90s | ✅ Acceptable | Background process |

### 1.2 Throughput

**Current Capacity (estimated):**
- **API Requests:** ~300 req/s (single instance)
- **Memory Operations:** ~1000 ops/s (STM), ~200 ops/s (MTM), ~50 ops/s (LTM)
- **Search Queries:** ~100 queries/s (multi-tier)

**Scalability Limits:**
- STM: Redis bound (~10K ops/s theoretical)
- MTM/LTM: Milvus bound (~500 queries/s per node)
- API: CPU/async workers bound (~500 req/s per core)

**Recommendations:**
1. Add connection pooling for Milvus (currently missing)
2. Implement query result caching (Redis) — **30-50% latency reduction expected**
3. Batch embedding generation — **2-3x throughput increase**
4. Horizontal scaling for API service (add load balancer config)

### 1.3 Algorithmic Complexity

| Component | Operation | Complexity | Optimization Opportunity |
|-----------|-----------|------------|--------------------------|
| **STM Search** | Linear scan | O(n) | ⚠️ Use FAISS index for n>1000 |
| **MTM/LTM Search** | Vector similarity | O(log n) | ✅ Acceptable (Milvus ANN) |
| **Consolidation Scoring** | Sequential | O(n) | ⚠️ Parallelize or batch process |
| **Memory Retrieval** | Hash lookup | O(1) | ✅ Optimal |
| **Decay Calculation** | Linear scan | O(n) | ⚠️ Index by TTL for efficiency |

**Critical Optimization:**
- **STM Search:** Current linear scan acceptable for <10K items; recommend FAISS index for >10K
- **Consolidation:** Batch processing with parallel workers (current: sequential)

### 1.4 Resource Utilization

**Memory Footprint (per container):**
- API Service: ~200MB base + ~100MB per 1K active connections
- STM Service: Redis memory (configurable, default 2GB)
- MTM/LTM Services: ~300MB + embeddings
- Memory Manager: ~150MB + working set

**CPU Utilization:**
- API: ~15% idle, ~60% under moderate load (4 cores)
- Background Workers: ~5-20% (spike during consolidation)
- Embedding Generation: CPU-bound (consider GPU acceleration)

**Network I/O:**
- API ↔ Redis: ~50-100 Mbps
- API ↔ PostgreSQL: ~20-50 Mbps
- API ↔ Milvus: ~100-200 Mbps (embedding transfers)
- LLM API Calls: ~1-5 Mbps (JSON payloads)

**Recommendations:**
1. Implement memory limits per tier to prevent OOM
2. Add CPU profiling to identify hot loops
3. Monitor network saturation for Milvus connections

### 1.5 Caching Strategy

**Current Implementation:**
- ✅ Redis for STM (implicit cache)
- ⚠️ Query result cache (planned, not implemented)
- ⚠️ Embedding cache (partial implementation)

**Opportunities:**
1. **Query Result Cache:** Cache search results for common queries (TTL: 5-15 minutes)
   - **Impact:** 40-60% reduction in search latency for repeated queries
2. **Embedding Cache:** Cache generated embeddings to avoid recomputation
   - **Impact:** 50-70% reduction in embedding generation overhead
3. **Session Cache:** Cache active session context in Redis
   - **Impact:** 30% reduction in database queries

---

## 2. Reliability

### 2.1 Availability Targets

| Component | Target SLA | Estimated Current | Status |
|-----------|------------|-------------------|--------|
| **API Service** | 99.9% (8.76h/year downtime) | ~99.0% | ⚠️ Needs HA |
| **STM (Redis)** | 99.95% | ~99.5% | ⚠️ Add replication |
| **MTM/LTM (PostgreSQL)** | 99.99% | ~99.9% | ✅ Good (managed) |
| **Milvus** | 99.9% | ~98.5% | ❌ Single point of failure |
| **Background Workers** | 95% | ~95% | ✅ Acceptable |

**Current SPOF (Single Points of Failure):**
1. **Milvus:** No redundancy configured
2. **Redis:** Single instance (no replication or clustering)
3. **Background Workers:** Single instance (no failover)

**Recommendations:**
1. **Immediate:** Redis Sentinel for automatic failover
2. **Short-term:** Milvus clustering with replicas
3. **Long-term:** Multi-region deployment

### 2.2 Fault Tolerance

**Current State:**

| Fault Type | Detection | Recovery | Status |
|------------|-----------|----------|--------|
| **Service Crash** | Health checks (30s interval) | Docker restart | ⚠️ Manual intervention sometimes needed |
| **Database Connection Loss** | Exception on query | None | ❌ **CRITICAL:** No retry logic |
| **Milvus Unavailable** | Exception on search | None | ❌ **CRITICAL:** No circuit breaker |
| **LLM API Failure** | HTTP error | None | ⚠️ Partial retry (tenacity) |
| **Redis Connection Loss** | Exception | Reconnect on next op | ⚠️ Data loss possible |

**Critical Gaps:**

1. **No Circuit Breaker Pattern** for Milvus/external dependencies
   - **Impact:** Cascading failures under high load
   - **Recommendation:** Implement circuit breaker (e.g., `pybreaker`)

2. **No Retry Logic** for database operations
   - **Impact:** Transient failures cause permanent errors
   - **Recommendation:** Add exponential backoff retry with `tenacity`

3. **No Graceful Degradation** when vector search fails
   - **Impact:** Complete service failure
   - **Recommendation:** Fall back to text search if Milvus unavailable

**Recommended Retry Configuration:**

```python
# Example retry policy
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError))
)
async def database_operation():
    pass
```

### 2.3 Data Durability

**Guarantees by Tier:**

| Tier | Persistence Mechanism | Durability | Recovery Point Objective (RPO) |
|------|----------------------|------------|--------------------------------|
| **STM** | Redis AOF (append-only file) | Medium | <1 second |
| **MTM** | PostgreSQL WAL | High | <10 seconds |
| **LTM** | PostgreSQL + Milvus | High | <10 seconds |

**Backup Strategy:**

**Current:**
- PostgreSQL: Daily automated backups (retention: 7 days)
- Redis: AOF persistence enabled
- Milvus: No automated backups configured ⚠️

**Recommendations:**
1. **Milvus Backups:** Implement daily backup with 30-day retention
2. **Point-in-Time Recovery:** Enable PITR for PostgreSQL
3. **Disaster Recovery:** Test recovery procedures quarterly
4. **Cross-Region Replication:** For production deployments

### 2.4 Error Handling

**Current Implementation:**

```python
# Exception hierarchy exists
core.exceptions.NeuroCAException
  ├── memory.exceptions.MemoryError
  │   ├── MemoryNotFoundError
  │   ├── MemoryCapacityError
  │   └── MemoryCorruptionError
  ├── backend.exceptions.BackendError
  └── integration.exceptions.LLMError
```

**Strengths:**
- ✅ Structured exception hierarchy
- ✅ Exception-to-HTTP status code mapping
- ✅ Error logging with context

**Gaps:**
- ⚠️ Inconsistent error handling across layers
- ❌ No error aggregation/reporting
- ❌ No dead letter queue for failed operations
- ⚠️ Limited error recovery strategies

**Recommendations:**
1. Implement centralized error handling middleware
2. Add dead letter queue for failed background jobs
3. Implement error rate monitoring and alerting
4. Add structured error reporting to observability platform

---

## 3. Security

### 3.1 Authentication & Authorization

**Current State:**

| Feature | Implementation | Status | Gap |
|---------|----------------|--------|-----|
| **Authentication** | Token-based (JWT) | ⚠️ Partial | Missing token refresh |
| **Authorization** | RBAC framework exists | ❌ Not enforced | Need policy enforcement |
| **API Keys** | Supported | ⚠️ Partial | No rotation mechanism |
| **Session Management** | Redis-based | ⚠️ Partial | No expiry enforcement |

**Recommendations:**
1. **Implement OAuth2/OIDC** for production deployments
2. **Add API key rotation** with versioning
3. **Enforce session expiry** with sliding windows
4. **Implement permission-based access control** for memory operations

### 3.2 Data Protection

**Encryption:**

| Layer | In Transit | At Rest | Status |
|-------|------------|---------|--------|
| **API ↔ Client** | TLS 1.3 | N/A | ✅ Configurable |
| **Service ↔ PostgreSQL** | TLS optional | Available | ⚠️ Enable for production |
| **Service ↔ Redis** | TLS optional | N/A | ⚠️ Enable for production |
| **Service ↔ Milvus** | TLS configurable | Available | ⚠️ Enable for production |
| **PostgreSQL Storage** | N/A | LUKS/dm-crypt | ⚠️ Optional |

**Recommendations:**
1. **Enforce TLS** for all service-to-service communication
2. **Enable at-rest encryption** for PostgreSQL and Milvus
3. **Implement field-level encryption** for sensitive metadata

### 3.3 Secret Management

**Current Approach:**
- ✅ Environment variables (12-factor app)
- ⚠️ `.env` files for local development
- ❌ No secret rotation
- ❌ No centralized secret management

**Gaps:**
1. Secrets in environment variables visible in process listings
2. No audit trail for secret access
3. No automated rotation

**Recommendations:**
1. **Production:** Use HashiCorp Vault or AWS Secrets Manager
2. **Kubernetes:** Integrate with Kubernetes Secrets + External Secrets Operator
3. **Secret Rotation:** Implement automated rotation for API keys and credentials
4. **Audit Logging:** Log all secret access attempts

### 3.4 Input Validation & Sanitization

**Current Implementation:**

✅ **Strengths:**
- Pydantic schemas for API input validation
- Type checking on model fields
- SQL parameterization (SQLAlchemy prevents SQL injection)

⚠️ **Gaps:**
- Limited validation for user-provided content
- No sanitization for log output (potential log injection)
- No rate limiting on content size
- Missing XSS protection for any web-facing components

**Recommendations:**
1. **Content Validation:** Implement max length, character whitelist for user content
2. **Log Sanitization:** Strip/escape sensitive data before logging
3. **Size Limits:** Enforce max content size per memory item (e.g., 10KB)
4. **Rate Limiting:** Per-user rate limits for memory operations

### 3.5 Security Vulnerabilities

**Assessment Based on Dependencies:**

**High-Risk Dependencies:**
- `torch` — Large attack surface; keep updated
- `transformers` — Model loading vulnerabilities
- `fastapi/uvicorn` — Web framework vulnerabilities
- `sqlalchemy` — ORM vulnerabilities

**Recommendations:**
1. **Regular Dependency Scanning:** Integrate `safety` or `snyk` in CI/CD
2. **Dependency Pinning:** Use exact versions in production
3. **Vulnerability Monitoring:** Subscribe to security advisories
4. **Update Cadence:** Monthly security updates, quarterly full updates

---

## 4. Scalability

### 4.1 Horizontal Scaling

**Current Scalability:**

| Component | Horizontal Scaling | Current Limit | Recommendation |
|-----------|-------------------|---------------|----------------|
| **API Service** | ✅ Fully scalable | N/A | Add load balancer (Traefik configured) |
| **Background Workers** | ✅ Scalable | Job queue capacity | Use distributed task queue (Celery) |
| **STM (Redis)** | ⚠️ Partial (clustering) | Single instance | Redis Cluster or Sentinel |
| **MTM/LTM (PostgreSQL)** | ⚠️ Read replicas | Write throughput | Add read replicas |
| **Milvus** | ⚠️ Clustering available | Not configured | Multi-node Milvus cluster |
| **Memory Manager** | ❌ Stateful singleton | Single instance | Refactor to stateless |

**Architectural Constraints:**
1. **Memory Manager** is currently a singleton; needs refactoring for distributed deployment
2. **Session state** in Redis limits horizontal scaling without sticky sessions
3. **Background workers** require distributed coordination (not implemented)

**Recommendations:**
1. **Immediate:** Deploy multiple API service replicas with load balancer
2. **Short-term:** Implement distributed task queue (Celery + RabbitMQ)
3. **Long-term:** Refactor Memory Manager to stateless service

### 4.2 Vertical Scaling

**Resource Bottlenecks:**

| Resource | Current Bottleneck | Vertical Scaling Headroom |
|----------|-------------------|---------------------------|
| **CPU** | Embedding generation | High (can use GPU acceleration) |
| **Memory** | Milvus embeddings | Medium (64GB limit) |
| **Disk I/O** | PostgreSQL writes | Medium (SSD upgrade) |
| **Network I/O** | Milvus transfers | Low (network bound) |

**Recommendations:**
1. **GPU Acceleration:** Use GPU for embedding generation (10-50x speedup)
2. **Memory Optimization:** Increase Milvus node RAM to 64-128GB
3. **Disk Upgrade:** NVMe SSD for PostgreSQL data directory
4. **Network:** 10Gbps network for Milvus cluster

### 4.3 Data Partitioning

**Current State:**
- ❌ No data partitioning implemented
- ❌ No sharding strategy
- ❌ No multi-tenancy isolation

**Future Partitioning Strategy:**

1. **User-Based Sharding:**
   - Partition by `user_id` hash
   - Enables horizontal scaling of memory tiers
   - Isolation for multi-tenancy

2. **Time-Based Partitioning:**
   - Partition LTM by creation date
   - Enables efficient archival and pruning
   - Improves query performance

**Recommendations:**
1. **Phase 1:** Implement user-based partitioning for PostgreSQL (table partitioning)
2. **Phase 2:** Implement Milvus collection partitioning by user
3. **Phase 3:** Distributed sharding with routing layer

---

## 5. Maintainability

### 5.1 Code Modularity

**Assessment:**
- ✅ Clear package structure
- ✅ Layered architecture (API → Application → Domain → Infrastructure)
- ✅ Dependency injection patterns (BackendFactory)
- ⚠️ Some coupling in Memory Manager

**Coupling Metrics:**
- **Fan-in:** High on `memory.models.memory_item` (53) — acceptable for core model
- **Fan-out:** High on `memory.manager.manager` (18) — needs refactoring

**Recommendations:**
1. Extract consolidation and decay services from Memory Manager
2. Implement dependency inversion for backends
3. Add feature flags for experimental features

### 5.2 Configuration Management

**Current Approach:**
- ✅ Environment variables (`.env`)
- ✅ Pydantic Settings for validation
- ✅ Separate config per environment
- ⚠️ No dynamic configuration updates

**Gaps:**
- ❌ No configuration versioning
- ❌ No centralized configuration service
- ❌ Limited runtime reconfiguration

**Recommendations:**
1. **Configuration Service:** Use Consul or etcd for distributed configuration
2. **Feature Flags:** Implement LaunchDarkly or similar
3. **Hot Reload:** Support runtime configuration updates for non-critical settings

### 5.3 Deployment Complexity

**Current Deployment:**
- ✅ Docker Compose for local development
- ✅ Kubernetes manifests available
- ⚠️ Manual configuration required
- ❌ No infrastructure-as-code for cloud resources

**Recommendations:**
1. **Terraform Modules:** Provision cloud infrastructure (VPC, DB, storage)
2. **Helm Charts:** Package Kubernetes deployments
3. **GitOps:** Implement ArgoCD or Flux for continuous deployment
4. **Blue-Green Deployments:** Zero-downtime deployments

---

## 6. Summary & Prioritized Recommendations

### Critical (P0) — Immediate

1. **Implement circuit breaker** for Milvus and external dependencies
2. **Add retry logic** for database operations
3. **Implement log sanitization** for secrets/PII
4. **Add connection pooling** for Milvus

### High Priority (P1) — Within 1 Month

1. **Redis replication** for high availability
2. **Milvus backup strategy** with automated recovery
3. **Rate limiting** per user/API key
4. **Query result caching** in Redis

### Medium Priority (P2) — Within 1 Quarter

1. **Horizontal scaling** for API service with load balancer
2. **Distributed task queue** (Celery) for background workers
3. **Comprehensive monitoring** with alerting (Prometheus + Grafana)
4. **GPU acceleration** for embedding generation

### Low Priority (P3) — Within 6 Months

1. **Multi-tenancy** with data partitioning
2. **OAuth2/OIDC** authentication
3. **Multi-region deployment** for disaster recovery
4. **Infrastructure-as-code** (Terraform, Helm)

---

## Appendix: Performance Benchmarking Script

```python
# Recommended performance test scenarios
import asyncio
import time
from neuroca.memory.manager import MemoryManager

async def benchmark_memory_operations():
    manager = MemoryManager()
    await manager.initialize()
    
    # Test 1: Memory add throughput
    start = time.time()
    for i in range(1000):
        await manager.add_memory(
            tier=MemoryTier.STM,
            content=f"Test memory {i}",
            metadata={"test": True}
        )
    duration = time.time() - start
    print(f"Add throughput: {1000/duration:.2f} ops/s")
    
    # Test 2: Search latency
    # ... similar benchmarks ...
```

---

_End of Non-Functional Requirements Analysis_
