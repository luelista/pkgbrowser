APPNAME    := pkgbrowser
VERSION    := 0.20.1

PYTHON	   := python3
CYTHON	   := $(shell command -v cython || command -v cython2)
PYUIC	   := $(shell command -v pyuic5 || command -v python2-pyuic5)
PYRCC	   := pyrcc5

DESTDIR    :=
PREFIX     := /usr/local
ROOTDIR    := $(DESTDIR)$(PREFIX)
BINDIR     := $(ROOTDIR)/bin
DESKTOPDIR := $(ROOTDIR)/share/applications
ICONDIR    := $(ROOTDIR)/share/icons/hicolor/48x48/apps
APPDIR     := $(ROOTDIR)/lib/$(APPNAME)
APPLIB     := $(APPDIR)/$(APPNAME)

PKGUI      := $(patsubst designer/%.ui,$(APPNAME)/ui/%.py,$(wildcard designer/*.ui))

buildtmp   := build
distdir    := dist
distname   := $(APPNAME)-$(VERSION)
source     := $(distdir)/$(distname)

all:	alpm pyqt scripts compile

cython:
ifneq ($(CYTHON),)
	$(CYTHON) -2 -w src -o alpm.c alpm.pyx
endif

alpm:	cython
	$(PYTHON) src/setup.py build_ext --inplace --build-temp $(buildtmp)
	rm -vrf $(buildtmp)

pyqt:	pyuic pyrcc

pyuic:	$(PKGUI)

$(APPNAME)/ui/%.py: designer/%.ui
	$(PYUIC) --from-imports -o $@ $<

pyrcc:
	$(PYRCC) -o $(APPNAME)/ui/resources_rc.py resources.qrc

scripts:
	@echo -e \
	"#!/bin/sh\n\nexec '$(PYTHON)' '$(APPDIR)/main.py' \"\$$@\"" \
	> $(APPNAME).sh

compile:
	$(PYTHON) -m compileall -ql $(APPNAME) $(APPNAME)/ui

install:
	install -m 755 -d $(BINDIR) $(APPLIB)/{,ui/}__pycache__
	install -m 755 -d $(DESKTOPDIR) $(ICONDIR)
	install -m 644 main.py $(APPDIR)
	install -m 644 $(APPNAME)/*.{py,so} $(APPLIB)
	install -m 644 $(APPNAME)/__pycache__/*.pyc $(APPLIB)/__pycache__
	install -m 644 $(APPNAME)/ui/*.py $(APPLIB)/ui
	install -m 644 $(APPNAME)/ui/__pycache__/*.pyc $(APPLIB)/ui/__pycache__
	install -m 644 $(APPNAME).desktop $(DESKTOPDIR)
	install -m 644 icons/app.png $(ICONDIR)/$(APPNAME).png
	install -m 755 $(APPNAME).sh $(BINDIR)/$(APPNAME)

uninstall:
	rm -vrf $(APPDIR)
	rm -vf $(DESKTOPDIR)/$(APPNAME).desktop
	rm -vf $(ICONDIR)/$(APPNAME).png
	rm -vf $(BINDIR)/$(APPNAME)
	rmdir -p --verbose --ignore-fail-on-non-empty $(DESKTOPDIR) $(ICONDIR)

clean:
	rm -vrf $(buildtmp) $(distdir)
	rm -vf src/alpm.c
	rm -vf $(APPNAME)/alpm*.so
	rm -vf $(APPNAME)/ui/[^_]*.py
	rm -vf $(APPNAME).sh
	find $(APPNAME) -type d -name __pycache__ -print0 | xargs -0 rm -vrf
	find $(APPNAME) -type f -name '*.py[co]' -print0 | xargs -0 rm -vf

dist:	cython
	rm -rf $(distdir)
	mkdir -p $(distdir)
	tar -czf $(source).tar.gz --transform='s|^|$(distname)/|' \
	    designer/*.ui src/{alpm.{c,pyx},setup.py} main.py \
	    $(APPNAME)/*.py $(APPNAME)/ui/_*.py icons/*.png resources.qrc \
	    $(APPNAME).desktop doc/*.html NEWS LICENSE Makefile

.PHONY: all cython alpm pyqt scripts compile install uninstall clean dist
