## Now

## Next
- [ ] Native support for the 2026-07-28 revision (stateless, per-request `_meta`, `server/discover`). Today modern clients fall back to `initialize`; a modern-only client would fail
- [ ] Optional bearer token for clients that support headers, for machines shared with other users
- [ ] `get_passage` can only return the first match; add an `occurrence` index, or a mode that returns every match in the book
- [ ] Submit to the calibre plugin index (MobileRead forum thread + zip)

## Someday
- [ ] Sortes Calibrianae: a `random_passage` tool (needs a way to read raw book text; FTS only returns snippets around matches) @idea
- [ ] Covers as MCP image content in `get_book` @idea
- [ ] Expose reading progress from the calibre viewer @idea

## Done
- [x] 2026-10-04 v0.1.1: security pass. Disabled template: searches (python: templates gave code execution via search_books), Host-header check, 1 MB request cap
- [x] 2026-10-04 v0.1.0: seven read-only tools, stdlib streamable HTTP server, tests on a throwaway library, verified with Claude Code
