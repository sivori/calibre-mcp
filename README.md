# calibre-mcp

A [calibre](https://calibre-ebook.com) plugin that lets Claude, or any other
[MCP](https://modelcontextprotocol.io) client, read your ebook library:
search metadata, search inside the books, pull passages, and read your
highlights.

It runs inside calibre and serves the library you have open over MCP's
streamable HTTP transport on `127.0.0.1`. Because it uses calibre's own
database API, there are no lock conflicts with the running app, and switching
libraries in calibre switches what the tools see.

**It is read-only.** No tool writes to the library.

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

`search_full_text` and `get_passage` need calibre's full-text search turned on
(**Preferences → Searching → Full text search**). Until indexing has run they
return an error saying so, not an empty result.

## Install

Requires calibre 6 or later.

```sh
git clone https://github.com/sivori/calibre-mcp
calibre-customize -b calibre-mcp/calibre_mcp
```

Or build a zip and load it in calibre under **Preferences → Plugins → Load
plugin from file**:

```sh
cd calibre-mcp/calibre_mcp && zip -r ../calibre-mcp.zip .
```

Restart calibre. Add the **MCP** button to a toolbar under **Preferences →
Toolbars & menus** to see the server's status, copy the connect command, or
stop and start the server.

On macOS, `calibre-customize` and `calibre-debug` are in
`/Applications/calibre.app/Contents/MacOS/`.

## Connect

The server listens at `http://127.0.0.1:8395/mcp` while calibre is running.

```sh
claude mcp add --transport http calibre http://127.0.0.1:8395/mcp
```

Add `-s user` to make it available in every project. Other clients that
support streamable HTTP servers take the same URL.

## Settings

**Preferences → Plugins → Calibre MCP → Customize plugin**: the port (default
`8395`) and whether the server starts with calibre.

## Security

- Binds to `127.0.0.1` only; it is not reachable from other machines.
- Rejects requests whose `Origin` header isn't localhost, so a web page can't
  reach it via DNS rebinding.
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
```

The tests build a throwaway library in a temp directory (including a
full-text index), call the tools directly and over HTTP, then delete it.

To try a change in the real app: reinstall with `calibre-customize -b
calibre_mcp`, then run `calibre-debug -g` so the plugin's output shows in your
terminal.

## License

GPL v3, like calibre itself.
