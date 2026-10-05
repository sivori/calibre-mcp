# calibre-mcp

Lets Claude read your [calibre](https://calibre-ebook.com) ebook library:
search metadata, search inside the books, pull quotable passages, and read
your highlights and notes. **It is read-only.** No tool writes to the
library.

It has two parts:

1. **A calibre plugin** that serves the library you have open over
   [MCP](https://modelcontextprotocol.io) on `127.0.0.1`. It uses calibre's
   own database API, so there are no lock conflicts with the running app, and
   switching libraries in calibre switches what Claude sees. Any MCP client
   that speaks streamable HTTP can use it directly.
2. **A Claude plugin** ("Calibre Library") that connects Claude to it, with a
   skill that teaches Claude the two search syntaxes and how to quote
   accurately.

Example prompts:

- "What do I own by Ursula K. Le Guin, and which haven't I highlighted?"
- "Find where the whale is first described in Moby-Dick and quote the passage."
- "Summarize everything I've highlighted about habit formation, with the book for each."

## Tools

| Tool | What it does |
| - | - |
| `library_info` | Book count, full-text indexing status, annotation count |
| `search_books` | Metadata search in calibre syntax: `author:dickens`, `tags:Fiction and pubdate:<1900` |
| `get_book` | Full metadata for one book, including description and custom columns |
| `list_categories` | Tags, authors, series, publishers or languages, with counts |
| `search_full_text` | Search inside the books; one highlighted snippet per matching book |
| `get_passage` | A longer passage around a match, for quoting in context |
| `get_annotations` | Highlights and notes from the calibre viewer, optionally filtered |

## Install

### 1. The calibre plugin

Requires calibre 6 or later. Download `calibre-mcp-<version>.zip` from the
[latest release](https://github.com/sivori/calibre-mcp/releases/latest) (or
build it from a checkout with `./build.sh`). Then in calibre: **Preferences → Plugins → Load plugin from file**, choose
the zip, and restart calibre. (Or install from the checkout with
`calibre-customize -b calibre-mcp/calibre_mcp`. On macOS, `calibre-customize`
and `calibre-debug` are in `/Applications/calibre.app/Contents/MacOS/`.)

Add the **MCP** button to a toolbar under **Preferences → Toolbars & menus**
to see the server's status, copy the connect command, or stop and start the
server.

For `search_full_text` and `get_passage`, turn on calibre's full-text search
(**Preferences → Searching → Full text search**). Until indexing has run
they return an error saying so, not an empty result.

### 2. Connect Claude

**With the Claude plugin** (Claude Code, and Cowork sessions on your
computer): add **Calibre Library** from the plugin directory, or in Claude
Code:

```sh
claude plugin marketplace add sivori/calibre-mcp
claude plugin install calibre-mcp@sivori-calibre
```

The plugin runs `mcp/bridge.py` with your system `python3` (3.8 or later,
standard library only, no packages to install; on macOS it comes with
the Xcode Command Line Tools or Homebrew). The bridge forwards Claude's
requests to calibre on `127.0.0.1`. If calibre is closed, the tools say so
instead of failing silently. The plugin can't be used in claude.ai chat on the
web or phone, which doesn't run local servers.

If you changed the port in calibre, set `CALIBRE_MCP_PORT` in the
environment Claude runs in.

**Without the plugin**, add the calibre server to Claude Code directly:

```sh
claude mcp add --transport http calibre http://127.0.0.1:8395/mcp
```

### Codex and other MCP clients

The calibre side is a plain MCP server, so any client that runs local
servers can use it. In the [Codex CLI](https://github.com/openai/codex):

```sh
codex mcp add calibre --url http://127.0.0.1:8395/mcp
```

That writes this to `~/.codex/config.toml`:

```toml
[mcp_servers.calibre]
url = "http://127.0.0.1:8395/mcp"
```

For a client that only runs stdio servers, use the bridge from a checkout
instead. It works the same way and starts even when calibre is closed:

```sh
codex mcp add calibre -- python3 /path/to/calibre-mcp/mcp/bridge.py
```

OpenAI's plugin directory only takes MCP servers at public HTTPS URLs, so
calibre-mcp isn't listed there. Your library never leaves your machine.

## Settings

**Preferences → Plugins → Calibre MCP → Customize plugin**: the port (default
`8395`) and whether the server starts with calibre.

## Security

- Binds to `127.0.0.1` only; it is not reachable from other machines.
- Rejects requests whose `Host` or `Origin` header isn't localhost, so a web
  page can't reach it via DNS rebinding.
- Calibre's `template:` searches are disabled in `search_books`. They can run
  Python, which would let anyone who can send a query (including text that
  talks a model into searching for it) run code inside calibre.
- Book text, descriptions and annotations go to your MCP client as-is. Treat
  them like any other untrusted content an assistant reads.
- The Claude plugin's bridge talks only to `127.0.0.1`. It has no other
  network access and stores nothing. See [PRIVACY.md](PRIVACY.md).
- There is no authentication: any process on your machine can read the
  library while calibre runs. That is the same access those processes already
  have to the library folder.

## Protocol notes

The plugin uses only the Python standard library, because calibre bundles its
own Python and third-party packages such as the MCP SDK aren't available. It
implements the `initialize`-based protocol revisions (`2025-03-26` through
`2025-11-25`) with plain JSON responses: no SSE streams and no sessions.
Clients on newer per-request-metadata revisions get a `400` on their probe and
fall back to `initialize`, as the spec describes. Claude Code does this.

## Development

```sh
calibre-debug tests/run_tests.py
claude plugin validate .
```

The tests build a throwaway library in a temp directory (including a
full-text index), call the tools directly, over HTTP and through the
bridge (under the system `python3`, with calibre up and with nothing
listening), then delete it. If you change a tool's schema, refresh the
bridge's offline tool list with `calibre-debug tests/run_tests.py --
--export-tools`.

To try the Claude plugin from a checkout: `claude --plugin-dir .`

To try a change in the real app: reinstall with `calibre-customize -b
calibre_mcp`, then run `calibre-debug -g` so the plugin's output shows in your
terminal.

## License

GPL v3, like calibre itself.
