# Knowledge Base source documents

These files are the ground truth the Bedrock Knowledge Base (see `infra/infra/knowledge_base_stack.py`)
is built from. Nothing here is synced or ingested automatically — that sync/ingest workflow is
built in US-4. Until then, editing a file here has no effect on the live KB.

| File | Purpose | Owner / update cadence |
|---|---|---|
| `resume.pdf` | Source-of-truth resume, exported as PDF. Copied from `~/Downloads/Ian_Koplowitz_Resume.pdf`. | Ian — update whenever the canonical resume changes, then re-copy here. |
| `about-me.md` | First-person narrative expanding on background, current role, and interests. Initial draft generated from resume content on 2026-07-13 and needs a human review pass. | Ian — review/edit draft, then keep in sync with how he wants to be represented conversationally (tone, interests, framing) rather than just resume facts. |
| `star-answers.md` | STAR-method (Situation/Task/Action/Result) behavioral stories, for grounding answers to "tell me about a time..." style questions. Currently a placeholder/template only. | Ian — fill in real stories; expand over time as new examples come up. |

When any file here changes, it needs to be re-synced to the KB's S3 source bucket and a new
ingestion job started (US-4) before the change is reflected in agent answers.
