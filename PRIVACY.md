# Privacy policy

calibre-mcp (the calibre plugin and the Claude plugin, "Calibre Library")
runs entirely on your computer. It has no servers and no accounts, and it
doesn't collect analytics or telemetry.

## What it reads

When an AI assistant calls one of its tools, it reads from the calibre
library you have open:

- Book metadata: titles, authors, tags, series, publishers, dates, ratings,
  descriptions, identifiers and custom columns
- Book text, through calibre's full-text search index, if you've enabled it
- Highlights and notes you made in calibre's viewer

It reads only what a tool call asks for. It never writes to the library.

## Where that data goes

- The calibre plugin serves the library on `127.0.0.1` (port 8395 by
  default), which only programs on your own computer can reach.
- The Claude plugin's bridge (`mcp/bridge.py`) connects only to that local
  address.
- Tool results go to the AI assistant you're using, such as Claude, which
  handles them under that provider's own privacy policy (for Claude, see
  https://www.anthropic.com/legal/privacy). Results contain only what was
  asked for, such as a search's matching books or one passage.

Nothing else is sent anywhere.

## Storage and retention

calibre-mcp stores nothing. It keeps no logs, caches or copies of your
library, and keeps nothing after a tool call returns. Its only saved state
is its settings (port, start with calibre) in calibre's own plugin
configuration.

## Children

It isn't directed at children under 18.

## Contact

Questions or concerns: open an issue at
https://github.com/sivori/calibre-mcp/issues.

## Changes

Changes to this policy are made in this file and recorded in the
repository's history.
