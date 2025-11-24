# Theodore CLI — Fix Priority Roadmap, DB Schema Suggestions, & Performance Optimization Plan

Below is a focused, actionable package you can drop into a Notion page or README. I’ve ordered items by **priority** (what to fix first), explained **why**, and given **concrete code / design suggestions** you can copy into your repo. I did **not** rewrite your code — only pointed to fixes and improvements.

---

# 1. Fix Priority Roadmap (ordered)

> Priority levels: **P0 (Critical)**, **P1 (High)**, **P2 (Medium)**, **P3 (Low / Nice-to-have)**
> Fix order follows critical → high → medium → low. Each item shows **what to change**, **why**, and **how** (concise snippet or instruction).

## P0 — Critical (breaks / crashes / data loss)

1. **`total_size` UnboundLocalError (download_manager)**

   * **What:** `total_size` may be referenced when undefined (if `expected_total == 0` or file already complete).
   * **Why:** raises `UnboundLocalError` and crashes the download flow.
   * **How to fix:** Define/guard `total_size` before use. Use a safe fallback and treat `0` as unknown. Example logic:

     ```py
     # after determining expected_total:
     total_size = expected_total if expected_total and expected_total > 0 else None

     # when comparing:
     final_size = filepath.stat().st_size
     if total_size is not None and final_size != total_size:
         # mismatch handling
     elif total_size is None:
         # unknown total size; rely on headers or verify via length of last chunk / checksum
     ```
   * **Extra:** Use checksum (sha256) when possible to assert file integrity.

2. **Blocking `requests.get()` inside async function (weather_manager.make_request)**

   * **What:** An `async` function uses synchronous `requests`, and also opens `async with engine.begin()` unnecessarily.
   * **Why:** Blocks the event loop and may deadlock or cause poor concurrency.
   * **How to fix:** Use an async HTTP client (e.g. `httpx.AsyncClient` or `aiohttp`). Remove the unused `async` DB transaction unless actually performing DB ops. Example with `httpx`:

     ```py
     import httpx

     async with httpx.AsyncClient(timeout=30) as client:
         r = await client.get(url, params=params, headers=headers)
         r.raise_for_status()
         data = r.json()
     ```
   * **Also:** avoid `async with engine.begin()` unless you need DB operations inside the request attempt loop.

3. **SQL filter bug: comparing to literal `'status'` (tasks_manager.get_tasks)**

   * **What:** `query = query.where(Tasks.c.status == 'status')` — uses the string `"status"` rather than the variable.
   * **Why:** filter never matches; returned results wrong.
   * **How to fix:** replace `'status'` with the variable:

     ```py
     query = query.where(Tasks.c.status == status)
     ```

4. **Inconsistent / wrong return type shapes (various managers)**

   * **What:** Some functions return `send_message(...)`, others return tuples `(False, '...')`, sometimes `None`.
   * **Why:** Callers expect consistent dict shape → hard-to-handle downstream.
   * **How to fix:** pick a single canonical response format (e.g. `{"ok": bool, "message": str, "data": ...}`) and ensure all functions return it.

## P1 — High (security, correctness, or major flows)

1. **HTTPError handling for status codes (download_manager)**

   * **What:** checking error text for '416 client error' instead of status code.
   * **Why:** brittle string matching; unreliable.
   * **How to fix:** check `e.response.status_code` (if available) or `r.status_code`:

     ```py
     except HTTPError as e:
         code = getattr(e.response, "status_code", None)
         if code == 416:
             # Range not satisfiable → treat as already completed
     ```

2. **`delete_task()` only deletes where `is_deleted == True` (tasks_manager)**

   * **What:** delete logic only removes soft-deleted rows; user expectations unclear.
   * **Why:** calling delete on active tasks does nothing.
   * **How to fix:** clarify behavior and API:

     * Option A: Keep delete strict (only purge trash). Document it.
     * Option B (more intuitive): support an explicit `force=True` to delete active tasks. Example:

       ```py
       if force:
           stmt = delete(Tasks).where(Tasks.c.task_id.in_(task_ids))
       else:
           stmt = delete(Tasks).where(Tasks.c.is_deleted.is_(True), Tasks.c.task_id.in_(task_ids))
       ```

3. **Cache/key-check bug in weather_manager (`if query in data`)**

   * **What:** caches weather response but checks `if query in data` — wrong structure.
   * **Why:** never hits cache, causing redundant API calls and wasted quotas.
   * **How to fix:** store per-location-per-query keys. Example:

     ```py
     # cache key format
     cache_key = f"{location}:{query}"
     data = cache.get_cache(cache_key)
     # when storing:
     cache.set_cache(cache_key, data)
     ```

4. **Attribute access without guards (weather_manager tables)**

   * **What:** `current.get('condition').get('text')` can raise if `condition` missing.
   * **How to fix:** use safe lookups:

     ```py
     condition = (current or {}).get("condition") or {}
     condition_text = condition.get("text", "Unknown")
     ```

## P2 — Medium (bugs that cause incorrect results or inefficiencies)

1. **Resume logic edge-cases (download_manager)**

   * **What:** server may ignore Range header or return full content; logic assumes partial content behavior.
   * **How to fix:** detect when server ignores `Range` (status code 200 vs 206), and handle accordingly:

     ```py
     if r.status_code == 206:
         # supports ranges
     elif r.status_code == 200 and downloaded_bytes > 0:
         # server ignored range → remove local partial or validate and restart
     ```

2. **Repeated code building `task_ids` (tasks_manager)**

   * **What:** identical block repeated in many places.
   * **How to fix:** centralize into small helper:

     ```py
     def _normalize_ids(task_id=None, ids=None):
         ids_list = []
         if task_id:
             ids_list.append(task_id)
         if ids:
             ids_list.extend(ids)
         # validate ints and raise ValueError with friendly message
         return list(map(int, ids_list))
     ```

3. **Date parsing path uses undefined method `self.messenger` (tasks_manager)**

   * **What:** references to `self.messenger` or `self.messenger(False, ...)` where only `send_message` exists.
   * **How to fix:** replace with canonical `send_message(False, ...)`.

4. **`make_request` sets `headers = {"User-Agent": ua}` where `ua` may be broken**

   * **What:** `fake_user_agent` may fail at runtime (network call).
   * **How to fix:** use a safe fallback:

     ```py
     try:
         ua = fake_user_agent.user_agent()
     except Exception:
         ua = "Theodore/1.0 (+https://github.com/yourname/theodore)"
     ```

## P3 — Low / nice-to-have

1. Add more defensive logging (debug statements for headers, status codes, and chunk sizes).
2. Add unit tests around date parsing, resume behavior, and cache hits.
3. Centralize response / error formatting to a utils module.
4. Add metrics (Prometheus counters or simple metrics file) for retries, failures, durations.

---

# 2. Database Schema Suggestions for Task Manager

Below is a robust SQL schema suggestion (SQL + SQLAlchemy/metadata) that supports soft delete, tags, priorities, reminders, audit fields, and indexing for search and date queries.

## SQL DDL (Postgres-flavored but easily adapted to SQLite)

```sql
CREATE TABLE tasks (
    task_id      SERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT,
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','not_completed')),
    priority     SMALLINT DEFAULT 3, -- 1-high, 5-low
    tags         TEXT[],             -- Postgres text[]; otherwise use a separate tags table
    due          TIMESTAMP WITH TIME ZONE,
    date_created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    date_updated TIMESTAMP WITH TIME ZONE,
    is_deleted   BOOLEAN NOT NULL DEFAULT false,
    date_deleted TIMESTAMP WITH TIME ZONE,
    reminder_at  TIMESTAMP WITH TIME ZONE,
    created_by   TEXT,   -- optional user id/email
    metadata     JSONB   -- flexible store for custom settings
);

-- Indexes
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_due ON tasks(due);
CREATE INDEX idx_tasks_date_created ON tasks(date_created);
CREATE INDEX idx_tasks_title_trgm ON tasks USING gin (title gin_trgm_ops); -- if pg_trgm available
```

### If you are using SQLite / SQLAlchemy and want a normalized tags table:

```sql
CREATE TABLE tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE task_tags (
    task_id INTEGER REFERENCES tasks(task_id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(tag_id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, tag_id)
);
```

## SQLAlchemy Declarative Example (concise)

```py
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean,
    SmallInteger, JSON, func
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Task(Base):
    __tablename__ = 'tasks'
    task_id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    status = Column(String(20), nullable=False, default='pending')
    priority = Column(SmallInteger, default=3)
    tags = Column(ARRAY(String), default=[])  # Postgres; otherwise use relationship
    due = Column(DateTime(timezone=True))
    date_created = Column(DateTime(timezone=True), server_default=func.now())
    date_updated = Column(DateTime(timezone=True), onupdate=func.now())
    is_deleted = Column(Boolean, default=False)
    date_deleted = Column(DateTime(timezone=True))
    reminder_at = Column(DateTime(timezone=True))
    metadata = Column(JSON, default={})
```

### Notes & rationale

* **Tags as normalized table:** if you expect tag queries (search by tag), normalized `tags` + `task_tags` is better than storing CSV/text arrays.
* **Indexes:** add indexes on `status`, `due`, `date_created`, and optionally a trigram or full-text index on `title` and `description` to speed searches.
* **Audit fields:** `date_updated`, `created_by`, and `metadata` give flexibility for multi-user or future features.
* **Reminder & Priority:** add fields so your CLI can support scheduling and priority-based reminders.

---

# 3. Performance Optimization Plan

This plan covers immediate low-effort wins and more advanced changes. Each bullet gives the problem, impact, and suggested fixes.

## Quick wins (little code change, high impact)

1. **Use connection pooling & short transactions**

   * Problem: long transactions (`async with engine.begin()`) block connections.
   * Fix: open sessions only when needed, keep transactions short; for read-only ops, use `execute` without explicit begin if supported (or use `autocommit` semantics).

2. **Avoid synchronous I/O in async functions**

   * Problem: `requests.get` in async code stops concurrency.
   * Fix: replace with async HTTP client (httpx/aiohttp). This is critical for concurrency under load.

3. **Cache API results properly**

   * Problem: repeated API calls for same location waste time and quota.
   * Fix: cache per `location:query` with TTL and validate responses. Add in-memory LRU cache (e.g., `cachetools.TTLCache`) for very frequent calls.

4. **Batch DB operations**

   * Problem: repetitive small writes create overhead.
   * Fix: where possible, group updates/inserts into a single statement (e.g., update multiple rows in a single `UPDATE ... WHERE id IN (...)` call).

## Medium-term (some refactor)

1. **Introduce async job queue for heavy/background tasks**

   * Use `RQ`, `Celery`, or lightweight `dramatiq`, or even a small `asyncio` background worker for downloads and long-running operations.
   * Offload downloads, long computations, and notification sending to the queue to keep CLI responsive.

2. **Use streaming & backpressure for download writes**

   * Buffer chunk writes and tune `chunksize` for your environment. Consider `aiofiles` for async writes if you make downloads fully async.

3. **Add metrics & observability**

   * Track: request latency, retries, failures, success rates, DB query times. Use Prometheus or a simple log-based metrics collector to identify hotspots.

4. **Introduce pagination and LIMIT/OFFSET**

   * For `get_tasks` and `search`, add limit/offset or cursor-based pagination to avoid loading huge result sets into memory.

## Longer-term / Architectural

1. **Separate concerns: microservices / processes**

   * Split heavy background tasks (download manager, cache updater) into separate processes or workers. Keep CLI as a thin controller.

2. **Use efficient search engines for text search**

   * If app scales, delegate title/description search to PostgreSQL full-text, Elasticsearch, or SQLite FTS5.

3. **Parallelize safe independent operations**

   * For file moves or downloads of many independent items, use a worker pool (asyncio or threads) with a bounded concurrency to avoid saturating disk or network.

4. **Database tuning**

   * Add proper indexes based on actual query patterns. Use EXPLAIN on heavy queries. Consider partitioning tasks by date if table grows very large.

## Example measurable goals (metrics to track)

* Average `get_tasks` latency under 100ms for common queries.
* Download success rate > 99% over 24 hours.
* Cache hit rate > 80% for repeated weather queries.
* Database query count per CLI command minimized (1-3).

---

# 4. Suggested small refactors & helper utilities

These are local refactors with high ROI:

* **`utils.normalize_ids(task_id, ids)`** → centralize conversion + validation.
* **`utils.safe_response(ok, message=None, data=None)`** → single response format.
* **`utils.safe_get(obj, *keys, default=None)`** → nested dict safe-get helper.
* **`managers.http_client`** → central http client factory (sync or async) to centralize headers, timeouts, retries.
* **`managers.check_file_integrity(filepath, expected_size=None, checksum=None)`** → reusable function for downloads.

---

# 5. Example "Issue Tracker" entries you can paste to GitHub

1. **BUG: UnboundLocalError in download flow when content-length missing**

   * Severity: P0
   * Description: `total_size` is referenced while possibly undefined. Add guards and fallback.

2. **BUG: Blocking HTTP request inside async function (weather)**

   * Severity: P0
   * Description: `make_request` uses `requests` in an async function; replace with async client.

3. **BUG: Status filter compares to literal 'status' (tasks_manager)**

   * Severity: P0
   * Description: change to compare to `status` var.

4. **ENHANCEMENT: Add cache key format `location:query` for weather cache**

   * Severity: P1

5. **ENHANCEMENT: Centralize id normalization & validation helper**

   * Severity: P2

---

# Closing / Next steps

If you want, I can now:

* Produce a small patch PR (diffs) for the **P0** fixes only (no full rewrites).
* Generate unit tests that assert these bugs (e.g., simulate missing `content-length`, async weather call).
* Create GitHub issues with the title/body and suggested labels for you to paste directly.

Which would you like me to do next?
