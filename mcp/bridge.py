'''
Stdio MCP server for the Claude plugin. It forwards each request to the
calibre-mcp plugin running inside calibre (http://127.0.0.1:8395/mcp) and
writes the reply back. Standard library only.

The bridge answers initialize and ping itself, so the server starts cleanly
while calibre is closed. tools/list falls back to tools.json (exported from
calibre_mcp/tools.py and checked by the tests) and tools/call returns an
error telling the user to open calibre.

The only network traffic is to 127.0.0.1. Set CALIBRE_MCP_PORT if you
changed the port in calibre's plugin settings.
'''

import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get('CALIBRE_MCP_PORT') or 8395)
URL = f'http://127.0.0.1:{PORT}/mcp'
TIMEOUT = 60  # full-text searches over a large library can take a while
SUPPORTED_VERSIONS = ('2025-11-25', '2025-06-18', '2025-03-26')
SERVER_INFO = {'name': 'calibre', 'version': '0.2.0'}
INSTRUCTIONS = (
    "Read-only access to the user's calibre ebook library. Use search_books "
    'for metadata, search_full_text / get_passage for the text of the books, '
    'get_annotations for highlights. calibre must be running with the '
    'calibre-mcp plugin installed.'
)
NOT_RUNNING = (
    f'calibre is not reachable at {URL}. Ask the user to open calibre. If it '
    'is open, the calibre-mcp plugin may not be installed or its server may '
    'be stopped: see https://github.com/sivori/calibre-mcp#install.'
)

INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601


def _result(req_id, result):
    return {'jsonrpc': '2.0', 'id': req_id, 'result': result}


def _error(req_id, code, message):
    return {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': code, 'message': message}}


class Unreachable(Exception):
    pass


def forward(msg):
    '''POSTs one JSON-RPC message to calibre and returns the decoded reply.'''
    req = urllib.request.Request(
        URL, data=json.dumps(msg).encode('utf-8'), method='POST',
        headers={'Content-Type': 'application/json',
                 'Accept': 'application/json, text/event-stream'})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read()  # calibre-mcp puts a JSON-RPC error in 4xx bodies
    except (urllib.error.URLError, OSError) as e:
        raise Unreachable(str(e))
    try:
        return json.loads(body.decode('utf-8'))
    except ValueError:
        raise Unreachable('calibre-mcp returned a non-JSON reply')


def offline_tools():
    with open(os.path.join(HERE, 'tools.json'), encoding='utf-8') as f:
        return json.load(f)


def handle(msg):
    if not isinstance(msg, dict) or msg.get('jsonrpc') != '2.0':
        return _error(None, INVALID_REQUEST, 'Expected a JSON-RPC 2.0 object')
    if 'id' not in msg or 'method' not in msg:
        return None  # notification or a response; nothing to send back
    req_id, method = msg['id'], msg['method']
    params = msg.get('params') or {}

    # Clients on the per-request-metadata revisions (2026-07-28+) probe first
    # and fall back to initialize on an error, as calibre-mcp's HTTP side does.
    version = (params.get('_meta') or {}).get('io.modelcontextprotocol/protocolVersion')
    if version and version not in SUPPORTED_VERSIONS:
        return _error(req_id, INVALID_REQUEST,
                      f'Unsupported protocol version {version}; this server '
                      f'speaks {", ".join(SUPPORTED_VERSIONS)} via initialize')

    if method == 'initialize':
        requested = params.get('protocolVersion')
        return _result(req_id, {
            'protocolVersion': requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0],
            'capabilities': {'tools': {'listChanged': False}},
            'serverInfo': SERVER_INFO,
            'instructions': INSTRUCTIONS,
        })
    if method == 'ping':
        return _result(req_id, {})
    if method == 'tools/list':
        try:
            return forward(msg)
        except Unreachable:
            return _result(req_id, {'tools': offline_tools()})
    if method == 'tools/call':
        try:
            return forward(msg)
        except Unreachable:
            return _result(req_id, {
                'content': [{'type': 'text', 'text': NOT_RUNNING}], 'isError': True})
    return _error(req_id, METHOD_NOT_FOUND, f'Unknown method: {method}')


def main():
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            response = _error(None, -32700, 'Parse error')
        else:
            response = handle(msg)
        if response is not None:
            out.write(json.dumps(response, ensure_ascii=False) + '\n')
            out.flush()


if __name__ == '__main__':
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    main()
