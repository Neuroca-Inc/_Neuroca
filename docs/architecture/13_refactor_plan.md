# Refactor Plan — Technical Debt & Improvement Roadmap

**Project:** Neuroca  
**Generated:** 2025-11-06  
**Commit:** 563c5ce81e92499cf83c4f674f6dc1ebf86a4906

---

## Executive Summary

This document outlines a prioritized refactoring roadmap organized into **Quick Wins** (1-2 days), **Medium Efforts** (1-2 sprints), and **Strategic Initiatives** (3-6 months). The plan addresses technical debt, architecture improvements, and scalability enhancements.

**Total Estimated Effort:** ~18 weeks (person-weeks)

---

## Quick Wins (1-2 Days Each)

### QW1: Remove BOM Characters
**Effort:** 1 hour  
**Files:** `scripts/__init__.py`, `tools/__init__.py`  
**Action:** Remove U+FEFF byte-order marks

### QW2: Fix Invalid Escape Sequence
**Effort:** 1 hour  
**File:** `core/utils/__init__.py:137`  
**Action:** Use raw string literal or properly escape

### QW3: Add Correlation IDs
**Effort:** 4 hours  
**Impact:** High — enables distributed tracing  
**Implementation:**
- Add middleware to FastAPI
- Use `contextvars` for thread-local storage
- Propagate via HTTP headers

### QW4: Implement Log Sanitization
**Effort:** 8 hours  
**Impact:** Critical — prevents secret leakage  
**Implementation:**
- Create sanitizer utility function
- Apply to all log statements
- Test with known sensitive patterns

### QW5: Add Hard Memory Limits
**Effort:** 6 hours  
**Impact:** High — prevents OOM  
**Files:** `memory/tiers/stm.py`  
**Implementation:**
- Add max_items configuration
- Implement LRU eviction when at capacity

### QW6: Connection Pooling for Milvus
**Effort:** 8 hours  
**Impact:** High — prevents connection exhaustion  
**Implementation:**
- Add connection pool wrapper
- Configure min/max connections
- Add connection health checks

---

## Medium Efforts (1-2 Sprints Each)

### ME1: Refactor Memory Manager
**Effort:** 2 weeks  
**Impact:** Critical — reduces coupling, improves maintainability  
**Current State:** Monolithic manager with 18+ dependencies  

**Refactoring Strategy:**
1. Extract `ConsolidationService` (3 days)
2. Extract `DecayService` (2 days)
3. Extract `SearchCoordinator` (3 days)
4. Refactor `MemoryOrchestrator` to coordinate services (2 days)
5. Update tests (2 days)

**Target Architecture:**
```
MemoryOrchestrator
  ├── ConsolidationService
  ├── DecayService
  ├── SearchCoordinator
  └── BackendFactory
```

### ME2: Implement Circuit Breaker
**Effort:** 1 week  
**Impact:** High — prevents cascading failures  
**Dependencies:** Milvus, LLM APIs  

**Implementation:**
```python
from pybreaker import CircuitBreaker

milvus_breaker = CircuitBreaker(
    fail_max=5,
    timeout_duration=60,
    expected_exception=MilvusConnectionError
)

@milvus_breaker
async def search_vector(embedding):
    # ... milvus search logic
```

### ME3: Add Comprehensive Integration Tests
**Effort:** 2 weeks  
**Impact:** High — improves reliability  
**Coverage Target:** >70%  

**Test Scenarios:**
1. Consolidation pipeline (STM → MTM → LTM)
2. Decay process with various functions
3. Multi-tier search with ranking
4. LLM integration with context assembly
5. Error recovery and retry logic

### ME4: Implement Query Result Caching
**Effort:** 1 week  
**Impact:** Medium — 40-60% latency reduction  

**Implementation:**
- Cache key: hash(query_embedding + filters)
- TTL: 5-15 minutes
- Cache invalidation: on memory updates in queried tiers

### ME5: Add Distributed Task Queue
**Effort:** 2 weeks  
**Impact:** High — enables horizontal scaling of workers  
**Technology:** Celery + RabbitMQ  

**Tasks to Migrate:**
- Consolidation jobs
- Decay jobs
- Batch embedding generation
- Report generation

### ME6: Enable MyPy for Core Modules
**Effort:** 1.5 weeks  
**Impact:** Medium — improves code quality  

**Rollout Plan:**
1. Enable for `core/enums.py` (already done)
2. Enable for `memory/models/*` (2 days)
3. Enable for `memory/manager/*` (3 days)
4. Enable for `api/routes/*` (2 days)
5. Enable for `core/*` (2 days)

---

## Strategic Initiatives (3-6 Months)

### SI1: Microservices Extraction
**Effort:** 8 weeks  
**Impact:** Critical — enables independent scaling  

**Phase 1: Extract Memory Tier Services (4 weeks)**
- Separate services for STM, MTM, LTM
- gRPC APIs between services
- Independent deployment and scaling

**Phase 2: Extract Background Services (2 weeks)**
- Consolidation service
- Decay service
- Job scheduler

**Phase 3: API Gateway (2 weeks)**
- Unified API gateway
- Service discovery
- Load balancing

**Target Architecture:**
```
API Gateway
  ├── STM Service (stateless, Redis backend)
  ├── MTM Service (stateless, PostgreSQL + Milvus)
  ├── LTM Service (stateless, PostgreSQL + Milvus)
  ├── Consolidation Service (worker pool)
  ├── Decay Service (worker pool)
  └── LLM Integration Service
```

### SI2: Multi-Tenancy Support
**Effort:** 6 weeks  
**Impact:** High — enables SaaS deployment  

**Implementation:**
1. **Data Partitioning (2 weeks)**
   - PostgreSQL table partitioning by tenant_id
   - Milvus collection per tenant or partitioning
   - Redis namespace per tenant

2. **Tenant Isolation (2 weeks)**
   - Tenant context middleware
   - Row-level security in PostgreSQL
   - Tenant-aware queries

3. **Billing & Quotas (2 weeks)**
   - Usage tracking per tenant
   - Quota enforcement
   - Billing integration

### SI3: Event Sourcing & CQRS
**Effort:** 8 weeks  
**Impact:** High — improves auditability, enables time travel  

**Implementation:**
1. **Event Store (2 weeks)**
   - Event schema design
   - Event store implementation (PostgreSQL or EventStoreDB)
   - Event publishing

2. **Command Handlers (3 weeks)**
   - Separate write models (commands)
   - Event generation
   - Aggregate root patterns

3. **Query Models (2 weeks)**
   - Read model projections
   - Materialized views
   - Query optimization

4. **Event Replay (1 week)**
   - Event replay mechanism
   - Projection rebuilding
   - Time-travel queries

### SI4: GPU Acceleration for Embeddings
**Effort:** 4 weeks  
**Impact:** High — 10-50x speedup  

**Implementation:**
1. **GPU Detection & Initialization (1 week)**
   - Detect CUDA availability
   - Initialize GPU models
   - Fallback to CPU

2. **Batch Processing (1 week)**
   - Accumulate embedding requests
   - Batch processing (size: 32-128)
   - Parallel GPU execution

3. **Model Optimization (1 week)**
   - Model quantization (FP16/INT8)
   - TensorRT optimization
   - ONNX export

4. **Performance Testing (1 week)**
   - Benchmark GPU vs CPU
   - Profile memory usage
   - Optimize batch sizes

### SI5: Data Partitioning & Sharding
**Effort:** 6 weeks  
**Impact:** Critical — enables horizontal data scaling  

**Implementation:**
1. **Shard Key Design (1 week)**
   - Choose shard key (user_id hash)
   - Plan shard count (start with 16)
   - Rebalancing strategy

2. **PostgreSQL Partitioning (2 weeks)**
   - Native table partitioning
   - Partition-aware queries
   - Partition maintenance

3. **Milvus Sharding (2 weeks)**
   - Multi-collection strategy
   - Shard routing layer
   - Query federation

4. **Routing Layer (1 week)**
   - Shard router implementation
   - Consistent hashing
   - Shard affinity caching

---

## Dependency Cleanup

### Remove Unused Dependencies
**Effort:** 2 days  
**Identified:**
- Old analysis artifacts
- Deprecated libraries
- Development-only deps in production

### Update Outdated Dependencies
**Effort:** 1 week  
**Process:**
1. Run `poetry update --dry-run`
2. Review breaking changes
3. Update incrementally
4. Run full test suite after each update

**Critical Updates:**
- `fastapi` → latest stable
- `pydantic` → 2.x (already done)
- `sqlalchemy` → latest 2.x
- Security patches for all deps

---

## Performance Optimization

### PO1: Query Optimization
**Effort:** 1 week  
**Focus:**
- Add indexes for common queries
- Eliminate N+1 patterns
- Use eager loading for relationships
- Implement query result caching

### PO2: Embedding Generation Optimization
**Effort:** 1 week  
**Strategies:**
- Batch processing
- Embedding caching
- Model quantization
- GPU acceleration (see SI4)

### PO3: Connection Pool Tuning
**Effort:** 3 days  
**Targets:**
- PostgreSQL pool size optimization
- Redis connection pooling
- Milvus connection management

---

## Documentation Improvements

### DI1: API Documentation
**Effort:** 1 week  
**Deliverables:**
- Complete OpenAPI 3.0 spec
- Interactive API docs (Swagger UI)
- Code examples for each endpoint
- Authentication guide

### DI2: Developer Onboarding
**Effort:** 3 days  
**Content:**
- Setup guide
- Architecture overview
- Development workflow
- Testing guide
- Contribution guidelines

### DI3: Operations Runbooks
**Effort:** 1 week  
**Topics:**
- Deployment procedures
- Scaling guidelines
- Incident response
- Common troubleshooting
- Backup and recovery

---

## Testing Improvements

### TI1: Increase Unit Test Coverage
**Effort:** 2 weeks  
**Target:** >80% coverage  
**Priority Areas:**
- Memory manager operations
- Backend adapters
- Domain models
- Utility functions

### TI2: Integration Test Suite
**Effort:** 2 weeks  
**Coverage:**
- Database operations
- Redis operations
- Milvus operations
- LLM integrations
- End-to-end pipelines

### TI3: Performance Regression Tests
**Effort:** 1 week  
**Metrics:**
- API latency benchmarks
- Memory operation throughput
- Search query performance
- Consolidation duration

---

## Security Hardening

### SH1: Secret Management
**Effort:** 1 week  
**Implementation:**
- HashiCorp Vault integration
- Secret rotation mechanism
- Audit logging for secret access

### SH2: Rate Limiting
**Effort:** 3 days  
**Levels:**
- Global rate limits
- Per-user rate limits
- Per-endpoint rate limits

### SH3: Input Validation
**Effort:** 3 days  
**Enhancements:**
- Content size limits
- Character whitelist/blacklist
- Injection attack prevention

---

## Prioritization Matrix

| Initiative | Effort | Impact | Priority | Quarter |
|-----------|--------|--------|----------|---------|
| QW3: Correlation IDs | Low | High | **P0** | Q1 |
| QW4: Log Sanitization | Low | Critical | **P0** | Q1 |
| QW5: Memory Limits | Low | High | **P0** | Q1 |
| QW6: Connection Pooling | Low | High | **P0** | Q1 |
| ME1: Refactor Manager | High | Critical | **P1** | Q1 |
| ME2: Circuit Breaker | Medium | High | **P1** | Q1 |
| ME3: Integration Tests | High | High | **P1** | Q1-Q2 |
| ME4: Query Caching | Medium | Medium | **P2** | Q2 |
| ME5: Task Queue | High | High | **P1** | Q2 |
| SI1: Microservices | Very High | Critical | **P2** | Q2-Q3 |
| SI2: Multi-Tenancy | High | High | **P2** | Q3 |
| SI3: Event Sourcing | Very High | Medium | **P3** | Q4 |
| SI4: GPU Acceleration | High | High | **P2** | Q3 |
| SI5: Data Sharding | High | Critical | **P2** | Q3-Q4 |

---

## Rollout Strategy

### Phase 1: Foundation (Q1 - Weeks 1-4)
- All Quick Wins
- Circuit breaker implementation
- Start Memory Manager refactoring

### Phase 2: Resilience (Q1-Q2 - Weeks 5-12)
- Complete Memory Manager refactor
- Integration test suite
- Distributed task queue
- Query result caching

### Phase 3: Scale (Q2-Q3 - Weeks 13-24)
- Microservices extraction
- Multi-tenancy support
- GPU acceleration
- Data sharding

### Phase 4: Advanced (Q3-Q4 - Weeks 25-40)
- Event sourcing (optional)
- Advanced analytics
- ML-based optimization

---

## Success Metrics

| Metric | Current | Target (6 months) |
|--------|---------|-------------------|
| Test Coverage | ~45% | >80% |
| Deployment Frequency | Weekly | Daily |
| Mean Time to Recovery | ~2 hours | <30 minutes |
| P95 API Latency | ~500ms | <200ms |
| System Availability | ~99.0% | >99.9% |
| Technical Debt Ratio | ~25% | <15% |

---

_End of Refactor Plan_
