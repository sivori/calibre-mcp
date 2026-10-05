'''
A minimal MCP server over the streamable HTTP transport, stdlib only (calibre
bundles its own Python, so the MCP SDK is not available).

Every request gets a single JSON response; there are no SSE streams and no
server-initiated messages, which the spec allows. No session ids are issued.
'''

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .tools import TOOLS, TOOLS_BY_NAME, ToolError

ENDPOINT = '/mcp'
SUPPORTED_VERSIONS = ('2025-11-25', '2025-06-18', '2025-03-26')
SERVER_INFO = {'name': 'calibre-mcp', 'version': '0.2.1'}
LOCAL_HOSTS = {'localhost', '127.0.0.1', '[::1]', '::1'}
MAX_BODY = 1 << 20  # requests are small JSON-RPC calls

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def _result(req_id, result):
    return {'jsonrpc': '2.0', 'id': req_id, 'result': result}


def _error(req_id, code, message):
    return {'jsonrpc': '2.0', 'id': req_id, 'error': {'code': code, 'message': message}}


def _tool_text(payload, is_error=False):
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=1)
    return {'content': [{'type': 'text', 'text': text}], 'isError': is_error}


class MCPServer:
    '''Owns the HTTP server thread. ``get_db`` returns the current Cache.'''

    def __init__(self, get_db, port, log=print):
        self.get_db = get_db
        self.port = port
        self.log = log
        self.httpd = None
        self.thread = None

    @property
    def url(self):
        return f'http://127.0.0.1:{self.port}{ENDPOINT}'

    def start(self):
        handler = type('Handler', (_Handler,), {'mcp': self})
        self.httpd = ThreadingHTTPServer(('127.0.0.1', self.port), handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(
            target=self.httpd.serve_forever, name='calibre-mcp', daemon=True)
        self.thread.start()
        self.log(f'calibre-mcp: listening on {self.url}')

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            self.log('calibre-mcp: stopped')

    @property
    def running(self):
        return self.httpd is not None

    # JSON-RPC dispatch

    def handle(self, msg):
        '''Returns a response dict, or None for notifications and responses.'''
        if not isinstance(msg, dict) or msg.get('jsonrpc') != '2.0':
            return _error(None, INVALID_REQUEST, 'Expected a JSON-RPC 2.0 object')
        method = msg.get('method')
        if 'id' not in msg or method is None:
            return None  # notification (e.g. notifications/initialized) or a response
        req_id = msg['id']
        params = msg.get('params') or {}
        try:
            if method == 'initialize':
                return _result(req_id, self.initialize(params))
            if method == 'ping':
                return _result(req_id, {})
            if method == 'tools/list':
                return _result(req_id, {'tools': [
                    {k: t[k] for k in ('name', 'title', 'description', 'inputSchema', 'annotations')}
                    for t in TOOLS
                ]})
            if method == 'tools/call':
                return _result(req_id, self.call_tool(params))
            return _error(req_id, METHOD_NOT_FOUND, f'Unknown method: {method}')
        except _InvalidParams as e:
            return _error(req_id, INVALID_PARAMS, str(e))
        except Exception as e:
            self.log(f'calibre-mcp: {method} failed: {e!r}')
            return _error(req_id, INTERNAL_ERROR, f'{type(e).__name__}: {e}')

    def initialize(self, params):
        requested = params.get('protocolVersion')
        version = requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
        return {
            'protocolVersion': version,
            'capabilities': {'tools': {'listChanged': False}},
            'serverInfo': SERVER_INFO,
            'instructions': (
                "Read-only access to the user's calibre ebook library. Use "
                'search_books for metadata, search_full_text / get_passage for '
                'the text of the books, get_annotations for highlights.'
            ),
        }

    def call_tool(self, params):
        name = params.get('name')
        tool = TOOLS_BY_NAME.get(name)
        if tool is None:
            raise _InvalidParams(f'Unknown tool: {name}')
        args = params.get('arguments') or {}
        if not isinstance(args, dict):
            raise _InvalidParams('arguments must be an object')
        allowed = tool['inputSchema'].get('properties', {})
        unknown = set(args) - set(allowed)
        if unknown:
            return _tool_text(f'Unknown argument(s): {", ".join(sorted(unknown))}', True)
        missing = set(tool['inputSchema'].get('required', ())) - set(args)
        if missing:
            return _tool_text(f'Missing argument(s): {", ".join(sorted(missing))}', True)
        db = self.get_db()
        if db is None:
            return _tool_text('No calibre library is open.', True)
        try:
            return _tool_text(tool['fn'](db, **args))
        except ToolError as e:
            return _tool_text(str(e), True)
        except TypeError as e:
            return _tool_text(f'Bad arguments for {name}: {e}', True)


class _InvalidParams(Exception):
    pass


class _Handler(BaseHTTPRequestHandler):
    mcp = None  # set per server
    server_version = 'calibre-mcp'
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        pass  # calibre's console doesn't need a line per request

    def _send(self, status, body=None, content_type='application/json'):
        data = b'' if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
        if status >= 400:
            self.close_connection = True
        self.send_response(status)
        if body is not None:
            self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        if self.close_connection:
            self.send_header('Connection', 'close')
        self.end_headers()
        if data:
            self.wfile.write(data)

    def _check(self):
        '''Path, Origin (DNS rebinding) and protocol-version checks.'''
        if urlparse(self.path).path.rstrip('/') != ENDPOINT:
            self._send(404, _error(None, INVALID_REQUEST, f'MCP endpoint is {ENDPOINT}'))
            return False
        # DNS rebinding: a page on attacker.example resolved to 127.0.0.1
        # arrives with that name in Host (and usually in Origin).
        host = (self.headers.get('Host') or '').rsplit(':', 1)[0]
        if host not in LOCAL_HOSTS:
            self._send(403, _error(None, INVALID_REQUEST, 'Host not allowed'))
            return False
        origin = self.headers.get('Origin')
        if origin and urlparse(origin).hostname not in LOCAL_HOSTS:
            self._send(403, _error(None, INVALID_REQUEST, 'Origin not allowed'))
            return False
        version = self.headers.get('MCP-Protocol-Version')
        if version and version not in SUPPORTED_VERSIONS:
            self._send(400, _error(None, INVALID_REQUEST, f'Unsupported MCP-Protocol-Version: {version}'))
            return False
        return True

    def _read_body(self):
        # Some clients (Claude Code among them) send chunked bodies with no
        # Content-Length; http.server doesn't decode those for us.
        if 'chunked' in self.headers.get('Transfer-Encoding', '').lower():
            chunks = []
            while True:
                size = int(self.rfile.readline().split(b';')[0].strip(), 16)
                if size == 0:
                    while self.rfile.readline() not in (b'\r\n', b'\n', b''):
                        pass  # trailers
                    return b''.join(chunks)
                if sum(map(len, chunks)) + size > MAX_BODY:
                    raise ValueError('body too large')
                chunks.append(self.rfile.read(size))
                self.rfile.readline()  # CRLF after each chunk
        length = int(self.headers.get('Content-Length') or 0)
        if length > MAX_BODY:
            raise ValueError('body too large')
        return self.rfile.read(length)

    def do_POST(self):
        # Always drain the body first: answering early on a keep-alive
        # connection leaves the JSON to be parsed as the next request line.
        try:
            raw = self._read_body()
        except ValueError:
            self.close_connection = True
            self._send(400, _error(None, PARSE_ERROR, 'Malformed request body'))
            return
        if not self._check():
            return
        try:
            msg = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            self._send(400, _error(None, PARSE_ERROR, 'Body is not valid JSON'))
            return
        if isinstance(msg, list):
            self._send(400, _error(None, INVALID_REQUEST, 'Batches are not supported'))
            return
        # Clients on the per-request-metadata revisions (2026-07-28+) probe
        # first and fall back to initialize on a plain 400.
        meta = ((msg.get('params') or {}) if isinstance(msg, dict) else {}).get('_meta') or {}
        version = meta.get('io.modelcontextprotocol/protocolVersion')
        if version and version not in SUPPORTED_VERSIONS:
            self._send(400, _error(msg.get('id'), INVALID_REQUEST,
                                   f'Unsupported protocol version {version}; '
                                   f'this server speaks {", ".join(SUPPORTED_VERSIONS)} via initialize'))
            return
        response = self.mcp.handle(msg)
        if response is None:
            self._send(202)
        else:
            self._send(200, response)

    def do_GET(self):
        if self._check():
            self.send_response(405)
            self.send_header('Allow', 'POST')
            self.send_header('Content-Length', '0')
            self.end_headers()

    def do_DELETE(self):
        self.do_GET()
