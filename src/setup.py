from distutils.core import setup, Extension


setup(ext_modules=[Extension(
    'pkgbrowser.alpm',
    libraries=['alpm'],
    sources=['src/alpm.c'],
    )])
