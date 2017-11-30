# Copyright (C) 2010-2017, kachelaqa <kachelaqa@gmail.com>

import sys, os, re, glob, copy, errno, socket, json
import urllib.request, urllib.error, http.client
from zipfile import ZipFile, BadZipfile
from html.parser import HTMLParser
from traceback import format_exception
from functools import cmp_to_key
from collections import defaultdict
from multiprocessing import Pool
from threading import Thread
from queue import Queue
from pkgbrowser import alpm, conf, utils
from pkgbrowser.enum import State, Source


AUR_DOM = os.environ.get('AUR_DOM', 'https://aur.archlinux.org')
AUR_RPC = AUR_DOM + '/rpc.php'
AUR_HTM = AUR_DOM + '/packages.php'
AUR_SRC = AUR_DOM + '/cgit/aur.git/plain/.SRCINFO'
PACNET_DOM = ('http://pacnet.karbownicki.com',
              'http://pacnet.archlinux.pl')
PACNET_CAT = '/api/categories/'
PACNET_LIST = '/api/category/%s/'
ALA_DOM = os.environ.get('ALA_DOM', 'https://archive.archlinux.org')
ALA_LIST = ALA_DOM + '/packages/%s/%s/'
ARCH_PKG = 'https://www.archlinux.org/packages/%s/%s/%s'

_arch_repos = set([
    'core', 'extra', 'community', 'multilib',
    'testing', 'community-testing', 'multilib-testing',
    ])


class BackendError(Exception): pass


class DatabaseError(BackendError):
    def __init__(self, source='', errno=None):
        self.source = source
        if errno is None:
            self.errno = alpm.error_number()
        else:
            self.errno = int(errno)
        BackendError.__init__(self, alpm.error_string(self.errno))

    def __str__(self):
        message = self.args[0]
        if self.source:
            message = '%s: %s' % (message, self.source)
        return '[Errno %d] %s' % (self.errno, message)

    def __reduce__(self):
        return (self.__class__, (self.source, self.errno))


class NetworkError(BackendError):
    def __init__(self, url, reason=None):
        if isinstance(reason, socket.timeout):
            message = '[Errno %d] %s' % (
                errno.ETIMEDOUT, os.strerror(errno.ETIMEDOUT))
        elif isinstance(reason, EnvironmentError):
            if reason.errno in errno.errorcode:
                message = '[Errno %d] %s' % (
                    reason.errno, os.strerror(reason.errno))
            else:
                message = reason.strerror
        elif isinstance(reason, int):
            message = '[HTTP %d] %s' % (
                reason, http.client.responses.get(reason, ''))
        elif reason is None:
            message = 'Unknown error'
        else:
            message = str(reason)
        BackendError.__init__(self, message)
        self.url = url

    def __reduce__(self):
        return (self.__class__, (self.url, self.args[0]))


class PatternError(BackendError):
    def __init__(self, text, message):
        BackendError.__init__(self, message)
        self.text = text

    def __reduce__(self):
        return (self.__class__, (self.text, self.args[0]))


class Traceback(Exception):
    @staticmethod
    def format(*args):
        if len(args) == 3:
            return ''.join(format_exception(*args))
        return args and args[0] or ''

    def __init__(self, *args):
        Exception.__init__(self, self.format(*args))

    def __reduce__(self):
        return (self.__class__, self.args)


class Cache(object):
    _caches = {}
    _path = ''
    _offline = False

    @classmethod
    def set_path(cls, path):
        cls._path = path

    @classmethod
    def set_offline(cls, offline):
        cls._offline = bool(offline)

    @classmethod
    def has_files(cls):
        if cls._path:
            return any(os.access(path, os.R_OK) for path in
                       glob.glob(os.path.join(cls._path, '*.files.zip')))
        return False

    @classmethod
    def get_files(cls, package):
        if alpm.pkg_get_installdate(package):
            return alpm.pkg_join_files(package) or ''
        else:
            key = alpm.pkg_get_repository(package)
            cache = cls._caches.get(key)
            if cache is None:
                path = os.path.join(cls._path, '%s.files.zip' % key)
                try:
                    cache = cls._caches[key] = ZipFile(path)
                except (IOError, BadZipfile):
                    pass
            if cache is not None:
                try:
                    files = cache.read(alpm.pkg_get_fullname(package))
                except KeyError:
                    pass
                except (IOError, BadZipfile):
                    cls.clear(key)
                else:
                    return files.decode('utf-8')

    @classmethod
    def get_log(cls, *names):
        key = 'log.zip'
        cache = cls._caches.get(key)
        if cache is None:
            path = alpm.option_get_logfile()
            try:
                cache = cls._caches[key] = conf.load_logfile(path)
            except (IOError, BadZipfile):
                pass
        if cache is not None:
            log = []
            try:
                for name in names:
                    try:
                        entry = cache.read(name)
                    except KeyError:
                        pass
                    else:
                        log.extend(entry.decode('utf-8').splitlines())
                return '\n'.join(sorted(
                    log, key=lambda line: line.partition(']')[0]))
            except (IOError, BadZipfile):
                cls.clear(key)

    @classmethod
    def get_cache(cls, arch, *names):
        if arch == 'any':
            architectures = [os.uname()[4], 'any']
        else:
            architectures = [arch, 'any']
        sources = [[] for name in names]
        key = 'pkgcache.zip'
        cache = cls._caches.get(key)
        if cache is None:
            paths = alpm.option_get_cachedirs()
            try:
                cache = cls._caches[key] = conf.load_pkgcache(paths)
            except (IOError, BadZipfile):
                pass
        if cache is not None:
            try:
                for index, name in enumerate(names):
                    source = sources[index]
                    for arch in architectures:
                        path = '%s/%s' % (name, arch)
                        try:
                            entry = cache.read(path)
                        except KeyError:
                            pass
                        else:
                            source.extend(entry.decode('utf-8').splitlines())
            except (IOError, BadZipfile):
                cls.clear(key)
        if not cls._offline and ALA_DOM:
            parser = AlaParser()
            urls = [utils.make_url(ALA_LIST % (name[0], name))
                    for name in names]
            downloads = Downloader.download(urls, True)
            for index, url in enumerate(urls):
                data = downloads.get(url)
                if data is None:
                    continue
                source = sources[index]
                data = parser.read(data)
                for arch in architectures:
                    path = '%s/%s' % (names[index], arch)
                    if path not in data:
                        continue
                    for package in data[path]:
                        source.append(os.path.join(url, package))
        compare = cmp_to_key(
            lambda a, b, cmp=alpm.pkg_vercmp, match=conf.match_pkgfile:
                cmp(match(b).group(2), match(a).group(2)))
        for source in sources:
            source.sort(key=compare)
        return sources

    @classmethod
    def clear(cls, *args):
        for key in args or list(cls._caches.keys()):
            try:
                cls._caches.pop(key).close()
            except Exception:
                pass


class Downloader(Thread):
    @staticmethod
    def download(urls, quiet=False):
        tasks = Queue()
        output = Queue()
        for index, url in enumerate(urls):
            if index < 10:
                Downloader(tasks, output)
            tasks.put(url)
        tasks.join()
        result = {}
        while not output.empty():
            url, data, exception = output.get()
            if not quiet and exception is not None:
                raise exception
            result[url] = data
        return result

    def __init__(self, tasks, output):
        Thread.__init__(self)
        self._tasks = tasks
        self._output = output
        self.daemon = True
        self.start()

    def run(self):
        while True:
            url = self._tasks.get()
            try:
                response = urllib.request.urlopen(url, timeout=20)
                try:
                    self._output.put((url, response.read(), None))
                finally:
                    response.close()
            except urllib.error.HTTPError as exception:
                self._output.put(
                    (url, None, NetworkError(url, exception.code)))
            except urllib.error.URLError as exception:
                self._output.put(
                    (url, None, NetworkError(url, exception.reason)))
            except BaseException:
                self._output.put(
                    (url, None, Traceback(*sys.exc_info())))
            finally:
                self._tasks.task_done()


class AlaParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)

    def read(self, data):
        self._link = False
        self._info = defaultdict(list)
        self.reset()
        try:
            self.feed(data.decode('utf-8', 'replace'))
        except AssertionError:
            pass
        return self._info

    def handle_starttag(self, tag, attrs):
        self._link = tag == 'a'

    def handle_data(self, data):
        if self._link:
            data = data.strip()
            match = conf.match_pkgfile(data)
            if match is not None:
                self._info['%s/%s' % match.group(1, 3)].append(data)

    def handle_endtag(self, tag):
        self._link = False


class AurParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)

    def read(self, data):
        self._key = None
        self._link = False
        self._info = defaultdict(list)
        self.reset()
        try:
            self.feed(data.decode('utf-8', 'replace'))
        except AssertionError:
            pass
        return self._info

    def handle_starttag(self, tag, attrs):
        if tag == 'div':
            if len(self._info) < 2:
                key = dict(attrs).get('id')
                if key == 'pkgreqs':
                    self._key = 'RequiredBy'
        elif tag == 'a' and self._key:
            self._link = True

    def handle_data(self, data):
        if self._link:
            self._info[self._key].append(data.strip())

    def handle_endtag(self, tag):
        if self._link:
            self._link = False
        elif tag == 'div' and self._key:
            self._key = None
            self._link = False


class Matcher(object):
    Not = 1
    Exact = 2
    RegExp = 4
    Group = 8

    def __init__(self, text, getters, files=False):
        self._text = text
        self._getters = getters
        self._targets = self._compile(
            self._parse(iter(text)), files)

    def _parse(self, text, context=0):
        result = []
        element = []
        term = [0, '']
        alt = quoted = False
        char = quote = ''
        while char is not None:
            try:
                if not char:
                    char = next(text)
            except StopIteration:
                char = None
            else:
                if not quote:
                    if char == '(':
                        if not term[1]:
                            term[1] = self._parse(
                                text, term[0] | context | Matcher.Group)
                            if not term[1]:
                                term = [0, '']
                            char = ''
                    elif char == ')':
                        if context & Matcher.Group:
                            if not term[1]:
                                context = 0
                                break
                        else:
                            context |= Matcher.Group
                            break
                    elif char in '"\'':
                        quote = char
                        char = ''
                    elif char in '|~=%':
                        if not term[1]:
                            if char == '~':
                                term[0] |= Matcher.Not
                            elif char == '=':
                                term[0] |= Matcher.Exact
                            elif char == '%':
                                term[0] |= Matcher.RegExp
                            else:
                                alt = True
                            char = ''
                            continue
                    elif not char.isspace():
                        term[1] += char
                        char = ''
                        continue
                    else:
                        char = ''
                elif char == quote:
                    quote = char = ''
                    quoted = True
                else:
                    term[1] += char
                    char = ''
                    continue
            if term[1] or quoted:
                if context & Matcher.Group:
                    if context & Matcher.Not:
                        term[0] ^= Matcher.Not
                        if result:
                            alt = not alt
                    term[0] |= context & (Matcher.Exact | Matcher.RegExp)
                if isinstance(term[1], list):
                    term[0] = Matcher.Group
                if term[0] & Matcher.Group and len(term[1]) == 1:
                    terms = term[1][0]
                else:
                    terms = [term]
                if alt:
                    element = terms
                    alt = False
                else:
                    element.extend(terms)
                if element is not (result and result[-1]):
                    result.append(element)
                term = [0, '']
            quoted = False
        if quote:
            raise PatternError(self._text, 'unclosed quote')
        elif context & Matcher.Group:
            raise PatternError(self._text, 'unclosed parenthesis')
        return result

    def _compile(self, items, files=False):
        result = []
        flags = re.M if files else re.M | re.I
        for item in items:
            element = set()
            for term in item:
                if term[0] & Matcher.Group:
                    term = (term[0], self._compile(term[1], files))
                else:
                    if files and not term[0] & Matcher.RegExp:
                        pattern = '/%s\n' % term[1].lstrip('/')
                        if term[0] & Matcher.Exact:
                            pattern = '\n' + pattern
                        def search(value, pattern=pattern):
                            return pattern in value or None
                    else:
                        if term[0] & Matcher.RegExp:
                            pattern = term[1]
                        elif term[0] & Matcher.Exact:
                            pattern = '^%s$' % re.escape(term[1])
                        else:
                            pattern = '^.*%s.*$' % re.escape(term[1])
                        try:
                            search = re.compile(pattern, flags).search
                        except re.error as exception:
                            raise PatternError(pattern, str(exception))
                    term = (term[0], term[1], search)
                element.add(term)
            element = tuple(sorted(element, key=cmp_to_key(self._compare)))
            if element not in result:
                result.append(element)
        return tuple(result)

    def _compare(self, a, b):
        if a[0] & (Matcher.Not | Matcher.RegExp):
            if not b[0] & (Matcher.Not | Matcher.RegExp):
                return 1
        elif b[0] & (Matcher.Not | Matcher.RegExp):
            return -1
        if isinstance(a[1], (tuple, list)):
            if isinstance(b[1], (tuple, list)):
                result = self._compare(a[1][0][0], b[1][0][0])
                if not result:
                    return len(a[1]) - len(b[1])
                return result
            return 1
        elif isinstance(b[1], (tuple, list)):
            return -1
        if a[0] & Matcher.Exact:
            if not b[0] & Matcher.Exact:
                return -1
        elif b[0] & Matcher.Exact:
            return 1
        return len(b[1]) - len(a[1])

    def prioritize(self, strict=False):
        return self._prioritize(self._targets, strict)

    def _prioritize(self, items, strict=False):
        result = []
        for index, element in enumerate(items):
            term = element[0]
            if strict and term[0] & Matcher.Not:
                raise PatternError(self._text, 'unqualified negative term')
            if strict and term[0] & Matcher.RegExp:
                raise PatternError(self._text, 'unqualified regexp term')
            if term[0] & Matcher.Group:
                result.extend(self._prioritize(term[1], strict))
            else:
                result.append((bool(term[0] & Matcher.Exact), term[1]))
        return result

    def match(self, item):
        return self._match(item, self._targets)

    def _match(self, item, targets):
        for element in targets:
            terms = set(element)
            found = set()
            for getter in self._getters:
                value = getter(item) or ''
                for term in (terms - found):
                    if term[0] & Matcher.Group:
                        match = self._match(item, term[1])
                    else:
                        match = term[2](value) is not None
                        if term[0] & Matcher.Not:
                            match = not match
                    if match:
                        found.add(term)
                if found == terms:
                    return True
        return False


def _call(args):
    return getattr(backend, args[0])(*args[1:])

def _call_async(args):
    try:
        return _call(args)
    except BackendError as exception:
        return exception
    except BaseException:
        return Traceback(*sys.exc_info())


class Backend(object):
    def __init__(self):
        self._aurparser = AurParser()
        self._rpcs = {}
        self._pool = None
        self._callback = None
        self._offline = False

    def version(self):
        return alpm.version()

    def initialize(self):
        try:
            config = conf.read_config()
        except IOError as exception:
            raise DatabaseError(exception.filename, alpm.ERR_NOT_A_FILE)
        else:
            self.release()
            rootdir = config.get('RootDir')
            if rootdir:
                dbpath = os.path.join(rootdir, conf.PM_DB_PATH)
            else:
                rootdir = conf.PM_ROOT_DIR
                dbpath = config.get('DBPath', conf.PM_DB_PATH)
            error = alpm.initialize(rootdir, dbpath)
            if error == alpm.ERR_NOT_A_DIR:
                if not os.path.isdir(rootdir):
                    raise DatabaseError(rootdir, error)
                raise DatabaseError(dbpath, error)
            elif error:
                raise DatabaseError(None, error)
            arch = config.get('Architecture')
            if arch:
                alpm.option_set_arch(arch)
            for name in config['Repositories']:
                if alpm.register_syncdb(name) is None:
                    raise DatabaseError(name)
            alpm.option_set_logfile(config.get('LogFile', conf.PM_LOG_FILE))
            for path in config.get('CacheDir', conf.PM_CACHE_DIRS):
                alpm.option_add_cachedir(path)
            if self._callback is not None:
                _callback = self._callback
                def callback(items, exception):
                    if exception is None:
                        self._rpcs = dict(items)
                    self._callback = _callback
                    _callback([], exception)
                self.set_callback(callback)
                self._call([['_load']])
            else:
                self._rpcs = dict(self._load())

    def _load(self):
        items = []
        if alpm.is_initialized():
            targets = defaultdict(list)
            source = Source.Local | Source.Foreign
            for location, package in self._iter_packages(source):
                targets[('info', '')].append(alpm.pkg_get_name(package))
            for info in self._fetch_packages(targets):
                items.append((info['Name'], (
                    info['PackageBase'],
                    info['Version'],
                    info['Maintainer'] or '',
                    info['NumVotes'],
                    info['Popularity'],
                    )))
        return items

    def release(self):
        Cache.clear()
        self._rpcs.clear()
        if alpm.is_initialized() and alpm.release() != 0:
            raise DatabaseError()

    def set_offline(self, offline):
        self._offline = bool(offline)
        Cache.set_offline(offline)

    def set_callback(self, callback):
        if self._pool is not None:
            self._pool.terminate()
        self._callback = callback

    def _call(self, args):
        self._pool = Pool()
        if self._callback is not None:
            def callback(results):
                items = []
                exception = None
                for result in results:
                    if not isinstance(result, BaseException):
                        items.extend(result)
                    else:
                        exception = result
                        items = None
                        break
                self._callback(items, exception)
            self._pool.map_async(_call_async, args, callback=callback)
        else:
            items = []
            for item in self._pool.map(_call, args):
                items.extend(item)
            self._pool.terminate()
            return items

    def _iter_dbs(self, source=0, locations=()):
        if not source:
            source = Source.Sync | Source.Local
        if source & Source.Sync:
            item = alpm.get_syncdbs()
            while item is not None:
                db = alpm.list_get_db(item)
                name = alpm.db_get_name(db)
                if not locations or name in locations:
                    yield name, db
                item = alpm.list_next(item)
        if source & Source.Local:
            db = alpm.get_localdb()
            name = alpm.db_get_name(db)
            if not locations or name in locations:
                yield name, db

    def _iter_groups(self, locations=(), match=None):
        for location, db in self._iter_dbs(Source.Sync, locations):
            item = alpm.db_get_groupcache(db)
            while item is not None:
                group = alpm.list_get_group(item)
                item = alpm.list_next(item)
                if match and not match(group):
                    continue
                yield location, group

    def _iter_group(self, locations=(), targets=()):
        for location, db in self._iter_dbs(Source.Sync, locations):
            for target in targets or ():
                group = alpm.db_get_group(db, target)
                item = alpm.group_get_pkgs(group)
                while item is not None:
                    yield location, alpm.list_get_pkg(item)
                    item = alpm.list_next(item)

    def _iter_packages(self, source=0, locations=(), match=None):
        local = alpm.db_get_name(alpm.get_localdb())
        for location, db in self._iter_dbs(source, locations):
            item = alpm.db_get_pkgcache(db)
            while item is not None:
                package = alpm.list_get_pkg(item)
                item = alpm.list_next(item)
                if ((location == local and source & Source.Foreign and
                     alpm.pkg_get_repository(package) != local) or
                    (match and not match(package))):
                    continue
                yield location, package

    def _dispatch(self, keys, source=0):
        if source == Source.Group:
            dispatch = {
                'name': alpm.group_get_name,
                }
        elif source == Source.AUR:
            dispatch = {
                'name': lambda item: item['Name'],
                'description': lambda item: item['Description'],
                'maintainer': lambda item: item['Maintainer'],
                }
        else:
            def pkg_get_maintainer(item):
                name = alpm.pkg_get_name(item)
                if name in self._rpcs:
                    return self._rpcs[name][2]
                return alpm.pkg_get_packager(item)
            dispatch = {
                'name': alpm.pkg_get_name,
                'description': alpm.pkg_get_desc,
                'provides': alpm.pkg_join_provides,
                'replaces': alpm.pkg_join_replaces,
                'depends': alpm.pkg_join_depends,
                'optdepends': alpm.pkg_join_optdepends,
                'maintainer': pkg_get_maintainer,
                'files': Cache.get_files,
                }
        return tuple(dispatch[key] for key in keys if key in dispatch)

    def _fetch_packages(self, targets):
        packages = []
        if not self._offline:
            urls = []
            for (mode, by), targets in targets.items():
                last = len(targets)
                defaults = dict(type=mode, v=5)
                if mode == 'info':
                    key, limit = 'arg[]', 300
                else:
                    key, limit = 'arg', 1
                    defaults['by'] = by
                query = defaultdict(list, defaults)
                for index, target in enumerate(targets, 1):
                    query[key].append(target)
                    if not index % limit or index == last:
                        urls.append(utils.make_url(AUR_RPC, query))
                        query = defaultdict(list, defaults)
            for url, data in Downloader.download(urls).items():
                data = json.loads(data.decode('utf-8', 'replace'))
                if data['type'] == 'error':
                    raise NetworkError(url, data['error'])
                elif data['resultcount']:
                    packages.extend(data['results'])
        return packages

    def _fetch_package(self, name, basename=None, update=False):
        if not self._offline:
            info = None
            urls = {
                'rpc': utils.make_url(
                    AUR_RPC, dict(type='info', arg=name, v=5)),
                'htm': utils.make_url(AUR_HTM, dict(N=name)),
                }
            while True:
                if basename:
                    urls['src'] = utils.make_url(AUR_SRC, dict(h=basename))
                downloads = Downloader.download(urls.values())
                if 'rpc' in urls:
                    url = urls.pop('rpc')
                    data = downloads.get(url)
                    if data is not None:
                        data = json.loads(data.decode('utf-8', 'replace'))
                        if data['type'] == 'error':
                            raise NetworkError(url, data['error'])
                        elif data['resultcount']:
                            info = data['results'][0]
                            data = downloads.get(urls.pop('htm'))
                            if data is not None:
                                info.update(self._aurparser.read(data))
                            if not basename:
                                basename = info['PackageBase']
                                continue
                if info is not None:
                    data = downloads.get(urls['src'])
                    if data is not None:
                        info.update(conf.load_srcinfo(name, data))
                    return AurPackage(info, update=update)
                break
        return NullPackage(name)

    def get_package(self, target, location=None, state=State.Unknown):
        if isinstance(target, Summary):
            state = target.state
            if state & State.AUR and not state & State.Installed:
                location = target.basename
            else:
                location = target.repository
            target = target.name
        update = bool(state & State.Update)
        if state & State.AUR and not state & State.Installed:
            return self._fetch_package(target, location, update)
        elif not state & State.Group:
            locations = location and [location]
            local = localdb = None
            if state & State.Installed or state & State.Unknown:
                localdb = alpm.get_localdb()
                local = alpm.db_get_pkg(localdb, target)
            if state & State.NonInstalled or state & State.Unknown:
                for location, db in self._iter_dbs(Source.Sync, locations):
                    sync = alpm.db_get_pkg(db, target)
                    if sync is not None:
                        if state & State.NonInstalled or local is None:
                            return Package(sync, update=update)
                        else:
                            return Package(local)
                    elif locations:
                        return NullPackage(target)
            if (local is not None and
               (not locations or state & State.Installed)):
                if ((state & State.Foreign or state & State.Unknown) and
                    not state & State.Database):
                    rpc = self._rpcs.get(target)
                    if rpc is not None:
                        aur = self._fetch_package(target, rpc[0], update)
                        return Package(local, aur)
                return Package(local)
            elif not locations and state & State.Unknown:
                provider = alpm.db_find_provider(target, 0)
                if provider is not None:
                    return Package(provider)
                replacer = alpm.db_find_replacer(target, 0)
                if replacer is not None:
                    return Package(replacer)
                if not state & State.Database:
                    return self._fetch_package(target, None, update)
        return NullPackage(target)

    def find(self, text, filters=0, keys=()):
        keys = keys or ['name']
        args = []
        if filters & State.AUR and filters & State.NonInstalled:
            args.append(('_find_aur', text, filters, keys))
        for location in self.list_repositories():
            args.append(('_find', text, filters, keys, [location]))
        return self._call(args)

    def _find(self, text, filters=0, keys=(), locations=()):
        items = []
        if filters & State.Group:
            filters &= ~State.Group
            matcher = Matcher(text, self._dispatch(keys, Source.Group))
            iterator = self._iter_groups(locations, matcher.match)
            items.extend(self._filter_groups(iterator, filters))
        else:
            filters &= ~State.AUR
            args = defaultdict(list)
            for key in keys:
                if key == 'files' and not filters & State.NonInstalled:
                    source = Source.Local
                else:
                    source = Source.Sync | Source.Local | Source.Foreign
                args[source].append(key)
            for source, keys in args.items():
                matcher = Matcher(text, self._dispatch(keys), 'files' in keys)
                iterator = self._iter_packages(
                    source, locations, matcher.match)
                items.extend(self._filter_packages(iterator, filters))
        return items

    def _find_aur(self, text, filters=0, keys=()):
        matcher = Matcher(text, self._dispatch(keys, Source.AUR))
        terms = matcher.prioritize(True)
        maintainer = 'maintainer' in keys
        if 'name' in keys and 'description' not in keys:
            by = 'name'
        else:
            by = 'name-desc'
        targets = defaultdict(list)
        for exact, target in terms:
            if maintainer:
                targets[('search', 'maintainer')].append(target)
            if not maintainer or len(keys) > 1:
                if exact:
                    targets[('info', '')].append(target)
                else:
                    targets[('search', by)].append(target)
        items = []
        seen = set()
        for package in self._fetch_packages(targets):
            identifier = package['ID']
            if identifier not in seen:
                seen.add(identifier)
                if matcher.match(package):
                    items.append(package)
        return self._filter_aur(items, filters)

    def _filter_aur(self, items, filters=0):
        output = []
        for package in items:
            name = package['Name']
            if name not in self._rpcs:
                summary = Summary()
                summary.name = name
                summary.version = package['Version']
                summary.repository = 'aur'
                summary.state = State.NonInstalled | State.AUR
                summary.basename = package['PackageBase']
                summary.votes = package['NumVotes']
                summary.popularity = package['Popularity']
                output.append(summary)
        return output

    def _filter_groups(self, items, filters=0):
        output = []
        if not filters:
            filters = State.Installed | State.NonInstalled | State.Update
        for repository, group in items:
            name = alpm.group_get_name(group)
            summary = Summary()
            summary.name = name
            summary.repository = repository
            summary.state = State.Group | State.Installed
            locations = [repository] if repository else None
            for location, package in self._iter_group(locations, [name]):
                if (summary.state & State.Installed and
                    alpm.pkg_get_status(package) & State.NonInstalled):
                    summary.state = State.Group | State.NonInstalled
                summary.size += alpm.pkg_get_isize(package)
            if filters & summary.state:
                output.append(summary)
        return output

    def _filter_packages(self, items, filters=0):
        output = []
        if not filters:
            filters = State.Installed | State.NonInstalled | State.Update
        localdb = alpm.get_localdb()
        local = alpm.db_get_name(localdb)
        for repository, package in items:
            update = None
            summary = Summary()
            summary.repository = repository
            summary.name = alpm.pkg_get_name(package)
            summary.version = alpm.pkg_get_version(package)
            summary.state = alpm.pkg_get_status(package)
            summary.size = alpm.pkg_get_isize(package)
            if summary.state & State.Installed:
                if summary.repository in (local, 'aur'):
                    rpc = self._rpcs.get(summary.name)
                    if rpc is not None:
                        summary.repository = 'aur'
                        summary.basename = rpc[0]
                        summary.version = rpc[1]
                        summary.state |= State.AUR
                        summary.votes = rpc[3]
                        summary.popularity = rpc[4]
                    elif summary.repository == local:
                        summary.repository = alpm.pkg_get_repository(package)
                if filters & State.Update:
                    state = alpm.pkg_check_update(summary.name,
                                                  summary.version)
                    if filters & state:
                        update = copy.copy(summary)
                        update.state = state | summary.state & State.AUR
                        if update.state & State.AUR:
                            update.size = -1
                        output.append(update)
                current = alpm.db_get_pkg(localdb, summary.name)
                summary.version = alpm.pkg_get_version(current)
                summary.date = alpm.pkg_get_installdate(current)
            if (filters & summary.state and (
                update is None or summary.state & State.AUR or
                summary.repository == alpm.pkg_get_repository(current))):
                output.append(summary)
        return output

    def list_targets(self, targets):
        return self._call([['_list_targets', targets]])

    def _list_targets(self, targets):
        unknown = []
        packages = []
        for target in set(targets):
            package = self.get_package(
                target, state=(State.Database | State.Unknown))
            if package['state'] & State.Unknown:
                unknown.append(target)
            else:
                packages.append((package['repository'], package.base()))
        items = self._filter_packages(packages)
        items.extend(self._filter_aur(
            self._fetch_packages({('info', ''): unknown})))
        return items

    def list_packages(self, filters=0, location=None):
        if filters and filters & State.Foreign:
            source = Source.Local | Source.Foreign
            filters &= ~State.Foreign
        elif location:
            source = Source.Sync
        else:
            source = Source.Sync | Source.Local | Source.Foreign
        packages = self._iter_packages(source, location and [location])
        return self._filter_packages(packages, filters)

    def list_group(self, location=None, target=None):
        packages = self._iter_group(location and [location],
                                    target and [target])
        return self._filter_packages(packages)

    def list_groups(self, location=None):
        groups = self._iter_groups(location and [location])
        return self._filter_groups(groups)

    def list_repositories(self):
        return [repository for repository, db in self._iter_dbs()]

    def list_categories(self):
        return self._call([['_list_categories']])

    def _list_categories(self):
        categories = defaultdict(list)
        data = self._fetch_categories(PACNET_CAT)
        if data is not None:
            for item in json.loads(data.decode('utf-8', 'replace')):
                target = item['name']
                parent, child = target.partition('-')[::2]
                if parent and child:
                    categories[parent].append((child, target))
        return sorted(categories.items())

    def list_category(self, category):
        return self._call([['_list_category', category]])

    def _list_category(self, category):
        packages = []
        data = self._fetch_categories(PACNET_LIST % category)
        if data is not None:
            for item in json.loads(data.decode('utf-8', 'replace')):
                for repository, db in self._iter_dbs(Source.Sync):
                    package = alpm.db_get_pkg(db, item['name'])
                    if package is not None:
                        packages.append((repository, package))
        return self._filter_packages(packages)

    def _fetch_categories(self, path):
        if not self._offline:
            exception = None
            for domain in PACNET_DOM:
                url = utils.make_url(domain + path)
                try:
                    return Downloader.download([url]).get(url)
                except NetworkError as exception:
                    pass
            if exception is not None:
                raise exception

    def statistics(self):
        data = defaultdict(list)
        for package in self.list_packages(State.Installed):
            for key in ('total', package.repository):
                item = data[key]
                if not item:
                    item[:] = [0, 0]
                item[0] += 1
                item[1] += package.size
        stats = []
        for key in self.list_repositories() + ['aur', 'total']:
            item = data.get(key)
            if item is not None:
                stats.append((key, item[0], item[1]))
        return stats


class Summary(object):
    name = ''
    version = ''
    repository = ''
    basename = ''
    state = 0
    date = 0
    size = -1
    votes = -1
    popularity = -1


class BasePackage(object):
    _base = None
    _match = re.compile(r'^([^\s<>=:]*)\s*(.*?)$').match

    def _tree(self):
        result = {'installed': 0, 'missing': 0, 'aur': 0,
                  'isize': 0, 'msize': 0}
        def tree(parent, seen=None):
            output = []
            if seen is None:
                seen = set()
            for depends in (parent.get('depends', ()),
                            parent.get('makedepends', ())):
                for provides, data in depends:
                    if provides in seen:
                        continue
                    seen.add(provides)
                    package = backend.get_package(provides)
                    if isinstance(package, NullPackage):
                        continue
                    name = package['name']
                    state = package['state']
                    if (name == provides and
                        not state & (State.Installed | State.AUR)):
                        provider = alpm.db_find_provider(provides, 1)
                        if provider is not None:
                            package = Package(provider)
                            name = package['name']
                            state = package['state']
                    if name != provides:
                        if name in seen:
                            continue
                        seen.add(name)
                    else:
                        provides = None
                    depends = tree(package, seen)
                    output.append((name, provides, state, depends))
                    if state & State.Installed:
                        result['isize'] += package['size']
                        result['installed'] += 1
                    elif not state & State.AUR:
                        result['msize'] += package['size']
                        result['missing'] += 1
                    else:
                        result['aur'] += 1
            return output
        result['packages'] = tree(self)
        return result

    def _log(self):
        names = (self['replaces'] or '').split()
        names.append(self['name'])
        return Cache.get_log(*names)

    def _cache(self):
        names = [self['name']]
        names.extend((self['replaces'] or '').split())
        return Cache.get_cache(self['arch'], *names)

    def _backup(self):
        item = alpm.pkg_get_backup(self._base)
        while item is not None:
            backup = alpm.list_get_backup(item)
            if backup is not None:
                yield backup
            item = alpm.list_next(item)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def base(self):
        return self._base


class Package(BasePackage):
    def __init__(self, base, aur=None, update=False):
        self._base = base
        self._aur = aur
        self._update = update

    def _map(self, node):
        items = []
        while node is not None:
            items.append(self._match(alpm.list_get_str(node)).groups())
            node = alpm.list_next(node)
        return items

    def __getitem__(self, key):
        if key == 'name':
            return alpm.pkg_get_name(self._base)
        elif key == 'version':
            return alpm.pkg_get_version(self._base)
        elif key == 'description':
            return alpm.pkg_get_desc(self._base)
        elif key == 'state':
            if self._update:
                state = alpm.pkg_check_update(self['name'], self['version'])
            else:
                state = alpm.pkg_get_status(self._base)
            if isinstance(self._aur, AurPackage):
                state |= State.AUR
            return state
        elif key == 'url':
            return alpm.pkg_get_url(self._base)
        elif key == 'pkgurl':
            repository = self['repository']
            if repository in _arch_repos:
                return ARCH_PKG % (repository, self['arch'], self['name'])
        elif key == 'license':
            licenses = alpm.pkg_get_licenses(self._base)
            return alpm.list_join_str(licenses, ', ')
        elif key == 'repository':
            if isinstance(self._aur, AurPackage):
                return 'aur'
            return alpm.pkg_get_repository(self._base)
        elif key == 'groups':
            groups = alpm.pkg_get_groups(self._base)
            return alpm.list_join_str(groups, ' ')
        elif key == 'provides':
            provides = alpm.pkg_get_provides(self._base)
            return alpm.list_join_str(provides, ' ')
        elif key == 'depends':
            depends = []
            node = alpm.pkg_get_depends(self._base)
            while node is not None:
                data = alpm.dep_compute_string(alpm.list_get_dep(node))
                depends.append(self._match(data).groups())
                node = alpm.list_next(node)
            return depends
        elif key == 'optdepends':
            optdepends = []
            node = alpm.pkg_get_optdepends(self._base)
            while node is not None:
                data = alpm.dep_compute_string(alpm.list_get_dep(node))
                optdepends.append(self._match(data).groups())
                node = alpm.list_next(node)
            return optdepends
        elif key == 'conflicts':
            return self._map(alpm.pkg_get_conflicts(self._base))
        elif key == 'replaces':
            replaces = alpm.pkg_get_replaces(self._base)
            return alpm.list_join_str(replaces, ' ')
        elif key == 'required':
            required = self._map(alpm.pkg_compute_requiredby(self._base))
            if isinstance(self._aur, AurPackage):
                required.extend(self._aur[key])
            return required
        elif key == 'optional':
            return self._map(alpm.pkg_compute_optionalfor(self._base))
        elif key == 'validation':
            return alpm.pkg_get_validation(self._base)
        elif key == 'installed':
            return alpm.pkg_get_installdate(self._base)
        elif key == 'download':
            return alpm.pkg_get_size(self._base)
        elif key == 'size':
            return alpm.pkg_get_isize(self._base)
        elif key == 'packager':
            return alpm.pkg_get_packager(self._base)
        elif key == 'arch':
            return alpm.pkg_get_arch(self._base)
        elif key == 'script':
            return alpm.pkg_has_scriptlet(self._base)
        elif key == 'built':
            return alpm.pkg_get_builddate(self._base)
        elif key == 'files':
            return Cache.get_files(self._base)
        elif key == 'backup':
            return self._backup()
        elif key == 'tree':
            return self._tree()
        elif key == 'log':
            return self._log()
        elif key == 'cache':
            return self._cache()
        elif isinstance(self._aur, AurPackage):
            return self._aur.get(key)
        else:
            raise KeyError(key)


class AurPackage(BasePackage):
    def __init__(self, base, update=False):
        self._base = base
        self._update = update

    def _map(self, strings):
        if strings:
            if not isinstance(strings, list):
                strings = [strings]
            return [self._match(string).groups() for string in strings]
        return []

    def _list(self, strings, sep=' '):
        if isinstance(strings, list):
            strings = sep.join(strings)
        return strings

    def _find(self, key, alt):
        value = self._base.get(alt)
        if not value or not value[0]:
            value = self._base.get(key)
        return value

    def __getitem__(self, key):
        if key == 'name':
            name = self._find(key, 'Name')
            if isinstance(name, list):
                return name[0]
            return name
        elif key == 'version':
            return self._find(key, 'Version')
        elif key == 'description':
            return self._find(key, 'Description')
        elif key == 'state':
            state = State.AUR
            if self._update:
                state |= alpm.pkg_check_update(self['name'], self['version'])
            return state
        elif key == 'url':
            return self._find(key, 'URL')
        elif key == 'aururl':
            try:
                return '%s?ID=%d' % (AUR_HTM, int(self._base.get('ID')))
            except (ValueError, TypeError):
                pass
        elif key == 'license':
            license = self._find(key, 'License')
            if isinstance(license, str):
                license = license.split()
            return self._list(license, ', ')
        elif key == 'outdated':
            try:
                return int(self._base.get('OutOfDate'))
            except (ValueError, TypeError):
                pass
        elif key == 'votes':
            try:
                return int(self._base.get('NumVotes'))
            except (ValueError, TypeError):
                pass
        elif key == 'popularity':
            try:
                return float(self._base.get('Popularity'))
            except (ValueError, TypeError):
                pass
        elif key == 'repository':
            return 'aur'
        elif key == 'installed':
            return None
        elif key == 'files':
            return None
        elif key == 'backup':
            return None
        elif key == 'tree':
            return self._tree()
        elif key == 'log':
            return self._log()
        elif key == 'cache':
            return self._cache()
        elif key == 'arch':
            return self._list(self._base.get('arch'), ', ')
        elif key == 'groups':
            return self._list(self._find(key, 'Groups'))
        elif key == 'provides':
            return self._list(self._find(key, 'Provides'))
        elif key == 'depends':
            return self._map(self._find(key, 'Depends'))
        elif key == 'makedepends':
            return self._map(self._find(key, 'MakeDepends'))
        elif key == 'optdepends':
            return self._map(self._find(key, 'OptDepends'))
        elif key == 'conflicts':
            return self._map(self._find(key, 'Conflicts'))
        elif key == 'replaces':
            return self._list(self._find(key, 'Replaces'))
        elif key == 'required':
            return self._map(self._base.get('RequiredBy'))
        elif key == 'submitted':
            try:
                return int(self._base.get('FirstSubmitted'))
            except (ValueError, TypeError):
                pass
        elif key == 'modified':
            try:
                return int(self._base.get('LastModified'))
            except (ValueError, TypeError):
                pass
        elif key == 'maintainer':
            return self._base.get('Maintainer')
        else:
            return self._base[key]


class NullPackage(BasePackage):
    def __init__(self, name):
        self._name = name

    def __getitem__(self, key):
        if key == 'name':
            return self._name
        elif key == 'state':
            return State.Unknown


backend = Backend()
