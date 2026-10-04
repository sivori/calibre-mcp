#!/bin/sh
# Builds calibre-mcp-<version>.zip, the file calibre's "Load plugin from file"
# and the MobileRead plugin thread expect.
set -e
cd "$(dirname "$0")/calibre_mcp"
version=$(sed -n 's/^    version = (\([0-9]*\), \([0-9]*\), \([0-9]*\)).*/\1.\2.\3/p' __init__.py)
out="../calibre-mcp-$version.zip"
rm -f "$out"
zip -qr "$out" . -x '*__pycache__*' -x '.DS_Store'
echo "$out"
