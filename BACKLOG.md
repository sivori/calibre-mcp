## Now
- [ ] Submit the Claude plugin to the directory at claude.ai/directory/manage (Plugin bundle, repo sivori/calibre-mcp, root path, branch master). Needs GitHub connected on claude.ai; expect a "known brand" reviewer hold on the calibre name

## Next
- [ ] Publish a GitHub release with the calibre plugin zip so installing doesn't need a clone + build.sh
- [ ] Windows: the bridge runs `python3`, which often isn't on PATH there (`py`/`python` are). Test on Windows, or document the workaround
- [ ] Install 0.2.0 into the running calibre (live copy is 0.1.1; works through the bridge, just no tool titles)
- [ ] Native support for the 2026-07-28 revision (stateless, per-request `_meta`, `server/discover`). Today modern clients fall back to `initialize`; a modern-only client would fail
- [ ] Optional bearer token for clients that support headers, for machines shared with other users
- [ ] `get_passage` can only return the first match; add an `occurrence` index, or a mode that returns every match in the book
- [ ] Submit to the calibre plugin index (MobileRead forum thread + zip)

## Someday
- [ ] Sortes Calibrianae: a `random_passage` tool (needs a way to read raw book text; FTS only returns snippets around matches) @idea
- [ ] Covers as MCP image content in `get_book` @idea
- [ ] Expose reading progress from the calibre viewer @idea

## Done
- [x] 2026-10-05 v0.2.1: calibre toolbar icon is now SVG (text), clearing the directory's "image file the plugin's code could run" policy hold
- [x] 2026-10-05 v0.2.0: Claude plugin bundle for the directory. Stdio bridge (mcp/bridge.py, offline tools.json fallback), calibre-library skill, PRIVACY.md, self-hosted marketplace.json, tool titles; bridge tested under system python3 and via `claude --plugin-dir`
- [x] 2026-10-04 v0.1.1: security pass. Disabled template: searches (python: templates gave code execution via search_books), Host-header check, 1 MB request cap
- [x] 2026-10-04 v0.1.0: seven read-only tools, stdlib streamable HTTP server, tests on a throwaway library, verified with Claude Code
