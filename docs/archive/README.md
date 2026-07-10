# Historical Documentation Archive

This folder keeps earlier NovelCraft documentation packages for reference.

## Included

### 1. NovelCraft-V2-Personal-Pro-Plus-Full-Documentation/ (37 docs)
The most comprehensive V2 documentation set. Covers the full Personal Pro+ vision:
00-项目总览 through 36-商业化规划 — from project overview, PRD, architecture, database, API design, AI Agent system, content production (novel/short/social/video), workflow engine, Knowledge Hub, publishing, overseas expansion, deployment, security, testing, and roadmap.

### 2. NovelCraft-V2-Personal-Pro-Plus-Complete-Documentation/ (14 docs)
A condensed documentation package covering the same scope in fewer, larger documents: project positioning, PRD, system architecture, database design (DDL + schema), API (OpenAPI), Agent architecture, story engine, content production, automation pipeline, deployment, sprint planning, Prompt specs, and testing standards.

### 3. NovelCraft-V2-All-Documentation/
- **NovelCraft-V2-Documentation/** (12 docs): Original V2 baseline — requirements, architecture, database, API, task breakdown, testing, PRD, implementation blueprint, ER diagrams, Agent design, and UI specs.
- **NovelCraft-V2-Enterprise-Documentation/** (13 docs): Enterprise-oriented documentation — backend/frontend standards, DevOps, AI model system, novel engine, viral content analysis, auto-serialization, overseas publishing, SaaS commercialization, security, testing, roadmap, and project management.

## Current Baseline

These are historical/expanded documentation sets. The **current implementation baseline** is:

- `docs/NovelCraft-开发文档/` (18 V2.1 documents) — the authoritative, actively maintained documentation set
- `docs/IDEA.md` — project idea and vision
- `PROJECT_PROGRESS.md` — current development progress

For any development work, refer to the V2.1 documents, not the archive.

## Document Status

All archive documents have been populated with substantive content based on the V2.1 specification and detailed feature list. No empty stub documents remain.

## Not Included

The following local archive files were intentionally not committed:

- `/Users/genius/Documents/NovelCraft-V2-All-Documentation.zip`
- `/Users/genius/Documents/NovelCraft-V2-Personal-Pro-Documentation.zip`
- `/Users/genius/Documents/NovelCraft-V2-Personal-Pro-Plus-Complete-Documentation.zip`
- `/Users/genius/Documents/NovelCraft-V2-Personal-Pro-Plus-Full-Documentation.zip`
- `/Users/genius/Documents/NovelCraft-五次修复全量审查版.tar`
- `/Users/genius/Documents/NovelCraft-六次修复全量审查版.tar`
- `/Users/genius/Documents/NovelCraft-七次真实修复版.tar`

Reasons:

- The `.zip` files duplicate documentation already committed as readable Markdown.
- The `.tar` files are binary code snapshots. One archive is about 137 MB, which is not suitable for normal GitHub source tracking.
- If these archives must be preserved later, use GitHub Releases or Git LFS instead of the main repository history.
