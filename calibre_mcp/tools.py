'''
The MCP tools. Each implementation takes a calibre ``Cache`` (``db.new_api``)
and plain arguments, and returns something JSON-serializable. Nothing here
touches the GUI, and nothing here writes to the library.
'''

from calibre.utils.date import is_date_undefined

FTS_DISABLED = (
    'Full-text search is not enabled for this library. Turn it on in '
    'calibre under Preferences > Searching > Full text search, then wait '
    'for indexing to finish.'
)
MAX_SNIPPET_WORDS = 200


class ToolError(Exception):
    '''A problem the caller can fix; reported to the client as isError.'''


def _date(value):
    if value is None or is_date_undefined(value):
        return None
    return value.isoformat()


def _book_summary(db, book_id):
    series = db.field_for('series', book_id)
    rating = db.field_for('rating', book_id)
    pubdate = db.field_for('pubdate', book_id)
    return {
        'id': book_id,
        'title': db.field_for('title', book_id),
        'authors': list(db.field_for('authors', book_id)),
        'series': series or None,
        'series_index': db.field_for('series_index', book_id) if series else None,
        'tags': list(db.field_for('tags', book_id)),
        'published': pubdate.year if pubdate and not is_date_undefined(pubdate) else None,
        'formats': list(db.formats(book_id)),
        'rating': rating / 2 if rating else None,
    }


def _require_book(db, book_id):
    if not isinstance(book_id, int) or not db.has_id(book_id):
        raise ToolError(f'No book with id {book_id!r} in this library.')


def _require_fts(db):
    if not db.is_fts_enabled():
        raise ToolError(FTS_DISABLED)


def library_info(db):
    left, total, _ = db.fts_indexing_progress()
    fts = db.is_fts_enabled()
    return {
        'book_count': len(db.all_book_ids()),
        'full_text_search': {
            'enabled': fts,
            'formats_indexed': total - left if fts else 0,
            'formats_total': total if fts else 0,
        },
        'annotation_count': len(db.all_annotations(ignore_removed=True)),
    }


def search_books(db, query='', limit=25):
    ids = db.search(query) if query else db.all_book_ids()
    ids = sorted(ids, key=lambda i: db.field_for('sort', i) or '')
    return {
        'total': len(ids),
        'books': [_book_summary(db, i) for i in ids[:limit]],
    }


def get_book(db, book_id):
    _require_book(db, book_id)
    from calibre.utils.html2text import html2text

    book = _book_summary(db, book_id)
    comments = db.field_for('comments', book_id)
    book.update({
        'publisher': db.field_for('publisher', book_id) or None,
        'languages': list(db.field_for('languages', book_id)),
        'identifiers': dict(db.field_for('identifiers', book_id)),
        'added': _date(db.field_for('timestamp', book_id)),
        'description': html2text(comments).strip() if comments else None,
        'annotation_count': len(db.all_annotations(
            restrict_to_book_ids={book_id}, ignore_removed=True)),
    })
    custom = {}
    for key in db.field_metadata.custom_field_keys():
        value = db.field_for(key, book_id)
        if value in (None, '', (), []):
            continue
        name = db.field_metadata[key].get('name') or key
        custom[name] = list(value) if isinstance(value, (tuple, set, frozenset)) else (
            _date(value) if hasattr(value, 'isoformat') else value)
    if custom:
        book['custom_columns'] = custom
    return book


CATEGORY_FIELDS = ('tags', 'authors', 'series', 'publisher', 'languages')


def list_categories(db, field='tags', limit=100):
    if field not in CATEGORY_FIELDS:
        raise ToolError(f'field must be one of: {", ".join(CATEGORY_FIELDS)}')
    names = db.get_id_map(field)
    counts = db.get_usage_count_by_id(field)
    items = sorted(
        ({'name': names[i], 'books': n} for i, n in counts.items() if n and i in names),
        key=lambda x: (-x['books'], x['name']),
    )
    return {'field': field, 'total': len(items), 'items': items[:limit]}


def search_full_text(db, query, book_ids=None, limit=20, snippet_words=30):
    _require_fts(db)
    restrict = set(book_ids) if book_ids else None
    try:
        hits = db.fts_search(
            query,
            highlight_start='**', highlight_end='**',
            snippet_size=max(5, min(snippet_words, MAX_SNIPPET_WORDS)),
            restrict_to_book_ids=restrict,
        )
    except Exception as e:
        raise ToolError(f'Bad full-text query {query!r}: {e}')
    # calibre indexes each format separately, so the same book usually hits
    # once per format with near-identical snippets. Keep one result per book.
    by_book = {}
    for hit in hits:
        bid = hit['book_id']
        if bid in by_book:
            by_book[bid]['formats'].append(hit['format'])
            continue
        by_book[bid] = {
            'book_id': bid,
            'title': db.field_for('title', bid),
            'formats': [hit['format']],
            'snippet': hit.get('text'),
        }
    results = list(by_book.values())
    return {'total': len(results), 'results': results[:limit]}


def get_passage(db, book_id, query, words=120):
    _require_book(db, book_id)
    out = search_full_text(
        db, query, book_ids=[book_id], limit=1,
        snippet_words=max(20, min(words, MAX_SNIPPET_WORDS)))
    if not out['results']:
        raise ToolError(f'{query!r} does not appear in book {book_id}.')
    hit = out['results'][0]
    return {
        'book_id': book_id,
        'title': hit['title'],
        'authors': list(db.field_for('authors', book_id)),
        'formats': hit['formats'],
        'passage': hit['snippet'],
    }


def _annotation(db, entry, titles):
    a = entry.get('annotation', {})
    bid = entry['book_id']
    if bid not in titles:
        titles[bid] = db.field_for('title', bid)
    return {
        'book_id': bid,
        'title': titles[bid],
        'type': a.get('type'),
        'highlighted_text': a.get('highlighted_text'),
        'note': a.get('notes') or None,
        'chapter': ' / '.join(a.get('toc_family_titles') or []) or None,
        'timestamp': a.get('timestamp'),
    }


def get_annotations(db, book_id=None, query=None, limit=50):
    if book_id is not None:
        _require_book(db, book_id)
    restrict = {book_id} if book_id is not None else None
    titles = {}
    if query:
        try:
            entries = db.search_annotations(
                query, restrict_to_book_ids=restrict, ignore_removed=True)
        except Exception as e:
            raise ToolError(f'Bad annotation query {query!r}: {e}')
    else:
        entries = db.all_annotations(
            restrict_to_book_ids=restrict, ignore_removed=True)
    return {
        'total': len(entries),
        'annotations': [_annotation(db, e, titles) for e in entries[:limit]],
    }


def _limit(default, maximum):
    return {'type': 'integer', 'minimum': 1, 'maximum': maximum, 'default': default}


TOOLS = [
    {
        'name': 'library_info',
        'description': 'Book count, whether full-text search is enabled and how much is indexed, and the annotation count.',
        'fn': library_info,
        'inputSchema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'search_books',
        'description': (
            'Search book metadata using calibre search syntax, e.g. "chess", '
            '"author:dickens", "tags:Fiction and pubdate:<1900", "series:true". '
            'An empty query lists every book. Results are sorted by title.'
        ),
        'fn': search_books,
        'inputSchema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'calibre search expression'},
                'limit': _limit(25, 200),
            },
        },
    },
    {
        'name': 'get_book',
        'description': 'Full metadata for one book: description, publisher, identifiers, languages, custom columns, annotation count.',
        'fn': get_book,
        'inputSchema': {
            'type': 'object',
            'properties': {'book_id': {'type': 'integer'}},
            'required': ['book_id'],
        },
    },
    {
        'name': 'list_categories',
        'description': 'Tags, authors, series, publishers or languages in the library, with book counts, most-used first.',
        'fn': list_categories,
        'inputSchema': {
            'type': 'object',
            'properties': {
                'field': {'type': 'string', 'enum': list(CATEGORY_FIELDS), 'default': 'tags'},
                'limit': _limit(100, 1000),
            },
        },
    },
    {
        'name': 'search_full_text',
        'description': (
            'Search inside the text of the books (calibre full-text search; '
            'SQLite FTS5 syntax: words, "exact phrases", AND/OR/NOT, prefix*). '
            'Returns one highlighted snippet per matching book.'
        ),
        'fn': search_full_text,
        'inputSchema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string'},
                'book_ids': {'type': 'array', 'items': {'type': 'integer'},
                             'description': 'Only search these books'},
                'limit': _limit(20, 100),
                'snippet_words': {'type': 'integer', 'minimum': 5,
                                  'maximum': MAX_SNIPPET_WORDS, 'default': 30},
            },
            'required': ['query'],
        },
    },
    {
        'name': 'get_passage',
        'description': 'A longer passage from one book around the first match for the query, for quoting or reading in context.',
        'fn': get_passage,
        'inputSchema': {
            'type': 'object',
            'properties': {
                'book_id': {'type': 'integer'},
                'query': {'type': 'string'},
                'words': {'type': 'integer', 'minimum': 20,
                          'maximum': MAX_SNIPPET_WORDS, 'default': 120},
            },
            'required': ['book_id', 'query'],
        },
    },
    {
        'name': 'get_annotations',
        'description': 'Highlights and notes made in the calibre viewer, optionally for one book and/or matching a text query.',
        'fn': get_annotations,
        'inputSchema': {
            'type': 'object',
            'properties': {
                'book_id': {'type': 'integer'},
                'query': {'type': 'string'},
                'limit': _limit(50, 500),
            },
        },
    },
]

for _t in TOOLS:
    _t['annotations'] = {'readOnlyHint': True, 'openWorldHint': False}

TOOLS_BY_NAME = {t['name']: t for t in TOOLS}
