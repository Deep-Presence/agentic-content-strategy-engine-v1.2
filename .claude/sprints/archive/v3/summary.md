# Sprint v3 — Summary

**Date:** 2026-03-04
**Sprint Goal:** Fix 9 P3 bugs from combined manual + Codex review (site audit pipeline)

## Completed Tasks
| Task ID | Description | Tests Added | Files Changed |
|---------|-------------|-------------|---------------|
| T-SA-32 | Integration test artifact isolation — `output_dir` param | +2 | pipeline.py, test_integration.py |
| T-SA-31 | AuditConfig `__post_init__` validation (8 checks, ValueError) | +11 | config.py, test_config_validation.py (NEW) |
| T-SA-23 | Robust date parsing via `python-dateutil` | +8 | eeat_signals.py, pyproject.toml, test_checks.py |
| T-SA-24 | Missing date metadata finding (article pages only) | +5 | eeat_signals.py, s2_analyze_pages.py, test_checks.py |
| T-SA-29 | Question-heading classifier expansion (Rule 3: wh-words without ?) | +10 | extractability.py, test_aeo.py |
| T-SA-30 | Quick-answer hook window expansion (15-150 words, heading boundary) | +10 | extractability.py, config.py, s4_check_aeo.py, test_aeo.py |
| T-SA-26 | Product and Speakable schema validators | +16 | schema_checks.py, test_schema.py |
| T-SA-27 | URL normalization — canonical_url() for dedup | +8 | s1_discover.py, test_crawler.py |
| T-SA-28 | Crawl-delay parsing and reporting | +12 | s1_discover.py, site_audit.py, pipeline.py, test_crawler.py |

## Decisions Made
- D1: Wh-word headings without `?` classified as questions (>= 4 words guard, 7 core wh-words only)
- D2: Quick-answer word range 15-150 (configurable via AuditConfig)
- D3: Missing date finding for article pages only (low severity)
- D4: Crawl-delay: parse+report only, no enforcement (capped at 300s)
- D5: Canonical URL split from request URL (sorts params, strips www, removes default ports)

## Failures Encountered
- None

## Deferred to Backlog
- T-SA-25: DROPPED — title/meta thresholds already configurable via AuditConfig
- Crawl-delay enforcement (rate limiting) — deferred, needs shared domain-level rate limiter

## Test Count
- Start of session: ~793 site audit tests (after all fixes + the percent-encoding fix)
- End of session: 793 tests (82 new, all passing)

## Key Metrics
- Tasks completed: 9
- Tasks deferred: 1 (T-SA-25 dropped)
- Files changed: ~11
- Codex review findings incorporated: 14/14
