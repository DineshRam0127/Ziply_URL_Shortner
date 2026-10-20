# Intent:

Workshop template. Fill in the sections marked **(fill in)** and leave the rest as-is. Keep it small — one service, one or two features.

---

## How to run

1. Save this file as `aidlc/spaces/default/knowledge/documents/intent.md`
2. Start the workflow:

`/aidlc express --depth minimal --test-strategy minimal --review advisory --guard-policy off --summary-confirmation off`

3. Then send:

`Read aidlc/spaces/default/knowledge/documents/intent.md and build what it describes`

4. When the agent asks a question, **"recommended"** is almost always the right answer. You'll still hit a few approval gates and one **Plan Approval** before any code is written — read them, then approve.

**Prerequisites:** Python 3 only. **No Docker required** — the app and its tests run locally with plain pytest.

---

## Run configuration — leave as-is

| Setting | Value |
|---|---|
| Scope | express |
| Depth | minimal |
| Test strategy | minimal |
| Reviews | advisory |
| Guard policy | off |
| Summary confirmation | off |
| Construction autonomy | automatic |
| Architecture | ONE modular monolith (not multiple services) |
| Tenancy | single-tenant |

**Standing instruction to the agent:** accept all recommended options by default; only ask when a decision is genuinely blocking and has no reasonable default. Record assumptions and keep going — never stop just to confirm one.

---

## What to build

Ziply is an existing URL-shortening web application built with Python, FastAPI, SQLite, HTML, CSS, and JavaScript. It converts long URLs into short, shareable links and redirects visitors to their original destinations. Extend the existing application without replacing its architecture or removing working features.

## Who uses it

Individuals and developers who need to create, manage, share, and track short URLs through a web interface.

## Must-have behaviors

- Generate unique short URLs from valid long URLs and redirect visitors to the original destinations; return an appropriate error for unknown or expired links.
- Support optional custom aliases and link expiration, with URL data persisted in SQLite.
- Provide QR-code generation, click analytics, and bulk URL shortening through CSV uploads.
- Preserve existing project data and working features when making changes, and verify the application with automated tests.

## Out of scope

- Do not split the application into microservices or replace FastAPI, Python, or SQLite with another technology stack.
- Do not introduce Docker, an external database server, or unnecessary infrastructure.
- Do not delete, reset, truncate, or recreate the existing SQLite database or remove existing features.
- Do not add unrelated features beyond the URL-shortening application's intended scope.

---

## Decisions already made — leave as-is (adjust only if you care)

- **Stack:** Python with a file-based **SQLite** database (or a simple in-memory store) — **no Docker, no database server to install**. Any cloud/Terraform is authored, not applied.
- **Tests:** plain pytest, run locally. Do not require Docker, testcontainers, or an external database.
- **Auth:** none for now (keep it simple).
- **Performance, availability, retention, compliance, other non-functional targets:** accept recommended defaults.

## Assumptions — leave as-is

Accept all reasonable assumptions; record them in the artifacts and keep moving. Do not stop to confirm an assumption.