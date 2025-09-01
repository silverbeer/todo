# OpenTelemetry Observability Implementation Plan

**Goal**: Implement comprehensive observability using OpenTelemetry's three pillars (traces, metrics, logs) with the Grafana stack following industry standards and best practices.

**Target Stack**: OpenTelemetry → Grafana (Tempo + Prometheus/Cloud + Loki)

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [OpenTelemetry Three Pillars Overview](#opentelemetry-three-pillars-overview)
3. [Technical Architecture](#technical-architecture)
4. [Implementation Phases](#implementation-phases)
5. [Development Workflow](#development-workflow)
6. [Configuration Specifications](#configuration-specifications)
7. [Testing Strategy](#testing-strategy)
8. [Migration Path](#migration-path)
9. [Monitoring & Alerting](#monitoring--alerting)
10. [Resources & References](#resources--references)

---

## Current State Analysis

### What We Have Now ❌
- **Unstructured logging**: Scattered `print()` statements throughout codebase
- **Rich console output**: User-facing terminal formatting (good to keep)
- **No observability**: Zero visibility into application performance
- **No correlation**: Cannot trace operations across components
- **Mixed concerns**: Debug info mixed with user-facing output
- **No metrics**: No performance or business metrics collection
- **No distributed tracing**: Cannot see request flows

### Current Logging Locations
```bash
# Database layer
src/todo/db/migrations.py:91    - print("✅ Database schema initialized")
src/todo/db/connection.py:59    - print(f"Error executing statement")

# AI enrichment layer
src/todo/ai/enrichment_service.py:53  - print("Warning: No AI providers available")
src/todo/ai/background.py:62          - print(f"Background enrichment failed")

# CLI layer
src/todo/cli/main.py - 40+ console.print() statements (user-facing, keep these)
```

### Problems with Current Approach
- **No structured data**: Cannot query or aggregate logs
- **No correlation**: Cannot trace a todo creation through AI enrichment
- **No performance metrics**: Cannot measure AI response times
- **No error tracking**: Cannot aggregate error patterns
- **Not production-ready**: Cannot operate this in production environments

---

## OpenTelemetry Three Pillars Overview

### 1. **Traces** (Stable ✅)
**Purpose**: Track request flows and timing across distributed components

**What we'll trace**:
- **CLI Commands**: `todo add`, `todo complete`, `todo enrich`
- **AI Enrichment Flow**: API calls → response processing → database storage
- **Database Operations**: Queries, transactions, migrations
- **Background Processing**: Async enrichment, cleanup tasks

**Benefits**:
- See exactly how long AI enrichment takes
- Identify bottlenecks in database operations
- Trace errors through the entire request flow
- Understand concurrent operation performance

### 2. **Metrics** (Stable ✅)
**Purpose**: Collect performance counters and business metrics

**RED Metrics** (Rate, Errors, Duration):
- Command execution rates
- Error percentages by operation type
- Response time distributions

**Business Metrics**:
- Todos created/completed per day
- AI suggestion acceptance rates
- User activity patterns
- Database query performance

**System Metrics**:
- Memory usage patterns
- Database connection pool status
- API rate limiting status

### 3. **Logs** (In Development, but usable 🚧)
**Purpose**: Structured events with full context correlation

**Features**:
- JSON-formatted logs with consistent schema
- Automatic trace correlation (trace_id, span_id in every log)
- Proper log levels (DEBUG, INFO, WARN, ERROR)
- Structured attributes following semantic conventions
- Separate from user-facing console output

---

## Technical Architecture

### Core Dependencies
```toml
# Add to pyproject.toml dependencies
"opentelemetry-api>=1.21.0",
"opentelemetry-sdk>=1.21.0",
"opentelemetry-exporter-otlp>=1.21.0",
"opentelemetry-instrumentation-requests>=0.42b0",
"opentelemetry-instrumentation-asyncio>=0.42b0",
"opentelemetry-instrumentation-logging>=0.42b0",
"opentelemetry-semantic-conventions>=0.42b0",
```

### Project Structure Additions
```
src/todo/
├── observability/           # New observability module
│   ├── __init__.py
│   ├── config.py           # OTEL configuration
│   ├── tracing.py          # Tracing utilities
│   ├── metrics.py          # Metrics collection
│   ├── logging.py          # Structured logging
│   └── decorators.py       # Instrumentation decorators
├── ai/
├── cli/
├── core/
└── db/
```

### Grafana Stack Integration

**Architecture Flow**:
```
Todo App
    ↓ OTLP
OTEL Collector (optional)
    ↓
Grafana Stack:
├── Tempo (traces)
├── Prometheus/Cloud (metrics)
└── Loki (logs)
```

**Direct Export Option**:
```
Todo App → Direct OTLP → Grafana Cloud
```

---

## Implementation Phases

### Phase 1: Foundation & Core Setup 🏗️
**Estimated Time**: 1-2 days

**Tasks**:
- [ ] Add OTEL dependencies to `pyproject.toml`
- [ ] Create `src/todo/observability/` module structure
- [ ] Implement basic OTEL SDK initialization
- [ ] Configure OTLP exporters for development
- [ ] Add environment-based configuration
- [ ] Create CLI flags (`--verbose`, `--debug`, `--trace`)

**Deliverables**:
- Basic OTEL initialization working
- Can export to local OTEL collector or console
- CLI flags control observability verbosity

**Testing**:
```bash
# Should show traces in console
uv run todo --trace add "Test task"

# Should export to local collector
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
uv run todo add "Test task"
```

### Phase 2: Distributed Tracing Implementation 🔍
**Estimated Time**: 2-3 days

**Tasks**:
- [ ] Instrument CLI commands with root spans
- [ ] Add AI enrichment tracing (OpenAI/Anthropic API calls)
- [ ] Instrument database operations with spans
- [ ] Add async operation correlation
- [ ] Implement span attributes following semantic conventions
- [ ] Add custom span events for key milestones

**Span Hierarchy Example**:
```
todo.command.add [3.2s]
├── db.todo.create [45ms]
├── ai.enrichment.analyze [2.8s]
│   ├── ai.provider.openai.request [2.1s]
│   ├── ai.response.parse [12ms]
│   └── db.ai_enrichment.save [23ms]
└── cli.display.results [15ms]
```

**Deliverables**:
- Complete request flow visibility
- Performance bottleneck identification
- Error propagation tracking

### Phase 3: Metrics Collection & Monitoring 📊
**Estimated Time**: 2-3 days

**Tasks**:
- [ ] Implement RED metrics for all operations
- [ ] Add business metrics collection
- [ ] Create custom metric instruments
- [ ] Configure Prometheus/Grafana Cloud export
- [ ] Build initial Grafana dashboards
- [ ] Set up basic alerting rules

**Key Metrics**:
```python
# RED Metrics
command_duration = Histogram("todo_command_duration_seconds")
command_errors = Counter("todo_command_errors_total")
command_rate = Counter("todo_commands_total")

# Business Metrics
todos_created = Counter("todos_created_total")
ai_suggestions_accepted = Counter("ai_suggestions_accepted_total")
ai_enrichment_duration = Histogram("ai_enrichment_duration_seconds")

# System Metrics
db_connections = Gauge("database_connections_active")
api_rate_limits = Gauge("api_rate_limit_remaining")
```

**Grafana Dashboards**:
- Service Overview (RED metrics, error rates)
- AI Performance (enrichment success, response times)
- Business Intelligence (user activity, completion rates)

### Phase 4: Structured Logging with Correlation 📝
**Estimated Time**: 2-3 days

**Tasks**:
- [ ] Replace all `print()` statements with structured logging
- [ ] Implement trace correlation in logs (trace_id, span_id)
- [ ] Add semantic log attributes
- [ ] Configure Loki export and label strategy
- [ ] Implement log sampling for performance
- [ ] Keep Rich console output for user-facing messages

**Log Structure**:
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "service": "todo-cli",
  "version": "0.1.0",
  "trace_id": "abc123...",
  "span_id": "def456...",
  "operation": "ai.enrichment",
  "user_context": "cli_user",
  "message": "AI enrichment completed",
  "attributes": {
    "todo_id": 42,
    "provider": "openai",
    "model": "gpt-4o-mini",
    "confidence": 0.95,
    "duration_ms": 1847
  }
}
```

**Loki Labels Strategy**:
```yaml
# Efficient querying in Loki
labels:
  service: todo-cli
  level: info|warn|error
  operation: ai.enrichment|db.query|cli.command
  environment: dev|staging|prod
```

### Phase 5: Advanced Features & Production Readiness 🚀
**Estimated Time**: 2-3 days

**Tasks**:
- [ ] Implement baggage for cross-cutting context
- [ ] Add resource detection (container, cloud environment)
- [ ] Optimize sampling rates for production
- [ ] Add advanced error tracking and context
- [ ] Create operational dashboards and runbooks
- [ ] Performance testing and optimization

**Advanced Features**:
- **Baggage**: User ID, session ID, operation context
- **Resource Detection**: Automatically detect k8s, cloud provider
- **Sampling**: Intelligent trace sampling based on error rates
- **Error Tracking**: Enhanced error context with stack traces

---

## Development Workflow

### Branch Strategy
```bash
# Create feature branch
git checkout -b feature/otel-observability

# Work in phases - create sub-branches for each phase
git checkout -b feature/otel-phase-1-foundation
git checkout -b feature/otel-phase-2-tracing
git checkout -b feature/otel-phase-3-metrics
git checkout -b feature/otel-phase-4-logging
git checkout -b feature/otel-phase-5-advanced
```

### Development Setup
```bash
# Install development dependencies
uv sync --dev

# Add OTEL packages
uv add "opentelemetry-api>=1.21.0"
uv add "opentelemetry-sdk>=1.21.0"
uv add "opentelemetry-exporter-otlp>=1.21.0"

# Local OTEL collector setup (optional)
docker run -p 4317:4317 -p 16686:16686 jaegertracing/all-in-one:latest
```

### Testing Each Phase
```bash
# Phase 1: Basic OTEL initialization
uv run todo --trace version
# Should show trace output in console

# Phase 2: Tracing
uv run todo --trace add "Test task"
# Should show span hierarchy

# Phase 3: Metrics
curl http://localhost:8000/metrics  # If we add metrics endpoint
# Should show Prometheus metrics

# Phase 4: Structured logging
uv run todo --debug add "Test task"
# Should show structured JSON logs

# Phase 5: Full integration
# Should work with Grafana stack
```

---

## Configuration Specifications

### Environment Variables
```bash
# OTEL Configuration
OTEL_SERVICE_NAME=todo-cli
OTEL_SERVICE_VERSION=0.1.0
OTEL_ENVIRONMENT=development
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer ${GRAFANA_CLOUD_TOKEN}"

# Grafana Cloud Endpoints (production)
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://tempo-prod-us-central1.grafana.net:443/v1/traces
OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=https://prometheus-prod-us-central1.grafana.net/api/prom/push
OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=https://logs-prod-us.grafana.net/v1/logs

# Application Configuration
TODO_LOG_LEVEL=INFO
TODO_TRACE_SAMPLE_RATE=1.0
TODO_ENABLE_METRICS=true
TODO_ENABLE_TRACES=true
TODO_ENABLE_LOGS=true
```

### CLI Configuration
```bash
# New CLI flags to add
--verbose        # Enable DEBUG level logging
--debug          # Enable DEBUG + trace/span details
--trace          # Enable console trace export
--no-telemetry   # Disable all OTEL (privacy mode)
--log-format     # json|console (default: console for CLI, json for export)
```

### Configuration File Support
```toml
# ~/.config/todo/config.toml
[observability]
enabled = true
log_level = "INFO"
export_traces = true
export_metrics = true
export_logs = true
sample_rate = 1.0

[grafana]
endpoint = "https://grafana-cloud-endpoint"
api_key = "${GRAFANA_API_KEY}"
```

---

## Testing Strategy

### Unit Testing OTEL Integration
```python
# Test trace generation
def test_trace_creation():
    with tracer.start_as_current_span("test_span") as span:
        span.set_attribute("test.attribute", "value")
        # Verify span attributes

# Test metrics collection
def test_metrics_collection():
    todo_counter.add(1, {"operation": "create"})
    # Verify metric recorded

# Test structured logging
def test_structured_logging():
    logger.info("Test message", extra={"todo_id": 123})
    # Verify log structure and trace correlation
```

### Integration Testing
```python
# Test full request flow tracing
@pytest.mark.asyncio
async def test_enrichment_tracing():
    result = await enrichment_service.enrich_todo("Test task")
    # Verify traces captured entire flow

# Test metrics export
def test_metrics_export():
    # Run operations that generate metrics
    # Verify metrics available in test endpoint
```

### E2E Testing with Grafana Stack
```bash
# Docker Compose setup for local Grafana stack
docker-compose -f docker-compose.observability.yml up -d

# Run E2E tests
uv run pytest tests/e2e/test_observability.py -v

# Verify dashboards
curl -H "Authorization: Bearer $GRAFANA_TOKEN" \
  http://localhost:3000/api/search
```

---

## Migration Path

### Phase-by-Phase Migration
1. **Phase 1**: No breaking changes, OTEL initialization is optional
2. **Phase 2**: Replace print() statements gradually, keep backwards compatibility
3. **Phase 3**: Metrics are additive, no breaking changes
4. **Phase 4**: Logging migration requires careful testing
5. **Phase 5**: Advanced features are opt-in

### Backwards Compatibility
- Keep existing Rich console output for users
- OTEL can be disabled completely via environment variable
- Graceful degradation if OTEL export fails
- No performance impact when observability disabled

### Production Migration Strategy
```bash
# Stage 1: Deploy with OTEL disabled
OTEL_ENABLED=false

# Stage 2: Enable with console export only
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_TRACES_EXPORTER=console

# Stage 3: Enable export to Grafana Cloud
OTEL_EXPORTER_OTLP_ENDPOINT=https://grafana-cloud...

# Stage 4: Enable all features
OTEL_ENABLE_METRICS=true
OTEL_ENABLE_LOGS=true
```

---

## Monitoring & Alerting

### Key Alerts to Set Up
```yaml
# Grafana Alerting Rules
alerts:
  - name: High Error Rate
    condition: error_rate > 5%
    duration: 5m

  - name: AI Enrichment Slow
    condition: ai_enrichment_p95 > 10s
    duration: 2m

  - name: Database Connection Issues
    condition: db_connection_errors > 0
    duration: 1m

  - name: No Telemetry Data
    condition: absent(traces) OR absent(metrics)
    duration: 5m
```

### SLIs/SLOs to Track
- **Availability**: 99.5% of commands complete successfully
- **Latency**: 95% of AI enrichments complete within 5 seconds
- **Quality**: AI suggestions have >80% user acceptance rate

### Operational Dashboards
1. **Service Health**: RED metrics, error rates, latency percentiles
2. **AI Performance**: Model response times, success rates, token usage
3. **Business Intelligence**: User activity, feature adoption, completion rates
4. **Infrastructure**: Database performance, API rate limits, resource usage

---

## Resources & References

### OpenTelemetry Documentation
- [OTEL Python Documentation](https://opentelemetry.io/docs/languages/python/)
- [OTEL Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- [OTEL Best Practices](https://opentelemetry.io/docs/best-practices/)

### Grafana Integration
- [Grafana Tempo](https://grafana.com/docs/tempo/latest/) - Distributed tracing
- [Grafana Loki](https://grafana.com/docs/loki/latest/) - Log aggregation
- [Grafana Cloud](https://grafana.com/docs/grafana-cloud/) - Managed service

### Python Implementation Examples
- [OTEL Python Examples](https://github.com/open-telemetry/opentelemetry-python/tree/main/docs/examples)
- [FastAPI + OTEL](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation/opentelemetry-instrumentation-fastapi)
- [Django + OTEL](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation/opentelemetry-instrumentation-django)

### Semantic Conventions Reference
- [General Attributes](https://opentelemetry.io/docs/specs/semconv/general/attributes/)
- [HTTP Conventions](https://opentelemetry.io/docs/specs/semconv/http/)
- [Database Conventions](https://opentelemetry.io/docs/specs/semconv/database/)
- [AI/ML Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) (Emerging)

---

## Success Criteria

### Technical Success
- ✅ All three OTEL pillars (traces, metrics, logs) implemented
- ✅ Integration with Grafana stack working
- ✅ No performance regression in CLI responsiveness
- ✅ Structured data queryable in Grafana
- ✅ Full request flow visibility from CLI to AI to database

### Operational Success
- ✅ Can identify performance bottlenecks in AI enrichment
- ✅ Can correlate errors across distributed components
- ✅ Can measure business metrics (user engagement, feature adoption)
- ✅ Can operate application confidently in production
- ✅ Can set up meaningful alerts and dashboards

### Developer Experience
- ✅ Easy to add new instrumentation
- ✅ Clear debugging with verbose flags
- ✅ No impact on existing user experience
- ✅ Comprehensive documentation and examples
- ✅ Integration with existing development workflow

---

**Next Steps**:
1. Create feature branch: `feature/otel-observability`
2. Begin Phase 1 implementation
3. Set up local Grafana stack for development/testing
4. Iterate through phases with testing at each step

**Estimated Total Implementation Time**: 10-15 days across all phases
