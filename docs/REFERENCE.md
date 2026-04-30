# Module 1 Reference: APGI Concepts and API

## Quick Reference: APGI Concepts

### Consciousness Equation

```text
Consciousness = Allostasis + Precision Gating + Ignition

1. Allostasis (Predictive Regulation)
   └─ Brain builds models of expected future states
   └─ Adapts goals and predictions continuously

2. Precision Gating (Information Filtering)
   └─ Gates (0-1) control which signals reach higher processing
   └─ Based on predictions and salience

3. Ignition (Network Synchronization)
   └─ When synchronized regions activate together
   └─ Maps to conscious experience
```

## Key APGI Terms

| Term | Definition | Example |
| **Allostasis** | Predictive regulation; anticipating future states | Brain predicts you'll hear a car before you consciously hear it |
| **Precision Gate** | Filter controlling information flow (0-1 scale) | 0.1 = sound mostly blocked; 0.9 = sound fully passes through |
| **Gating Value** | Numeric value (0-1) of precision gate; determines signal transmission | Task-relevant signals get 0.8; distracting signals get 0.2 |
| **Ignition Event** | Synchronized activation of brain networks; conscious moment | Seeing a flash of light is an ignition event |
| **Consciousness Level** | Computed metric (0-1) reflecting consciousness in APGI | 0.2 = low consciousness; 0.8 = high consciousness |
| **Synchrony** | How aligned brain oscillations are; measure of integration | High synchrony = coordinated network activity = consciousness |
| **Salience** | How important/novel/emotional a stimulus is | Your name is highly salient; background noise is low salience |

## API Endpoints

These are the core endpoints you'll use in APGI simulations:

### Authentication

```python
POST /v1/auth/login
  - Get JWT access token

POST /v1/auth/refresh
  - Refresh expired token

POST /v1/auth/logout
  - Logout and invalidate tokens
```

### API Keys

```python
POST /v1/api-keys
  - Create new API key
  - Returns: key_id, key_prefix, full_key (one-time display)

GET /v1/api-keys
  - List user's API keys
  - Returns: array of key objects (key_id, key_prefix, created_at, last_used)

GET /v1/api-keys/{key_id}
  - Get API key details
  - Returns: key metadata

PUT /v1/api-keys/{key_id}
  - Update API key metadata
  - Payload: name, description

POST /v1/api-keys/{key_id}/rotate
  - Rotate API key (generate new secret)
  - Returns: new full_key (one-time display)

DELETE /v1/api-keys/{key_id}
  - Delete API key
```

### Sessions (Core APGI Simulation)

```python
POST /v1/sessions
  - Create new APGI session
  - Payload: config (JSON), description
  - Returns: session_id, state="created"

GET /v1/sessions/{session_id}
  - Get session details
  - Returns: configuration, state, full_state, timestamps

PUT /v1/sessions/{session_id}
  - Update session (pause, resume)
  - Payload: state="running"|"paused"|"stopped"

POST /v1/sessions/{session_id}/start
  - Start simulation
  - Changes state: "created" → "running"

GET /v1/sessions
  - List all your sessions
  - Returns: array of session objects

POST /v1/sessions/{session_id}/pause
  - Pause session

POST /v1/sessions/{session_id}/stop
  - Stop session

POST /v1/sessions/{session_id}/reset
  - Reset session to initial state

DELETE /v1/sessions/{session_id}
  - Delete session
```

### Session Templates

```python
GET /v1/templates
  - List session templates (public and user's own)
  - Returns: array of template objects

POST /v1/templates
  - Create new session template
  - Payload: name, description, config, is_public
  - Returns: template_id

GET /v1/templates/{template_id}
  - Get template details
  - Returns: template configuration

PUT /v1/templates/{template_id}
  - Update template
  - Payload: name, description, config, is_public

DELETE /v1/templates/{template_id}
  - Delete template
```

### Tasks (Experiments within Session)

```python
POST /v1/sessions/{session_id}/tasks
  - Submit experiment/stimulus to session
  - Payload: task_type, parameters
  - Returns: task_id, status="pending"

GET /v1/sessions/{session_id}/tasks/{task_id}
  - Get task status and results
  - Returns: task details, status, results

GET /v1/sessions/{session_id}/tasks
  - List all tasks in session
  - Returns: array of task objects
```

### Export & Results

```http
GET /v1/sessions/{session_id}/export/json
  - Export session as JSON
  - Returns: complete session data

GET /v1/sessions/{session_id}/export/csv
  - Export session as CSV
  - Returns: tabular session data

GET /v1/sessions/{session_id}/export/summary
  - Get summary statistics
  - Returns: aggregated metrics

GET /v1/sessions/{session_id}/export/timeseries
  - Get time series data
  - Returns: time-indexed state data

GET /v1/sessions/{session_id}/export/events
  - Get event analysis data
  - Returns: ignition events and analysis
```

### Webhook Deliveries

```python
GET /v1/webhooks/deliveries
  - List webhook deliveries
  - Query params: session_id, status, limit, offset
  - Returns: array of delivery objects

GET /v1/webhooks/deliveries/{delivery_id}
  - Get delivery details
  - Returns: delivery status, attempts, response

POST /v1/webhooks/deliveries/{delivery_id}/retry
  - Retry failed delivery
  - Returns: new delivery attempt

DELETE /v1/webhooks/deliveries/{delivery_id}
  - Delete delivery

GET /v1/webhooks/dead-letter
  - List dead-letter webhook deliveries
  - Returns: failed deliveries that need attention

GET /v1/webhooks/dead-letter/{delivery_id}
  - Get dead-letter delivery details

POST /v1/webhooks/dead-letter/{delivery_id}/retry
  - Retry dead-letter delivery

DELETE /v1/webhooks/dead-letter/{delivery_id}
  - Delete dead-letter delivery
```

### Business Metrics

```python
GET /v1/metrics/dashboard
  - Complete dashboard data
  - Returns: all metrics aggregated

GET /v1/metrics/overview
  - High-level overview metrics
  - Returns: summary statistics

GET /v1/metrics/sessions
  - Session-related metrics
  - Returns: session counts, completion rates

GET /v1/metrics/tasks
  - Task-related metrics
  - Returns: task completion rates, performance

GET /v1/metrics/users
  - User-related metrics
  - Returns: user counts, activity

GET /v1/metrics/templates
  - Template-related metrics
  - Returns: template usage statistics
```

## Configuration Object Structure

When creating a session, you provide a `config` object:

```json
{
  "simulation_parameters": {
    "time_steps": 100,
    "initial_precision_gate": 0.3,
    "noise_level": 0.2,
    "tau_allostasis": 50,
    "tau_ignition": 10
  },
  "network_config": {
    "num_regions": 8,
    "connectivity": "small_world",
    "oscillation_frequency": 10
  }
}
```

### Key Parameters

| Parameter | Range | Meaning |
| `time_steps` | 1-1000 | How many simulation steps to run |
| `initial_precision_gate` | 0-1 | Starting gate value (0=closed, 1=open) |
| `noise_level` | 0-1 | Random perturbations in system |
| `tau_allostasis` | 1-100 | Time scale of predictive adaptation |
| `tau_ignition` | 1-100 | Time scale of synchronization |
| `num_regions` | 1-100 | Number of simulated brain regions |
| `connectivity` | "random", "small_world", "scale_free" | Network topology |
| `oscillation_frequency` | 1-50 | Brain oscillation frequency (Hz) |

## Session States

```text
CREATED   → RUNNING   → PAUSED  → RESUMED  → STOPPED
  ↓          ↓                                   ↓
(Setup)   (Active)                           (Results)
          Optional: RUNNING → ERROR (if something fails)
```

### State Explanations

- **CREATED**: Session exists but hasn't started. Configuration loaded, but simulation not running.
- **RUNNING**: Simulation is actively progressing through time steps.
- **PAUSED**: Simulation is paused; can resume from this point.
- **STOPPED**: Simulation complete or manually stopped. Results are final.
- **ERROR**: Something failed during simulation. Check logs for details.

## Task Types

These are experiment types you can submit within a session:

```python
"apply_stimulus"          - Apply sensory input to system
"measure_consciousness"   - Measure current consciousness level
"observe_state"          - Sample current system state
"perturb_gate"           - Modify precision gate value
"record_history"         - Save state history snapshot
```

## API Response Format

All successful responses follow this pattern:

```json
{
  "status": "success",
  "data": {
    // Response-specific content
  },
  "timestamp": "2024-03-26T10:30:00Z"
}
```

### Error Response

```json
{
  "status": "error",
  "error": {
    "code": "INVALID_SESSION",
    "message": "Session not found or unauthorized",
    "details": {}
  },
  "timestamp": "2024-03-26T10:30:00Z"
}
```

## Authentication: JWT Token Format

After login, you get a JWT token:

```python
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiMTIzIn0.signature
```

This is divided into three parts (separated by `.`):

1. **Header**: Algorithm and type information
2. **Payload**: User data (user_id, roles, expiration)
3. **Signature**: Cryptographic signature (can't be forged without the secret)

Use it by including in all requests:

```http
Authorization: Bearer eyJhbGciOi...
```

## Database Models (What Gets Stored)

### User

```python
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "student",
  "email": "student@example.com",
  "roles": ["user", "researcher"],
  "is_active": true,
  "created_at": "2024-03-26T10:00:00Z"
}
```

### Session

```python
{
  "session_id": "550e8400-e29b-41d4-a716-446655440001",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "config": { /* configuration object */ },
  "full_state": { /* current APGI state */ },
  "state": "running",
  "description": "Visual stimulus experiment",
  "created_at": "2024-03-26T10:00:00Z",
  "updated_at": "2024-03-26T10:05:00Z"
}
```

### Task

```python
{
  "task_id": "550e8400-e29b-41d4-a716-446655440002",
  "session_id": "550e8400-e29b-41d4-a716-446655440001",
  "task_type": "apply_stimulus",
  "parameters": {
    "stimulus_type": "visual",
    "intensity": 0.7,
    "expected": true
  },
  "status": "completed",
  "result": { /* computation results */ },
  "created_at": "2024-03-26T10:02:00Z"
}
```

### API Key

```python
{
  "key_id": "550e8400-e29b-41d4-a716-446655440003",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "key_prefix": "apgi_abc123",
  "key_hash": "hashed_secret_key",
  "name": "Production API Key",
  "description": "Key for production services",
  "is_active": true,
  "last_used_at": "2024-03-26T10:30:00Z",
  "created_at": "2024-03-26T10:00:00Z"
}
```

### Session Template

```python
{
  "template_id": "550e8400-e29b-41d4-a716-446655440004",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Default Visual Experiment",
  "description": "Standard configuration for visual stimulus experiments",
  "config": { /* configuration object */ },
  "is_public": true,
  "created_at": "2024-03-26T10:00:00Z",
  "updated_at": "2024-03-26T10:05:00Z"
}
```

### Webhook Delivery

```python
{
  "delivery_id": "550e8400-e29b-41d4-a716-446655440005",
  "session_id": "550e8400-e29b-41d4-a716-446655440001",
  "webhook_url": "https://example.com/webhook",
  "payload": { /* webhook payload */ },
  "status": "delivered",
  "http_status_code": 200,
  "response_body": "OK",
  "attempts": 1,
  "created_at": "2024-03-26T10:02:00Z",
  "delivered_at": "2024-03-26T10:02:01Z"
}
```

## Common HTTP Status Codes

| Code | Meaning | Example |
| **200** | OK - Request succeeded | GET session successful |
| **201** | Created - Resource created | POST session successful |
| **400** | Bad Request - Invalid input | Malformed JSON in request |
| **401** | Unauthorized - Need authentication | Missing or invalid token |
| **403** | Forbidden - Authenticated but not allowed | User A tries to access User B's session |
| **404** | Not Found - Resource doesn't exist | Session ID doesn't exist |
| **500** | Server Error - Something broke | Unexpected error in API |

## Metrics You'll See

When you monitor APGI sessions:

| Metric | Meaning | Typical Range |
| -------- | --------- | -------------- |
| **Consciousness Level** | Overall consciousness in APGI system | 0-1 |
| **Precision Gate Value** | Current filtering level per region | 0-1 |
| **Synchrony** | Network synchronization level | 0-1 |
| **Integration** | Information integration across regions | 0-1 |
| **Reaction Time** | Time from stimulus to ignition event | milliseconds |
| **Number of Ignitions** | Count of conscious events in session | integer |

## Troubleshooting Quick Reference

| Issue | Cause | Solution |
| 401 Unauthorized | Invalid/missing token | Re-login, get new token |
| 403 Forbidden | Don't own this session | Verify session belongs to you |
| 404 Not Found | Wrong session/task ID | Check IDs, list sessions to confirm |
| 500 Server Error | API crashed | Check server logs, try again |
| Task never completes | Worker crashed | Restart Celery worker |
| Slow response | Database query slow | Session might have large state |

## Architecture Mapping

How APGI theory maps to the system:

```text
APGI Theory              API Implementation
─────────────────────────────────────────
Consciousness model  ←→  Session object
Configuration        ←→  session.config (JSON)
System state         ←→  session.full_state (JSON)
Precision gates      ←→  task parameters
Ignition events      ←→  Task status/results
Measurement          ←→  Tasks + export
```
