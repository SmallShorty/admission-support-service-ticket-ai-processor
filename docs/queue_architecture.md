Here is your explanation converted into a clean **LLM knowledge file in Markdown format** (structured, normalized, and ready for embedding or documentation use):

---

# 📘 FastAPI Batch Processing Service (SNILS-based)

## Overview

This document describes the architecture and processing logic of a FastAPI service that handles incoming requests using:

- **SNILS** as the primary identifier
- **Batch processing** for efficiency
- **Parallel pipelines** for classification and applicant lookup
- **Redis caching** for performance optimization

---

## 1. Input Format

Each request contains:

```json
{
  "snils": "123-456-789 01",
  "ticket_text": "Как оплатить обучение?"
}
```

- `snils`: Unique applicant identifier
- `ticket_text`: User query to classify

---

## 2. High-Level Flow

```
Incoming Request (SNILS + Text)
            │
            ▼
    ┌──────────────────────────────┐
    │  Push into 2 Queues          │
    │  • Classification Queue      │
    │  • SNILS Lookup Queue        │
    └──────────────────────────────┘
            │
            ▼
    ┌──────────────────────────────┐
    │ Background Workers           │
    │ • Text → Category            │
    │ • SNILS → Applicant Data     │
    └──────────────────────────────┘
            │
            ▼
    ┌──────────────────────────────┐
    │ Merge Results                │
    │ → Calculate Priority         │
    │ → Return Response            │
    └──────────────────────────────┘
```

---

## 3. Independent Queues

### 3.1 Classification Queue

**Purpose:** Batch text classification

- **Input:** text
- **Output:** `{ category, confidence }`

**Batching parameters:**

| Parameter     | Value |
| ------------- | ----- |
| Batch size    | 32    |
| Max wait time | 50 ms |

**Rules:**

- Process when batch reaches 32 items
- Or after 50 ms timeout

**Notes:**

- CPU-bound (ML model)
- Batch improves throughput significantly

---

### 3.2 SNILS Lookup Queue

**Purpose:** Batch retrieval of applicant data

- **Input:** SNILS
- **Output:** Applicant data (Redis or Nest.js)

**Batching parameters:**

| Parameter     | Value |
| ------------- | ----- |
| Batch size    | 20–50 |
| Max wait time | 30 ms |

**Rules:**

- Only SNILS **not found in cache** are batched
- Batch request sent to Nest.js API

---

## 4. Redis Caching Strategy

### Key Structure

```
applicant:snils:{snils}
```

- **Value:** JSON applicant data
- **TTL:** 24 hours

---

### Lookup Algorithm

```
1. Check Redis
   → HIT → return immediately (~1–2 ms)

2. MISS → enqueue SNILS

3. Wait for batch worker:
   → Fetch from Nest.js
   → Save to Redis
   → Return result
```

---

## 5. SNILS Batch Worker

Runs every **30 ms** or when batch is full.

### Steps:

1. Collect SNILS from queue
2. Re-check Redis (avoid duplicate requests)
3. Send batch request:

```http
POST /api/applicants/batch
{
  "snils": ["...", "..."]
}
```

4. Receive response:

```json
{
  "applicants": [{ "snils": "...", "has_bvi": false }]
}
```

5. Store in Redis:

```python
redis.setex(key, 86400, json)
```

6. Resolve waiting requests (futures)

---

## 6. Full Request Lifecycle

```
1. Request received

2. Create futures:
   - classification_future
   - applicant_future

3. Push to queues

4. Await both:
   await gather(...)

5. Workers process in parallel:

   Classification Worker:
   → Batch texts → ML model → set results

   SNILS Worker:
   → Batch SNILS → Nest.js → cache → set results

6. Combine results

7. Compute priority

8. Return response
```

---

## 7. Priority Calculation

```python
priority = calculate_priority(
    category=classification.category,
    confidence=classification.confidence,
    applicant_data=applicant_data
)
```

---

## 8. Missing Applicant Data

If SNILS not found in Nest.js:

```json
{
  "has_bvi": false,
  "has_special_quota": false,
  "has_separate_quota": false,
  "has_target_quota": false,
  "has_priority_right": false,
  "original_document_received": false,
  "exam_scores": []
}
```

### Important:

- ❌ Do NOT cache default data
- ✅ Retry on next request (data may appear later)

---

## 9. Fault Tolerance (Fallback Strategy)

| Scenario            | Behavior                      |
| ------------------- | ----------------------------- |
| Redis unavailable   | Skip cache                    |
| Nest.js unavailable | Use default data              |
| Empty response      | Use default data (no caching) |
| Timeout (>500ms)    | Use default data              |

---

## 10. Architecture Decisions

### Dual Queue Design

| Queue          | Type      | Reason                           |
| -------------- | --------- | -------------------------------- |
| Classification | CPU-bound | Needs batching for ML efficiency |
| SNILS          | I/O-bound | Reduces HTTP calls               |

---

### Redis Role

- Reduces Nest.js load (~95%)
- Improves latency dramatically
- Acts as short-term data layer

---

### Batch Everywhere

- Text → ML batching
- SNILS → API batching

---

## 11. Performance Example

```
0 ms   → 100 requests arrive
30 ms  → SNILS batch processed (50)
50 ms  → Classification batch processed (32)
100 ms → All requests completed

Latency: ~100 ms
Throughput: ~1000 RPS
```

---

## 12. Configuration Parameters

| Parameter            | Default | Notes                       |
| -------------------- | ------- | --------------------------- |
| CLASSIFY_BATCH_SIZE  | 32      | Increase for high load      |
| CLASSIFY_MAX_WAIT_MS | 50      | Trade latency vs throughput |
| SNILS_BATCH_SIZE     | 50      | Depends on Nest.js          |
| SNILS_MAX_WAIT_MS    | 30      | Lower for faster response   |
| REDIS_TTL_SECONDS    | 86400   | 24 hours                    |

---

## 13. Monitoring Metrics

| Metric                  | Description                   |
| ----------------------- | ----------------------------- |
| classify_batch_size_avg | Avg classification batch size |
| classify_queue_wait_ms  | Queue wait time               |
| snils_batch_size_avg    | Avg SNILS batch size          |
| snils_cache_hit_rate    | Cache efficiency              |
| nest_batch_latency_ms   | Nest.js response time         |
| applicant_fallback_rate | % fallback usage              |

---

## 14. Key Benefits

### ✅ High Throughput

- Batch processing for all heavy operations

### ✅ Low Latency

- Parallel execution of pipelines

### ✅ Scalability

- Independent tuning of queues

### ✅ Fault Tolerance

- Graceful degradation with defaults

### ✅ Reduced External Load

- Redis caching minimizes API calls

---

## 15. Summary

Core principles:

1. **SNILS as primary key**
2. **Parallel pipelines**
3. **Batch-first architecture**
4. **Aggressive caching**
5. **Graceful fallback handling**
