# Copyright (C) 2010-2017, kachelaqa <kachelaqa@gmail.com>

import urllib.parse


def make_url(url, query=()):
    parts = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse((
        parts.scheme, parts.netloc,
        urllib.parse.quote(parts.path), urllib.parse.quote(parts.params),
        urllib.parse.urlencode(query, True), ''))
