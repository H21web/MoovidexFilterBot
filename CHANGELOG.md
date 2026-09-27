# MoovidexFilterBot — Audit, Bugfix & Optimization Changelog

- **Repo:** https://github.com/H21web/MoovidexFilterBot (deployed branch `clean`)
- **Work date:** 2026-09-26
- **Scope:** full codebase analysis (~15,310 Python lines, ~50 files), bug fixes,
  safe optimizations, dependency/runtime updates, compile + install verification.
- **Rules followed:** behavior preserved unless the behavior was a bug; no new
  features invented; bot never run (needs live Telegram credentials);
  nothing pushed to GitHub.

Severity legend: **Critical** (crash / data loss / security hole),
**High** (broken feature, hangs the bot), **Medium** (wrong results, leaks,
fragile code), **Low** (hygiene, warnings, dead code).

---

## 1. Dependencies & runtime

### requirements.txt — dependency audit (Medium)
- **Bug:** the file listed packages that are never imported anywhere in the
  repo (verified by repo-wide import search in both pristine and fixed trees):
  `bs4` (stub shadow of `beautifulsoup4`), `googletrans`, `speedtest` (wrong
  package), `PyLeaves`, `NumPy`, `pyshorteners`, `python-dotenv`, `umongo`,
  `marshmallow`, `apscheduler`, `colorama`, `wheel`, `wget`, `ujson`,
  `python-decouple`, and `aiofiles` (added to the unused list during this pass —
  zero imports in pristine or fixed code).
- **Fix:** removed all unused entries; kept `tgcrypto` (pyrofork's crypto
  backend, used implicitly) and `dnspython` (required by `pymongo[srv]` for
  SRV connection strings).
- **Old → new pins:**

| Package | Old | New |
|---|---|---|
| pyrofork | 2.3.24 | 2.3.69 |
| tgcrypto | 1.2.5 | 1.2.5 |
| requests | 2.32.3 | 2.34.2 |
| beautifulsoup4 | 4.12.3 | 4.15.0 |
| shortzy | 0.0.8 | 0.0.8 |
| pytz | 2024.1 | 2026.4 |
| aiohttp | 3.9.5 | 3.14.3 |
| jinja2 | 3.1.4 | 3.1.6 |
| hachoir | 3.1.0 | 3.4.0 |
| pymongo[srv] | 4.7.2 | 4.18.2 |
| motor | 3.3.2 | 3.7.1 |
| humanize | 4.9.0 | 4.16.0 |
| Pillow | 10.3.0 | 12.3.0 |
| psutil | 5.9.8 | 7.2.2 |
| dnspython | 2.6.1 | 2.8.0 |

  (Old pins are the values found in the pristine `requirements.txt`; new pins
  were confirmed published/current on PyPI on 2026-09-26.)

### runtime.txt / Dockerfile — runtime upgrade (Medium)
- **Bug:** pinned Python 3.10.8 / `python:3.10-slim-bullseye` (old, near EOL).
- **Fix:** `runtime.txt` → `python-3.12.9`; `Dockerfile` →
  `python:3.12-slim-bookworm` (image tag verified to exist).

---

## 2. Configuration — info.py (High)

The pristine `info.py` was restored and re-edited surgically (CRLF preserved).

- **Loose/unsafe config parsing:** env values were read with weak fallbacks
  that silently produced wrong types (e.g. non-boolean strings treated as
  truthy, malformed ID lists).
  **Fix:** strict parsing — required values raise a clear error at startup
  instead of failing mysteriously later; booleans/integers/IDs/ID-lists are
  validated and normalized.
- **Admins locked out of auth lists:** `ADMINS` were not automatically part of
  authorized users.
  **Fix:** admins are always merged into the authorized-user set.
- **Bundled API keys:** the file shipped default TMDB and Deepgram keys.
  **Fix:** defaults removed; keys are only read from the environment.
  ⚠️ The old keys still exist in the repo's **git history** — rotate them on
  TMDB/Deepgram; removing them from the working tree does not revoke them.
- **Payment UPI hardcoded:** **Fix:** now environment-configurable, keeping the
  deployed fallback value so current payments keep working.
- Preserved deployed payment wording/plans; restored missing reaction entries.

---

## 3. Core

### bot.py (High)
- **Path handling:** `logging.config.fileConfig('logging.conf')` depended on the
  process working directory.
  **Fix:** resolved from the file's own directory
  (`Path(__file__).resolve().parent / 'logging.conf'`).
- **Event loop:** legacy `asyncio.get_event_loop()` usage.
  **Fix:** `asyncio.run(start())`.
- **Duplicate `get_me()`:** the bot called `get_me()` twice at startup.
  **Fix:** single call, reused.
- **Startup notice crash:** a failure sending the restart notice to
  `LOG_CHANNEL` was handled with a bare `except` + print.
  **Fix:** safer handling that never blocks startup.
- **`AUTH_CHANNEL=None` unsupported:** startup assumed a log/auth channel.
  **Fix:** `None` is handled gracefully.
- **HTTP session leak:** the shared aiohttp session was never closed.
  **Fix:** `close_http_session()` from utils is wired into shutdown.
- **Missing pyromod:** several plugins used `bot.ask()` / `client.listen()`,
  but pyromod was never installed → `AttributeError` at runtime.
  **Fix:** new `TechVJ/util/conversation.py` implements native `ask()`/`listen()`
  conversation routing; `bot.py` installs it and registers a router at handler
  group `-1000` so a pending conversation captures the reply before other
  handlers (raising `StopPropagation`).
- **Index setup:** `ensure_indexes()` is now awaited at startup; a failure is
  logged and does not block the bot.

### TechVJ/util/conversation.py (new file)
- Native replacement for pyromod's `ask`/`listen` used by the rename and
  other flows. No behavior invented — it restores the calls the code already
  made.

### TechVJ/bot/clients.py (High)
- **Crash on failed extra clients:** `dict(clients)` raised `TypeError` when any
  extra bot token failed to start (`start_client` returns `None` on failure).
  **Fix (final):** `dict(result for result in clients if result is not None)` —
  `None` results are filtered *before* tuple unpacking (an earlier draft
  filtered after unpacking, which still crashed).
- **Dead flag:** the module set a local `MULTI_CLIENT = True` that nothing read
  (plugins read `info.MULTI_CLIENT`).
  **Fix:** writes `info.MULTI_CLIENT = True`; `plugins/route.py` reads
  `info.MULTI_CLIENT`.

---

## 4. Database layer

### Sync PyMongo inside async code (Critical)
Multiple database modules called **synchronous** PyMongo inside `async def`
coroutines, blocking the entire event loop on every DB call:
`database/connections_mdb.py`, `database/filters_mdb.py`,
`database/gfilters_mdb.py`, `database/users_chats_db.py`,
`database/config_db.py`, `database/requests_db.py`, `database/join_reqs.py`,
`database/stats_db.py`.
**Fix:** converted to Motor (`AsyncIOMotorClient`); all DB calls awaited.

### database/ia_filterdb.py (High)
- **Removed API:** `.count()` no longer exists in modern PyMongo/Motor.
  **Fix:** `count_documents({})`.
- **Missing awaits / unbound locals / missing-document guards** fixed across
  query helpers.
- **Upserts added** to user/chat/config writes to reduce check-then-write races.
- **Index setup:** safe non-unique index creation in `ensure_indexes()`.
- **Two-database pagination corrected** (offset math across primary/secondary).
- **Bad-file search:** regex is now escaped; deletion queries project only the
  fields they need; new count-only helper `count_bad_files()`.
- **Single-DB compatibility:** when multi-DB mode is off, `sec_db`/`sec_col`
  are set to `None` so the unconditional `pm_filter` import cannot crash.
- **Motor truthiness crash (Critical):** `if MULTIPLE_DATABASE and sec_col:`
  (5 occurrences) — Motor collections raise `NotImplementedError` on
  truth-value testing, so multi-DB mode crashed.
  **Fix:** `... and sec_col is not None`.
- Deployed typo collection name `uersz` intentionally preserved.

### Other database fixes
- `database/join_reqs.py`: `_id` queries corrected.
- `database/requests_db.py`: request-status result reporting fixed.
- Referral helpers: missing awaits and unbound variables fixed.
- `database/topdb.py`: removed the dead interactive console loop (it blocked
  forever waiting on stdin); removed the blank line left at EOF.

---

## 5. Plugins

### plugins/pm_filter.py (Critical/High)
- **Duplicate `^fl#` handlers:** two handlers with the same pattern both fired
  on every quality/homepage callback; the second referenced an undefined `lang`
  → `NameError`.
  **Fix:** merged into one `filter_fl_cb_handler` with malformed-data and
  expired-search checks, ownership check, no-results answer, and a final
  callback answer (no hanging spinners). `QUALITY_MAP` (line 56) verified to
  exist.
- **Undefined name:** `BUTTON0` → `BUTTONS0`.
- **Dead code in `backcb`:** referenced undefined `languages`, `lang`, `key`.
  **Fix:** removed.
- **Spell-check callbacks:** no validation of callback structure, user ID,
  session, or movie index.
  **Fix:** structural/user validation, missing reply/session handling, index
  bounds check.
- **Alert callbacks (`gfilteralert`, `alertmessage`):** `alerts[int(i)]` raised
  `ValueError`/`IndexError` on crafted callbacks; `ast.literal_eval` unguarded.
  **Fix:** index parsed and bounds-checked; eval wrapped; user-facing error
  answers.
- **Secondary-DB guards:** `sec_col is not None` checks added to deletion/stats
  paths; `unpack_new_file_id` single-return-value misuse fixed (see
  files_delete).
- Exact `^languages#` vs broad `^languages` duplicate handlers noted for
  follow-up consolidation (both still present; the broad one no longer crashes).

### plugins/commands.py (High)
- **`unpack_new_file_id` misuse:** `file_id, file_ref = unpack_new_file_id(...)`
  but the helper returns one value → `ValueError`.
  **Fix:** single assignment.
- **Missing awaits** on Motor delete/drop calls; secondary-DB guards added.
- **Event-loop blocking (High):** 8 sites did `await asyncio.sleep(300–1200)`
  inside handlers (10/20-min autodeletes), freezing the handler (and, for the
  sequential paths, delaying everything behind it).
  **Fix:** new `schedule_autodelete()` helper + a task-reference set; all 8
  sleeps converted to fire-and-forget background tasks preserving each path's
  exact behavior (delete media, edit the notice, or both). Verified: 0 long
  sleeps remain, 8 `schedule_autodelete` call sites.

### plugins/files_delete.py (High)
- Same `unpack_new_file_id` tuple-unpack fix; missing awaits added;
  `sec_col is not None` guards.

### plugins/dashboard.py (High/Critical)
- **Session forgery (Critical):** login set a client-side `admin_auth=true`
  cookie — anyone could forge it.
  **Fix:** random server-side session tokens with expiry; logout destroys the
  token; cookies are `HttpOnly` + `SameSite=Lax`.
- **XSS:** dashboard Jinja environment had autoescape off.
  **Fix:** HTML autoescape enabled.
- **Info leak:** the dashboard home returned tracebacks to visitors.
  **Fix:** logs server-side, returns generic 500.
- **Open redirect-ish:** request-action redirect messages now URL-encoded.
- **Broadcast:** bounded FloodWait retries.
- File deletion awaits Motor calls and guards `sec_col`.

### plugins/index.py (High)
- **FloodWait resume never resumed:** the restructured loop slept on FloodWait
  but then hit an unconditional `break`.
  **Fix:** `continue` after the capped sleep (max 300 s), resuming at the
  preserved message offset; aborts cleanly with a user message after 10
  consecutive FloodWaits instead of hanging forever.
- **SyntaxWarning:** invalid escape in the t.me link regex → raw string
  (identical semantics).

### plugins/route.py (High)
- **Duplicate handler name:** two `stream_handler` functions; the second
  silently overwrote the first.
  **Fix:** renamed to `download_handler`.
- **Header injection (High):** `file_name` (untrusted) was interpolated into
  `Content-Disposition`.
  **Fix:** strips `"`, CR, LF (verified by micro-test).
- Reads the real `info.MULTI_CLIENT` flag.

### TechVJ/util/render_template.py + templates (High/Critical)
- **Full self-download for size:** the page did `s.get(src)` downloading the
  whole file to read `Content-Length`.
  **Fix:** `HEAD` request with `file_data.file_size` fallback.
- **TMDB key leak (High):** the API key was injected into the public page
  render. **Fix:** no longer passed; `req.html` no longer references it
  (client-side TMDB code falls back to the default poster).
- **XSS (High):** Jinja autoescape enabled on both templates; JS string
  contexts (`FileName`, `botUrl`) now use `|tojson`.
- **Broken watch page (Critical, found during verification):** `req.html`
  contained `FileName.includes("{{")` in three places — Jinja tried to parse
  the literal `{{` and raised `TemplateSyntaxError` on **every** video/audio
  page render (pristine repo included: the deployed watch page was broken).
  **Fix:** `"{" + "{"` keeps the runtime "was the variable substituted?" check
  without breaking the parser. Verified: template now compiles and renders.
- `dl.html`: dead `%s` placeholders converted to real Jinja variables; the
  download link is now quoted.

### plugins/Extra/rename/cb_data.py (High)
- **Callback hijack:** `filters.regex('cancel')` matched any callback
  *containing* "cancel" (e.g. `delallcancel`).
  **Fix:** anchored `r'^cancel$'`.
- **Path traversal (High):** the new file name was used raw in
  `f"downloads/{new_filename}"`.
  **Fix:** `basename`, rejects empty/`.`/`..`, confined to `downloads/`.
- **Discarded resize:** `img.resize((320, 320))` result thrown away.
  **Fix:** `img = img.resize((320, 320))`.
- `await ms.edit(e)` with an exception object → `str(e)`.

### plugins/Extra/rename/filedetect.py (High)
- **NameError on every call:** `out_filename` used before assignment; the
  extension branch never ran.
  **Fix:** output name is built first, then the picker is shown.

### plugins/Extra/paste.py (Medium)
- No-input path fell through and crashed (`message_s` unbound).
  **Fix:** replies and returns.
- Downloaded reply documents were left on disk on some paths.
  **Fix:** `try/finally` removes the temp file.
- Paste-service error responses unhandled → `KeyError`.
  **Fix:** checks `"error"` in the response.

### plugins/Extra/ott.py (Medium)
- `int(...)` / list index on callback data unguarded → crash on crafted taps.
  **Fix:** `try/except (ValueError, IndexError)` with user alert.
- Next/previous/back/close buttons lacked ownership checks — any user could
  drive another user's menu.
  **Fix:** `user_id` ownership enforced; cache entry cleared on close;
  callbacks always answered.

### plugins/Extra/approve.py (Medium)
- `data.split(...)` when `data` is `None` → `AttributeError`.
  **Fix:** `if data and ...`.
- `await get_seconds(time)` — `get_seconds` is sync.
  **Fix:** dropped the `await`.

### plugins/Extra/binged.py & upcoming.py (Medium)
- **Hardcoded personal admin IDs** `[1011394081, 7191327005]` and channel ID.
  **Fix:** `BINGED_ADMIN_IDS` env list, defaulting to configured `ADMINS`;
  `UPDATE_CHANNEL_ID` env-configurable with the deployed channel as fallback.
  No personal IDs remain in the repo.
- **Dead "Edit & Post" button:** its callback had no handler (would have been a
  new feature to implement).
  **Fix:** button removed, noted in code.

### utils.py (High/Medium)
- Async HTTP helpers with bounded retries; shortlink code no longer disables
  TLS verification; premium/direct-file edge cases fixed; caption/signature
  builders fixed; string-list parsing fixed; timezone handling fixed
  (`Asia/Kolkata`); replaced `print` debugging with logging.

### Script.py (Low)
- Fixed a split `</code>` tag in help text, `message` → `query` in the
  results template, and a Kannada info block referencing
  `message.from_user` in a callback context.

---

## 6. Behavior changes (deliberate, bug-driven)

1. Flood-hit extra bot tokens are skipped instead of crashing startup
   (`TechVJ/bot/clients.py`).
2. `info.py` fails fast on invalid config instead of running misconfigured.
3. Long autodeletes (5–20 min) now run as background tasks; the command handler
   returns immediately. The deletion/notice outcome is unchanged.
4. Indexing resumes after FloodWait (capped 300 s sleeps) instead of dying;
   aborts with a message after 10 consecutive FloodWaits.
5. Dashboard requires a server-side session — old forged `admin_auth=true`
   cookies stop working.
6. The "Edit & Post" button in upcoming-movie details was removed (it never
   worked — no handler existed).
7. Stream pages no longer receive the TMDB API key (poster falls back to the
   default image).
8. `aiofiles` dropped from requirements (never imported).

---

## 7. Verification outcomes (2026-09-26)

| Check | Result |
|---|---|
| `python -m compileall` (whole repo, Python 3.12) | ✅ PASS (one pre-existing `SyntaxWarning` in `plugins/index.py` fixed via raw string) |
| Clean Python 3.12 venv + `pip install -r requirements.txt` | ✅ PASS — all 15 pinned packages + deps installed, incl. building `tgcrypto` |
| `git diff --check` | ✅ PASS (repo-local `core.whitespace=cr-at-eol` set; repo is CRLF throughout) |
| Full diff review | ✅ done — 33 files, +1128/−999, all hunks reviewed |
| Pristine comparison | ✅ `~/workspace/moovidex-review` (branch `clean`, untouched) used as baseline |
| Filename header sanitizer | ✅ micro-test: `"`, CR, LF stripped |
| `tojson` XSS test | ✅ `Evil"</script><script>alert(1)</script>` safely escaped |
| `req.html` Jinja parse | ✅ previously raised `TemplateSyntaxError`; now compiles and renders |
| `info.py` config check | ✅ dummy-env import passed (earlier pass) |
| Live bot run / Telegram | ⛔ not done by design (needs real credentials) |
| GitHub push | ⛔ not done — working copy only, per instructions |

## 8. Follow-ups for the deployer (Hari)

1. **Rotate the old TMDB and Deepgram keys** — they are in the branch's git
   history; removing them from the working tree does not revoke them.
2. Set the new environment variables the code now supports: payment UPI,
   `BINGED_ADMIN_IDS`, `UPDATE_CHANNEL_ID`.
3. The exact `^languages#` vs broad `^languages` callback handlers in
   `plugins/pm_filter.py` are both still registered — consider consolidating.
4. Stream range/mid-stream error paths were hardened for headers but not
   load-tested (no live run possible here).
5. `database/topdb.py`'s dead console loop was removed; if any ops runbook
   invoked it, that path is gone.
