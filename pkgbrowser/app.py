# Copyright (C) 2010-2017, kachelaqa <kachelaqa@gmail.com>

import sys, os, getopt
from PyQt5 import QtWidgets
from PyQt5.QtCore import (
    QSettings,
    )
from PyQt5.QtWidgets import (
    QApplication,
    )


QApplication.setApplicationName('PkgBrowser')
QApplication.setApplicationVersion('0.20.1')

QSettings.setPath(QSettings.NativeFormat, QSettings.SystemScope, '/etc')


class Application(QApplication):

    @staticmethod
    def applicationName():
        return QApplication.applicationName().lower()

    @staticmethod
    def applicationTitle():
        return QApplication.applicationName()

    @classmethod
    def applicationUrl(cls, *paths):
        url = 'https://bitbucket.org/kachelaqa/%s' % cls.applicationName()
        if paths:
            url = os.path.join(url, *paths)
        return url

    @classmethod
    def settings(cls):
        organization = application = cls.applicationName()
        return Settings(organization, application)

    @classmethod
    def cacheDirectory(cls):
        settings = cls.settings()
        path = settings.value('options/cache-directory')
        if not path:
            path = os.path.join('/var/cache', cls.applicationName())
        settings.deleteLater()
        return path

    def __init__(self):
        QApplication.__init__(self, sys.argv[:])
        self._window = None

    def window(self):
        if self._window is None:
            from pkgbrowser.window import Window
            self._window = Window()
        return self._window


class Settings(QSettings):

    def value(self, key, default=None, typeinfo=None):
        if default is not None and typeinfo is None:
            if isinstance(default, list):
                typeinfo = 'QStringList'
            else:
                typeinfo = type(default)
        try:
            if typeinfo is None:
                return QSettings.value(self, key, default)
            return QSettings.value(self, key, default, typeinfo)
        except TypeError:
            print('WARNING: config key has an invalid type: %s/%s' % (
                  self.group(), key))
            return default


def usage():
    print(QApplication.translate('usage', """
usage: %s [opts]

options:
 -h  display this help and exit
 -V  display version information
 -u  create/update files cache
""" % Application.applicationName()))

def run():
    keys = 'hVu'
    try:
        options, args = getopt.getopt(sys.argv[1:], keys)
    except getopt.GetoptError as exception:
        print(':: ERROR:', exception)
        usage()
        return 2
    else:
        options = dict(options)
        if '-h' in options:
            usage()
        elif '-V' in options:
            print('%s-%s' % (
                Application.applicationTitle(),
                Application.applicationVersion(),
                ))
        elif '-u' in options:
            from pkgbrowser.conf import update_cache
            return update_cache(Application.cacheDirectory(),
                                Application.applicationTitle())
        elif QApplication.instance() is None:
            app = QtWidgets.qApp = Application()
            app.window().setup()
            app.window().show()
            return app.exec_()
        return 0
