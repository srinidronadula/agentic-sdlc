# Brownfield run

**Requirement:** Add custom aliases to the existing URL shortener. Callers may optionally send `alias` with `POST /shorten`. Reject aliases that are taken, reserved, or invalid. Keep random codes when alias is omitted. Do not rewrite the service.

This run patched `workspace/` (greenfield artifact) instead of starting over.

| | |
|---|---|
| Run id | `ad239710-2aec-444a-9f06-e762b582f60f` |
| Status | **succeeded** |
| Model | Claude Haiku 4.5 |
| Test retries | 0 |
| Human gate | approved before **implement** |
| Tests | **38 passed** (12 existing + 26 alias tests) |

## Decomposition

`understand → design → [human approve] → implement → test → docs`

Understand listed alias-format questions, then bounded assumptions (3–50 chars, lowercase + hyphens, 409 on taken, optional field). Design named impacted files (`app.py`, `service.py`, `db.py`, new `alias_validator.py`) and said it would not rewrite the service.

## Validation

Surgical patch: existing random-code APIs still work. New tests in `workspace/tests/test_aliases.py`.
