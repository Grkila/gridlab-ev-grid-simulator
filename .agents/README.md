# Agent memory protocol

Agents cannot reliably “memorize the README” across tasks. Durable project knowledge lives in versioned files.

At task start, follow the reading order in the root `AGENTS.md` and then read the nearest subtree instructions. At task end, update `PROJECT_MEMORY.md` only when a fact is durable and verified. Record the fact, evidence or command, date, and affected paths. Put architectural choices in `DECISIONS.md` and operational commands in `RUNBOOK.md`.

Do not store secrets, credentials, personal data, copied chat history, raw logs, transient tool output, or speculation. Label assumptions. Replace stale facts instead of accumulating contradictory entries. Keep the memory compact enough to reread at every task start.
