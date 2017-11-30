# Copyright (C) 2010-2017, kachelaqa <kachelaqa@gmail.com>

import os, re, glob, time, signal
import urllib.request
from email.utils import parsedate
from tarfile import TarFile, TarError
from zipfile import ZipFile, BadZipfile, ZIP_DEFLATED
from tempfile import TemporaryFile
from collections import defaultdict
from io import BytesIO
from multiprocessing import Pool, TimeoutError
from pkgbrowser import utils


PM_ROOT_DIR = '/'
PM_DB_PATH = '/var/lib/pacman'
PM_CONF_FILE = '/etc/pacman.conf'
PM_LOG_FILE = '/var/log/pacman.log'
PM_CACHE_DIRS = ('/var/cache/pacman/pkg',)

match_pkgfile = re.compile(r"""
    ^(.+)-([^-\s]+-[^-\s]+)-(i686|x86_64|any)
    \.pkg\.tar(?:\.(?:gz|bz2|xz|Z))?$
    """, re.X).match


def read_config(path=PM_CONF_FILE, section=None, config=None):
    if config is None:
        config = {
            'Repositories': [],
            'Servers': defaultdict(list),
            'SigLevels': defaultdict(list),
            }
    repeating = set((
        'CacheDir', 'CleanMethod', 'HoldPkg', 'IgnoreGroup',
        'IgnorePkg', 'NoExtract', 'NoUpgrade', 'SigLevel',
        'LocalFileSigLevel', 'RemoteFileSigLevel',
        ))
    with open(path, 'r') as stream:
        for line in stream:
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            if line[0] == '[' and line[-1] == ']':
                section = line[1:-1]
                continue
            if not section:
                continue
            key, sep, value = line.partition('=')
            key = key.rstrip()
            value = value.lstrip()
            if not key:
                continue
            if key == 'Include':
                for path in glob.glob(value):
                    read_config(path, section, config)
            elif section == 'options':
                if value:
                    if key == 'Architecture':
                        if key in config:
                            continue
                        if value == 'auto':
                            value = os.uname()[4]
                    elif key in repeating:
                        if key == 'CacheDir':
                            value = [value]
                        else:
                            value = value.split()
                        if key in config:
                            config[key].extend(value)
                            continue
                else:
                    value = True
                config[key] = value
            elif key == 'Server':
                server = value.replace('$repo', section)
                arch = config.get('Architecture')
                if arch:
                    server = server.replace('$arch', arch)
                config['Servers'][section].append(server)
                if section not in config['Repositories']:
                    config['Repositories'].append(section)
            elif key == 'SigLevel':
                config['SigLevels'][section].extend(value.split())
    return config

def load_logfile(path=PM_LOG_FILE):
    log = defaultdict(list)
    pattern = re.compile(r"""
        ^(\[[^]]+\])\ +(?:\[[^]]+\]\ +)?
        (installed|upgraded|downgraded|removed)\ +(\S+)\ +(\(.+)
        """, re.X | re.S)
    with open(path, 'r') as stream:
        for line in stream:
            match = pattern.match(line)
            if match is not None:
                log[match.group(3)].append(' '.join(match.groups()))
    temp = TemporaryFile()
    with ZipFile(temp, 'w') as zip:
        for name, lines in log.items():
            zip.writestr(name, ''.join(lines).encode('utf-8'))
    return ZipFile(temp)

def load_pkgcache(caches=PM_CACHE_DIRS):
    packages = defaultdict(list)
    for cache in sorted(caches):
        try:
            filenames = os.listdir(cache)
        except OSError:
            pass
        else:
            for filename in filenames:
                match = match_pkgfile(filename)
                if match is not None:
                    path = os.path.join(cache, filename)
                    if os.path.isfile(path):
                        packages['%s/%s' % match.group(1, 3)].append(path)
    temp = TemporaryFile()
    with ZipFile(temp, 'w') as zip:
        for path, filenames in packages.items():
            zip.writestr(path, '\n'.join(filenames).encode('utf-8'))
    return ZipFile(temp)

def load_srcinfo(pkgname, data):
    if isinstance(data, bytes):
        data = data.decode('utf-8', 'replace')
    keys = {
        'name': True,
        'version': False,
        'description': False,
        'url': False,
        'license': True,
        'groups': True,
        'arch': True,
        'conflicts': True,
        'depends': True,
        'makedepends': True,
        'optdepends': True,
        'provides': True,
        'replaces': True,
        }
    pkgbase = {}
    srcinfo = {}
    info = None
    for line in data.splitlines():
        key, sep, value = [part.strip() for part in line.partition('=')]
        if line.startswith('\t'):
            if info is not None and key in keys:
                if keys[key]:
                    if key in info:
                        info[key].append(value)
                    else:
                        info[key] = [value]
                else:
                    info[key] = value
        elif key == 'pkgbase':
            pkgbase.clear()
            info = pkgbase
        elif key == 'pkgname' and value == pkgname:
            info = srcinfo
    srcinfo.update(pkgbase)
    return srcinfo

def _process_archive(args):
    path, root, urls, comment = args
    archive = None
    timestamp = 0
    try:
        zip = ZipFile(path)
        try:
            if zip.comment == comment:
                timestamp = os.path.getmtime(path)
        finally:
            zip.close()
    except (EnvironmentError, BadZipfile):
        pass
    for url in urls:
        url = utils.make_url(url)
        try:
            response = urllib.request.urlopen(url, timeout=30)
            current = parsedate(response.info().get('last-modified'))
            if current is not None:
                current = time.mktime(current)
            try:
                if current is None or current > timestamp:
                    archive = BytesIO(response.read())
                else:
                    print(':: already up to date: [%s.files]' % root)
                    return True
            finally:
                response.close()
        except IOError:
            pass
        else:
            print(':: download succeeded: [%s.files] (%s)' % (root, url))
            break
    if archive is not None:
        try:
            with ZipFile(path, 'w', ZIP_DEFLATED) as zip:
                print(':: converting archive: [%s.files] ...' % root)
                with TarFile.open(fileobj=archive) as tar:
                    for info in tar:
                        if info.isfile() and info.name.endswith('/files'):
                            state = 0
                            lines = [b'']
                            stream = tar.extractfile(info)
                            for line in stream:
                                if line.isspace():
                                    state = 0
                                elif state == 1:
                                    lines.append(line)
                                elif state == 2:
                                    continue
                                elif line.startswith(b'%FILES%'):
                                    state = 1
                                elif line.startswith(b'%BACKUP%'):
                                    state = 2
                            lines = b'/'.join(sorted(lines))
                            if len(lines) > 1:
                                lines = b'\n' + lines
                            zip.writestr(info.name.split('/')[0], lines)
                            stream.close()
                zip.comment = comment
                archive.close()
            return True
        except (EnvironmentError, TarError, UnicodeError) as exception:
            print(':: ERROR: failed to convert archive: '
                  '[%s.files]' % root)
            print('::  ', exception)
            try:
                os.remove(path)
            except OSError:
                pass
    else:
        print(':: ERROR: could not find a valid mirror: '
              '[%s.files]' % root)
    return False

def update_cache(root, comment=''):
    try:
        pool = None
        try:
            config = read_config()
        except IOError as exception:
            print(':: ERROR: could not read pacman config:')
            print('::  ', exception)
        else:
            if not os.path.exists(root):
                print(':: creating cache directory:', root)
                try:
                    os.makedirs(root)
                except OSError as exception:
                    print(':: ERROR: could not create cache directory:')
                    print('::  ', exception)
                    return 1
            args = []
            if not isinstance(comment, bytes):
                comment = comment.encode('utf-8')
            for name in config['Repositories']:
                mirrors = config['Servers'].get(name, [])
                urls = [os.path.join(mirror, '%s.files.tar.gz' % name)
                        for mirror in mirrors]
                path = os.path.join(root, '%s.files.zip' % name)
                args.append((path, name, urls, comment))
            if args:
                def initializer():
                    signal.signal(signal.SIGINT, signal.SIG_IGN)
                pool = Pool(initializer=initializer)
                start = time.time()
                if all(pool.map_async(_process_archive, args).get(1000)):
                    seconds = time.time() - start
                    print(':: update completed in %.1f seconds' % seconds)
                    return 0
            else:
                print(':: ERROR: could not find repositories/mirrors')
    except (KeyboardInterrupt, TimeoutError):
        print(':: update aborted')
        if pool is not None:
            pool.terminate()
            pool.join()
    return 1
