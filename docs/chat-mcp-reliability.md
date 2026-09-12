# Chat and MCP reliability

The chat keeps its conversation ID across reloads, recovers active work from the local server, and offers saved conversations and a separate new-conversation action. Browser storage is scoped to the resolved experiment store. Missing conversations recover to an empty composer; a restarted backend marks abandoned turns interrupted.

The server remains limited to one active chat turn. It publishes terminal status and releases the send gate together, after process cleanup. Cancellation remains visible until this transition. Minimize does not cancel. Cancelling a chat response does not cancel experiments it already started; their run IDs remain available and Runs owns their cancellation.

Send requests have persistent idempotency keys. If a response is lost, the browser checks whether that request was accepted before retrying. Reusing a key with different input is rejected. Polling is sequential, has a timeout and capped reconnect backoff, and rejects responses from an earlier conversation or mutation generation. Failed cancellation remains visible.

## Conversation and evidence

Messages and observable CLI events carry server-generated IDs, a turn ID, and a monotonically increasing sequence. Assistant text renders once; repeated identical user messages remain separate. CLI item IDs are scoped to a turn. Historical records lacking turn information are marked legacy rather than inventing tool chronology.

The HTTP chat snapshot accepts `after=<sequence>` and returns a cursor. A retention gap or an oversized message backlog triggers `reset: true`. The initial snapshot contains at most 100 messages; earlier messages are available through the history endpoint. Events are limited to 500 entries and approximately 256 KB of serialized content. Large entries become previews with links. Full completed MCP tool output is saved separately, including output that later leaves the event window. The saved-tool-evidence index is paginated.

Each ordinary CLI turn still starts with read-only workspace access; a validated explicit implementation selector or STRATEGY BUILD request enables workspace editing for that turn. Context contains at most 20 recent messages and 40,000 transcript characters, recent referenced immutable IDs, and user-pinned constraints verbatim. Omitted history is explicitly disclosed to the agent. Pinned constraints are edited in chat and saved with the next message; they are not inferred or automatically summarized. Referenced IDs are retrieval hints, not proof of results. Large tool outputs are not blindly replayed into model context.

## MCP result access

New case evidence has a separate derived summary containing all fields except interval, session, block and hierarchy detail. Summary reads and run comparisons use this cache; source size and modification time invalidate stale entries. Older artifacts lazily generate the same summaries, with a read-only-storage fallback. Detail evidence is never rewritten, and inability to save a derived cache does not fail a simulation.

`ev_list_experiments(limit=20, after=None)` returns compact experiment/run entries in ID order. Pass its `next_cursor` back as `after` until null. `ev_get_experiment(experiment_id)` retrieves a full immutable definition. `ev_get_results` also supports `limit` and `after`; both limits are bounded at 100. Full interval detail still requires a case ID. Result pagination never narrows the evaluation: `evaluation_scope: whole_run` and `total_cases` describe the entire run. Comparisons preserve completeness, provenance fingerprints, and paired-input checks.

The plugin configuration remains machine-specific because it launches a native interpreter. `scripts/setup_playground_plugin.py` validates the environment and regenerates those paths after moving or cloning the checkout. It works when invoked by absolute path outside the repository and supports an explicit interpreter/output destination.

## Verification

Use the project Python environment:

```text
python -m unittest discover -s tests -v
python scripts/verify_playground_mcp.py
python scripts/verify_chat_storage.py
npm --prefix web run build
node scripts/verify_chat_gui.cjs
```

Windows setup installs Playwright for the browser check. It launches an isolated real HTTP server and a deliberately fake CLI emitting JSONL. It exercises repeated messages, reused CLI item IDs, full evidence retrieval, reload, multiple tabs, minimize/cancel, a lost accepted POST response, polling loss, cancellation failure, new conversations and mobile layout. It never launches Codex or pays for a model call. The stdio check separately runs the real MCP server and simulations.

The synthetic storage check measures a 1 MB tool result: full results remain retrievable, the summary response is 256 bytes, warm summary reads open no detail files, and an unchanged chat poll is 239 bytes. These are fixture measurements, not a claim about simulation speed.

Logs are under `artifacts/playground/chat-*.log`; generated storage evidence is `artifacts/playground/evidence/chat-storage-check.json`. The build still reports the existing large JavaScript chunk warning. MCP/plugin/chat standardization is documented in `docs/agent-contract.md`; model-cost optimization is outside this scope.
