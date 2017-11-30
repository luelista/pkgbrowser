# Copyright (C) 2010-2017, kachelaqa <kachelaqa@gmail.com>

import os
from datetime import datetime
from email.utils import parsedate
from pkgbrowser.enum import State, Validation, Backup


class Format(object):
    @staticmethod
    def size(size, precision=1):
        if size < 0:
            return ''
        if size < 1024:
            return '%.0f B' % size
        size /= 1024.0
        if size < 1024:
            return '%.*f KiB' % (precision, size)
        size /= 1024
        if size < 1024 or not precision:
            return '%.*f MiB' % (precision, size)
        return '%.*f GiB' % (precision, size / 1024)

    @staticmethod
    def number(number, precision=2, signed=False):
        if signed or number >= 0:
            if isinstance(number, float):
                return '%.*f' % (precision, number)
            return str(number)
        return ''

    @staticmethod
    def date(date, locale=True):
        result = ''
        if isinstance(date, str):
            date = parsedate(date)
        if date:
            try:
                if isinstance(date, (int, float)):
                    date = datetime.fromtimestamp(date)
                else:
                    date = datetime(*date[:6])
            except (ValueError, TypeError):
                pass
            else:
                if date.year >= 2000:
                    if locale:
                        result = date.strftime('%c')
                    else:
                        result = date.strftime('%Y/%m/%d - %H:%M')
        return result

    def _escape(self, string, normalize=False):
        if isinstance(string, bytes):
            string = string.decode('utf-8')
        elif string is None:
            string = ''
        string = string.replace('&', """&amp;"""
                      ).replace('>', """&gt;"""
                      ).replace('<', """&lt;"""
                      ).replace('"', """&quot;"""
                      )
        if normalize:
            string = """&nbsp;""".join(string.split())
        return string

    def symbols(self):
        return {'angle': '+', 'tee': '+', 'line': '-', 'stem': '|'}

    def colours(self):
        return {
            'body-text': 'black',
            'body-back': 'white',
            'table-border': 'grey',
            'label-text': 'black',
            'label-back': 'white',
            'tree-lines': 'grey',
            }

    def information(self, package, page):
        markup = ["""
            <html><head><style type="text/css">
            body {color: %(body-text)s; background-color: %(body-back)s;}
            table.main {background-color: %(table-border)s;}
            p {margin-top: 25; margin-left: 35; margin-right: 10;}
            p.tree {font-family: monospace; color: %(tree-lines)s;}
            p.tree span {font-family: sans serif; color: %(body-text)s;}
            td.key, p.files, p.tree, p.log {white-space: pre;}
            td.key {padding: 4; padding-right: 15; color: %(label-text)s;
                    background-color: %(label-back)s;}
            td.value {white-space: pre-wrap; padding: 4;
                      background-color: %(body-back)s;}
            table.cache td, table.backup td {padding-right: 20;}
            img {float: left;}
            </style></head><body>
            <table class="main" cellspacing="1">
            """ % self.colours()]
        row = """
            <tr><td class="key">%s</td>
            <td class="value" width="100%%">%s</td></tr>
            """
        link = """<a name="%s" href="%s">%s</a>%s"""
        img = """<img src="%s"/>&nbsp;%s"""
        span = """<span>%s</span>"""
        state = package['state']
        text = None
        rows = []
        rows.append(('name', self.tr('Name')))
        if not state & State.Unknown:
            rows.append(('version', self.tr('Version')))
        if page == 'details' and not state & State.Unknown:
            rows.append(('description', self.tr('Description')))
            rows.append(('url', self.tr('Url')))
            if state & State.AUR:
                rows.append(('aururl', self.tr('AUR Url')))
            else:
                rows.append(('pkgurl', self.tr('Package Url')))
            rows.append(('license', self.tr('Licenses')))
            rows.append(('state', self.tr('Status')))
            rows.append(('repository', self.tr('Repository')))
            if state & State.AUR:
                rows.append(('votes', self.tr('Votes')))
                rows.append(('popularity', self.tr('Popularity')))
                rows.append(('outdated', self.tr('Out Of Date')))
            rows.append(('groups', self.tr('Groups')))
            rows.append(('provides', self.tr('Provides')))
            rows.append(('depends', self.tr('Dependencies')))
            if state & State.AUR:
                rows.append(('makedepends', self.tr('Build Requires')))
            rows.append(('optdepends', self.tr('Optional')))
            rows.append(('required', self.tr('Required By')))
            if not state & State.AUR or state & State.Installed:
                rows.append(('optional', self.tr('Optional For')))
            rows.append(('conflicts', self.tr('Conflicts With')))
            rows.append(('replaces', self.tr('Replaces')))
            rows.append(('arch', self.tr('Architecture')))
            if state & State.AUR:
                rows.append(('maintainer', self.tr('Maintainer')))
                rows.append(('submitted', self.tr('First Submitted')))
                rows.append(('modified', self.tr('Last Updated')))
            else:
                rows.append(('packager', self.tr('Maintainer')))
                rows.append(('built', self.tr('Build Date')))
            if state & State.Installed:
                rows.append(('installed', self.tr('Install Date')))
            elif not state & State.AUR:
                rows.append(('download', self.tr('Download Size')))
            if not state & State.AUR or state & State.Installed:
                rows.append(('size', self.tr('Installed Size')))
            if state & State.Installed:
                rows.append(('script', self.tr('Install Script')))
                rows.append(('validation', self.tr('Validation')))
        else:
            if page == 'tree':
                symbols = self.symbols()
                branch = '%%s%(angle)s%(line)s%(line)s%%s' % symbols
                junction = '%%s%(tee)s%(line)s%(line)s%%s' % symbols
                stem = '%(stem)s ' % symbols
                def process(parent, padding=''):
                    output = []
                    if padding:
                        padding += ' '
                    length = len(parent)
                    count = 0
                    for name, provides, state, depends in parent:
                        count += 1
                        if padding or count > 1:
                            output.append(padding + stem)
                        label = link % (page, name, name, '')
                        if provides is not None:
                            label = '%s (%s)' % (provides, label)
                        if not state & State.Installed:
                            label += '&nbsp;*'
                            if state & State.AUR:
                                label += '*'
                        if count == length:
                            output.append(junction % (padding, span % label))
                            output.extend(process(depends, padding + '  '))
                        else:
                            output.append(branch % (padding, span % label))
                            output.extend(process(depends, padding + stem))
                    return output
                tree = package[page]
                if tree is not None:
                    text = '\n'.join(process(tree['packages']))
                    if text:
                        rows.append(('tree:installed', self.tr('Installed')))
                        rows.append(('tree:missing', self.tr('Missing')))
            elif page == 'cache':
                sources = []
                for items in package[page] or ():
                    for item in items:
                        item = os.path.split(self._escape(item))
                        sources.append(
                            """<tr><td>%s</td><td><i>%s</i></td></tr>""" %
                            (item[1], item[0]))
                if sources:
                    text = """<table class="%s">%s</table>""" % (
                            page, ''.join(sources))
            elif page == 'backup':
                backups = package[page]
                if backups is not None:
                    lines = []
                    for state, path in backups:
                        lines.append(
                            """<tr><td><i>%s</i></td><td>%s</td></tr>""" %
                            (self.backup(state), self._escape(path)))
                    if lines:
                        text = """<table class="%s">%s</table>""" % (
                                page, ''.join(lines))
                    else:
                        text = ''
            else:
                text = package[page]
                if text is not None:
                    text = self._escape(text)
            if not text:
                if text is not None:
                    if page == 'tree':
                        text = self.tr('no dependencies')
                    elif page == 'files':
                        text = self.tr('no files')
                    elif page == 'log':
                        text = self.tr('no log entries')
                    elif page == 'backup':
                        text = self.tr('no backup files')
                if not text:
                    text = self.tr('no data')
                text = """<span><i>-- %s --</i></span>""" % text
            text = """<p class="%s">%s</p><div/>""" % (page, text)
        dates = set((
            'installed', 'built', 'submitted', 'modified', 'outdated',
            ))
        numbers = set((
            'votes', 'popularity',
            ))
        flagged = dates.union((
            'name', 'version', 'description', 'packager',
            ))
        permanent = set((
            'depends', 'required', 'license', 'maintainer',
            ))
        urls = set((
            'url', 'pkgurl', 'aururl',
            ))
        for key, title in rows:
            title = self._escape(title, True)
            if key == 'tree:installed':
                if tree['installed']:
                    value = '%s (%d)' % (
                        self.size(tree['isize'], 0), tree['installed'])
                else:
                    value = self.tr('None')
            elif key == 'tree:missing':
                if tree['missing'] or tree['aur']:
                    value = '%s (%d)' % (
                        self.size(tree['msize'], 0), tree['missing'])
                    if tree['aur']:
                        value += ' + (%d AUR)' % tree['aur']
                else:
                    value = self.tr('None')
            else:
                value = package[key]
                if value and isinstance(value, list):
                    items = []
                    for name, data in value:
                        name = self._escape(name)
                        data = self._escape(data, True)
                        items.append(link % (key, name, name, data))
                    value = ' '.join(items)
                elif key == 'state':
                    value = self._escape(self.status(state))
                    icon = self.icon(state)
                    if icon:
                        value = img % (icon, value)
                elif key == 'validation':
                    value = self._escape(self.validation(value))
                else:
                    if not value and key == 'outdated':
                        value = False
                    if isinstance(value, bool):
                        if value:
                            value = self.tr('Yes')
                        else:
                            value = self.tr('No')
                    else:
                        if key == 'size' or key == 'download':
                            value = self.size(value)
                        elif key in numbers:
                            value = self.number(value)
                        elif key in dates:
                            value = self.date(value)
                        if not value:
                            if key in permanent:
                                value = self.tr('None')
                            elif key in flagged:
                                value = self.tr('Unknown')
                            else:
                                continue
                    value = self._escape(value)
                    if key == 'name':
                        value = """<b>%s</b>""" % value
                    elif key in urls:
                        value = link % ('', value, value, '')
            markup.append(row % (title, value))
        markup.append("""</table>%s</body></html>""" % (text or ''))
        return ''.join(markup)

    def statistics(self, data):
        markup = ["""
            <html><head><style type="text/css">
            table {margin-top: 10; margin-bottom: 10; margin-right: 20}
            </style></head><body>
            <div><table width="320">
            """]
        row = """
            <tr><td><b>%s</b></td>
            <td align="right" width="40%%">%s</td>
            <td align="right">%s</td></tr>
            """
        line = """<tr><td colspan="3"><hr></td></tr>"""
        markup.append(row % (
            """<b>%s</b>""" % self._escape(self.tr('Repository')),
            """<b>%s</b>""" % self._escape(self.tr('Count')),
            """<b>%s</b>""" % self._escape(self.tr('Installed Size')),
            ))
        markup.append(line)
        for key, count, size in data:
            if key == 'total':
                key = self._escape(self.tr('Total'))
                markup.append(line)
            markup.append(row % (key, count, self.size(size, 0)))
        markup.append("""</table></div></body></html>""")
        return ''.join(markup)

    def file(self, text, source):
        text = text.strip()
        if source == 'details':
            from string import whitespace
            spaces = whitespace + '\xa0\ufffc'
            lines = text.splitlines()
            for index in range(0, len(lines), 2):
                lines[index] = '%s: ' % lines[index].strip(spaces)
                lines[index + 1] = '%s\n' % lines[index + 1].strip(spaces)
            text = ''.join(lines)
        else:
            header, data = text.partition('\n\n')[::2]
            header = '-'.join(header.splitlines()[1:4:2])
            data = data.strip().splitlines()
            if source == 'cache' or source == 'backup':
                data = self._columns(list(zip(data[::2], data[1::2])))
            text = '%s\n\n  %s\n' % (header, '\n  '.join(data))
        return text

    def _columns(self, lines, spacing=2, indent=0):
        result = []
        indent = ' ' * indent
        widths = [max(len(value) for value in column) + spacing
                  for column in zip(*lines)]
        for line in lines:
            result.append(indent + ''.join(
                '%-*s' % item for item in zip(widths, line)))
        return result

    def list(self, summaries):
        lines = []
        for summary in summaries:
            info = {
                'n': summary.name,
                'v': summary.version,
                'r': summary.repository,
                }
            if summary.state & State.Group:
                format = '%(r)s/%(n)s\n'
            else:
                format = '%(r)s/%(n)s-%(v)s\n'
            lines.append(format % info)
        return ''.join(lines)

    def status(self, state):
        if state & State.Orphan:
            return self.tr('orphan')
        if state & State.Dependency:
            return self.tr('dependency')
        if state & State.Optional:
            return self.tr('optional')
        if state & (State.Explicit | State.Installed):
            return self.tr('installed')
        if state & State.Upgrade:
            return self.tr('upgrade')
        if state & State.Downgrade:
            return self.tr('downgrade')
        return self.tr('non-installed')

    def backup(self, state):
        if state == Backup.Unmodified:
            return self.tr('unmodified')
        if state == Backup.Modified:
            return self.tr('modified')
        if state == Backup.Missing:
            return self.tr('missing')
        if state == Backup.Unreadable:
            return self.tr('unreadable')
        return self.tr('unknown')

    def validation(self, validation):
        string = ''
        if validation:
            if validation & Validation.Nothing:
                string = self.tr('None')
            else:
                if validation & Validation.Signature:
                    string += self.tr('Signature') + ', '
                if validation & Validation.Md5sum:
                    string += self.tr('MD5 Sum') + ', '
                if validation & Validation.Sha256sum:
                    string += self.tr('SHA256 Sum') + ', '
                string = string[:-2]
        if not string:
            string = self.tr('Unknown')
        return string
