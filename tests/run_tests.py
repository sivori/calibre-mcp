'''
End-to-end tests against a throwaway library. Run with calibre's Python:

    calibre-debug tests/run_tests.py

Builds a temp library with a few books (one with a TXT format so full-text
search has something to index), then exercises the tools directly and over
HTTP. Never touches a real library.
'''

import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calibre.ebooks.metadata.book.base import Metadata  # noqa: E402
from calibre.library import db as open_db  # noqa: E402

from calibre_mcp import tools  # noqa: E402
from calibre_mcp.server import MCPServer  # noqa: E402

TEXT = (
    'It was the best of times, it was the worst of times. The knight moved '
    'his bishop across the board and considered the chess problem for an hour. '
) * 20

failures = []


def check(name, cond, detail=''):
    print(('ok    ' if cond else 'FAIL  ') + name + (f'  ({detail})' if detail and not cond else ''))
    if not cond:
        failures.append(name)


def build_library(path):
    db = open_db(path).new_api
    txt = os.path.join(path, '..', 'book.txt')
    with open(txt, 'w') as f:
        f.write(TEXT)
    books = [
        ('A Tale of Two Cities', ['Charles Dickens'], ['Fiction', 'Classics'], {'TXT': txt}),
        ('The Chess Players', ['Ann Example'], ['Chess'], {}),
        ('Untitled Notes', ['Ann Example'], ['Fiction'], {}),
    ]
    ids = []
    for title, authors, tags, fmts in books:
        mi = Metadata(title, authors)
        mi.tags = tags
        mi.comments = '<p>A <b>description</b>.</p>'
        ids.extend(db.add_books([(mi, fmts)])[0])
    return db, ids


def wait_for_fts(db, seconds=120):
    db.enable_fts(start_pool=True)
    deadline = time.time() + seconds
    while time.time() < deadline:
        left, total, _ = db.fts_indexing_progress()
        if total and not left:
            return True
        time.sleep(1)
    return False


def rpc(url, method, params=None, req_id=1, headers=None):
    body = {'jsonrpc': '2.0', 'method': method}
    if req_id is not None:
        body['id'] = req_id
    if params is not None:
        body['params'] = params
    req = urllib.request.Request(url, json.dumps(body).encode(), method='POST', headers={
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
        **(headers or {}),
    })
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, None


def test_tools(db, ids):
    dickens, chess, notes = ids
    info = tools.library_info(db)
    check('library_info counts books', info['book_count'] == 3, info)

    r = tools.search_books(db, 'author:dickens')
    check('search_books by author', [b['id'] for b in r['books']] == [dickens], r)
    check('search_books empty query lists all', tools.search_books(db)['total'] == 3)
    check('search_books respects limit', len(tools.search_books(db, limit=1)['books']) == 1)

    b = tools.get_book(db, dickens)
    check('get_book has formats', b['formats'] == ['TXT'], b)
    check('get_book strips HTML', b['description'] == 'A **description**.', b['description'])
    try:
        tools.get_book(db, 9999)
        check('get_book unknown id raises', False)
    except tools.ToolError:
        check('get_book unknown id raises', True)

    c = tools.list_categories(db, 'tags')
    check('list_categories counts', c['items'][0] == {'name': 'Fiction', 'books': 2}, c)
    try:
        tools.list_categories(db, 'formats')
        check('list_categories rejects bad field', False)
    except tools.ToolError:
        check('list_categories rejects bad field', True)

    try:
        tools.search_full_text(db, 'chess')
        check('full text errors clearly when FTS is off', False)
    except tools.ToolError as e:
        check('full text errors clearly when FTS is off', 'not enabled' in str(e))

    check('get_annotations empty', tools.get_annotations(db)['total'] == 0)


def test_full_text(db, ids):
    dickens = ids[0]
    check('FTS indexing finishes', wait_for_fts(db))
    r = tools.search_full_text(db, 'bishop')
    check('search_full_text finds the word', r['total'] == 1 and r['results'][0]['book_id'] == dickens, r)
    check('search_full_text highlights', '**bishop**' in (r['results'][0]['snippet'] or ''), r)
    p = tools.get_passage(db, dickens, 'chess problem', words=60)
    check('get_passage returns longer text', len(p['passage'].split()) > 30, p)
    try:
        tools.get_passage(db, dickens, 'zeppelin')
        check('get_passage miss raises', False)
    except tools.ToolError:
        check('get_passage miss raises', True)


def test_http(db, ids):
    server = MCPServer(lambda: db, 0, log=lambda *a: None)
    server.port = 0
    server.start()
    server.port = server.httpd.server_address[1]
    url = server.url
    try:
        status, r = rpc(url, 'initialize', {
            'protocolVersion': '2025-06-18', 'capabilities': {},
            'clientInfo': {'name': 'test', 'version': '0'}})
        check('initialize negotiates version', status == 200 and r['result']['protocolVersion'] == '2025-06-18', r)
        status, r = rpc(url, 'initialize', {'protocolVersion': '1999-01-01'})
        check('initialize falls back to latest', r['result']['protocolVersion'] == '2025-11-25', r)

        status, r = rpc(url, 'notifications/initialized', req_id=None)
        check('notification gets 202 with no body', status == 202 and r is None, status)

        status, r = rpc(url, 'tools/list', headers={'MCP-Protocol-Version': '2025-06-18'})
        names = [t['name'] for t in r['result']['tools']]
        check('tools/list returns 7 tools', len(names) == 7, names)

        status, r = rpc(url, 'tools/call', {'name': 'search_books', 'arguments': {'query': 'chess'}})
        payload = json.loads(r['result']['content'][0]['text'])
        check('tools/call search_books', payload['total'] == 1 and not r['result']['isError'], r)

        status, r = rpc(url, 'tools/call', {'name': 'get_book', 'arguments': {'book_id': 9999}})
        check('tool errors set isError', r['result']['isError'], r)
        status, r = rpc(url, 'tools/call', {'name': 'get_book', 'arguments': {'bogus': 1}})
        check('unknown arguments set isError', r['result']['isError'], r)
        status, r = rpc(url, 'tools/call', {'name': 'nope', 'arguments': {}})
        check('unknown tool is a JSON-RPC error', r['error']['code'] == -32602, r)
        status, r = rpc(url, 'resources/list')
        check('unknown method is -32601', r['error']['code'] == -32601, r)

        status, _ = rpc(url, 'ping', headers={'Origin': 'https://evil.example'})
        check('foreign Origin is rejected', status == 403, status)
        status, r = rpc(url, 'ping', headers={'Origin': 'http://localhost:3000'})
        check('localhost Origin is allowed', status == 200, status)
        status, _ = rpc(url, 'ping', headers={'MCP-Protocol-Version': '1999-01-01'})
        check('unsupported protocol header is 400', status == 400, status)

        status, _ = rpc(url.replace('/mcp', '/other'), 'ping')
        check('other paths 404', status == 404, status)
        try:
            urllib.request.urlopen(url)
            check('GET is 405', False)
        except urllib.error.HTTPError as e:
            check('GET is 405', e.code == 405, e.code)
    finally:
        server.stop()


def main():
    root = tempfile.mkdtemp(prefix='calibre-mcp-test-')
    lib = os.path.join(root, 'library')
    os.mkdir(lib)
    db = None
    try:
        db, ids = build_library(lib)
        test_tools(db, ids)
        test_http(db, ids)
        test_full_text(db, ids)
    finally:
        if db is not None:
            db.close()
        shutil.rmtree(root, ignore_errors=True)
    print(f'\n{len(failures)} failure(s)' if failures else '\nall passed')
    sys.exit(1 if failures else 0)


main()
