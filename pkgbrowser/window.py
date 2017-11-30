# Copyright (C) 2010-2017, kachelaqa <kachelaqa@gmail.com>

import sys, time, subprocess
from PyQt5.QtCore import (
    Qt, QObject, QTimer, QEvent, QSignalMapper, QFile, QDir, QUrl,
    QTextStream, QStringListModel,
    )
from PyQt5.QtGui import (
    QInputEvent, QKeySequence, QIcon, QTextCursor, QTextDocument,
    QStandardItemModel, QStandardItem, QFontMetrics, QFont, QPalette,
    )
from PyQt5.QtWidgets import (
    qApp, QMainWindow, QDialog, QMessageBox, QFileDialog, QHBoxLayout,
    QWidget, QProgressBar, QShortcut, QAction, QMenu, QButtonGroup,
    QGroupBox, QToolButton, QRadioButton, QCheckBox, QTextBrowser,
    QTreeWidgetItem, QHeaderView,
    )
from pkgbrowser.backend import (
    backend, DatabaseError, NetworkError, PatternError, Traceback, Cache,
    )
from pkgbrowser.fmt import Format
from pkgbrowser.enum import State
from pkgbrowser.ui.window import Ui_Window
from pkgbrowser.ui.about import Ui_AboutDialog
from pkgbrowser.ui.help import Ui_HelpDialog


def delayed(method):
    def wrapper(*args, **kwargs):
        QTimer.singleShot(5, lambda: method(*args, **kwargs))
    return wrapper


class Window(QMainWindow, Ui_Window):
    def __init__(self):
        QMainWindow.__init__(self)
        self.setupUi(self)
        self._aborting = 0
        self._active = False
        self._help = None
        self._about = None
        self._dialog = None
        self._package = None
        self._history = []
        self._bookmarks = []
        self._index = 0
        self.setWindowTitle(qApp.applicationTitle())
        self.iconPackage = QIcon(':/icons/package.png')
        self.iconGroup = QIcon(':/icons/group.png')
        self.iconRepository = QIcon(':/icons/repository.png')
        self.iconCategory = QIcon(':/icons/category.png')
        self.iconFilter = QIcon(':/icons/filter.png')
        self.iconSearch = QIcon(':/icons/search.png')
        self.iconStop = QIcon(':/icons/stop.png')
        self.iconOrphan = QIcon(':/icons/orphan.png')
        self.iconInstalled = QIcon(':/icons/installed.png')
        self.iconDependency = QIcon(':/icons/dependency.png')
        self.iconOptional = QIcon(':/icons/optional.png')
        self.iconUpgrade = QIcon(':/icons/upgrade.png')
        self.iconDowngrade = QIcon(':/icons/downgrade.png')
        self.format = Formatter(self)
        self.centralWidget().installEventFilter(self)
        self.menuBar().installEventFilter(self)
        self.progress = QProgressBar()
        self.progress.setFixedSize(150, 16)
        self.statusBar().addPermanentWidget(self.progress)
        self.progress.hide()
        model = QStandardItemModel(self.packages)
        self.packages.setModel(model)
        header = self.packages.header()
        header.setSectionsMovable(False)
        header.setSectionsClickable(True)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.handleHeaderMenu)
        for index, (text, numeric, order, hidden) in enumerate((
            (self.tr('Package'), False, Qt.AscendingOrder, False),
            (self.tr('Version'), False, Qt.AscendingOrder, False),
            (self.tr('Repository'), False, Qt.AscendingOrder, False),
            (self.tr('Status'), False, Qt.AscendingOrder, False),
            (self.tr('Date'), True, Qt.DescendingOrder, False),
            (self.tr('Size'), True, Qt.AscendingOrder, False),
            (self.tr('Votes'), True, Qt.DescendingOrder, True),
            (self.tr('Popularity'), True, Qt.DescendingOrder, True),
            )):
            item = QStandardItem(text)
            item.setData(order, Qt.InitialSortOrderRole)
            item.setData(Qt.UserRole if numeric else Qt.DisplayRole)
            model.setHorizontalHeaderItem(index, item)
            if index == 0:
                header.setSortIndicator(index, order)
            header.setSectionHidden(index, hidden)
        self.filters.installEventFilter(self)
        self.filters.viewport().installEventFilter(self)
        corner = QWidget(self.information)
        self.backButton = QToolButton(corner)
        self.backButton.setFocusPolicy(Qt.NoFocus)
        self.backButton.setArrowType(Qt.LeftArrow)
        self.forwardButton = QToolButton(corner)
        self.forwardButton.setFocusPolicy(Qt.NoFocus)
        self.forwardButton.setArrowType(Qt.RightArrow)
        self.bookmarkButton = QToolButton(corner)
        self.bookmarkButton.setFocusPolicy(Qt.NoFocus)
        self.bookmarkButton.setIcon(QIcon(':/icons/bookmark.png'))
        self.bookmarkButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.bookmarkMenu = QMenu(self)
        self.bookmarkMenu.installEventFilter(self)
        self.bookmarkButton.setMenu(self.bookmarkMenu)
        layout = QHBoxLayout(corner)
        layout.setContentsMargins(0, 0, 0, 1)
        layout.setSpacing(0)
        layout.addWidget(self.backButton)
        layout.addWidget(self.forwardButton)
        layout.addWidget(self.bookmarkButton)
        self.information.setCornerWidget(corner)
        self.information.installEventFilter(self)
        self.searchBox.lineEdit().setPlaceholderText(self.tr('Search'))
        self.searchBox.setCompleter(None)
        self.searchBox.view().installEventFilter(self)
        self.searchBox.setModel(QStringListModel(self.searchBox))
        self.searchFiles.setHidden(True)
        self.searchButton.setEnabled(False)
        self.keyGroup.installEventFilter(self)
        self.scopeGroup.installEventFilter(self)
        self.filterButtons = QButtonGroup(self.searchOptions)
        self.filterButtons.addButton(self.scopeAll, 0)
        self.filterButtons.addButton(self.scopeInstalled, 1)
        self.filterButtons.addButton(self.scopeNonInstalled, 2)
        self.typeButtons = QButtonGroup(self.scopeGroup)
        self.typeButtons.addButton(self.scopePackages, 0)
        self.typeButtons.addButton(self.scopeGroups, 1)
        self.otherButtons = QSignalMapper(self.searchOptions)
        for button in (
            self.keyNames, self.keyDescriptions,
            self.keyDepends, self.keyProvides,
            self.keyReplaces, self.keyOptional,
            self.keyMaintainer, self.keyFiles,
            self.scopeAUR,
            ):
            self.otherButtons.setMapping(button, button)
            button.clicked.connect(self.otherButtons.map)
        self.keyNames.setChecked(True)
        self.keyDescriptions.setChecked(True)
        self.scopeAll.setChecked(True)
        self.scopePackages.setChecked(True)
        self.findBar.setVisible(False)
        self.showFindBar = QAction(self.tr('Find...'), self)
        self.addAction(self.showFindBar)
        self.fileRefresh.setShortcut(QKeySequence(self.tr('F5')))
        self.fileCancel.setShortcut(QKeySequence(self.tr('Ctrl+W')))
        self.fileQuit.setShortcut(QKeySequence(self.tr('Ctrl+Q')))
        self.toolsStatistics.setShortcut(QKeySequence(self.tr('Ctrl+S')))
        self.toolsCopy.setShortcut(QKeySequence(self.tr('Ctrl+L')))
        self.helpManual.setShortcut(QKeySequence(self.tr('F1')))
        self.searchButton.setShortcut(QKeySequence(self.tr('F3')))
        self.searchFiles.setShortcut(QKeySequence(self.tr('Ctrl+O')))
        self.backButton.setShortcut(QKeySequence(self.tr('Alt+Left')))
        self.forwardButton.setShortcut(QKeySequence(self.tr('Alt+Right')))
        self.bookmarkButton.setShortcut(QKeySequence(self.tr('Ctrl+B')))
        self.showFindBar.setShortcut(QKeySequence(self.tr('Ctrl+F')))
        shortcut = QShortcut(QKeySequence(self.tr('Escape')),
            self.findBar, self.findBar.hide)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(self.tr('F7')),
            self, self.bookmarkButton.showMenu)
        QShortcut(QKeySequence(self.tr('F9')),
            self, self.filters.setFocus)
        QShortcut(QKeySequence(self.tr('F10')),
            self, self.packages.setFocus)
        QShortcut(QKeySequence(self.tr('F11')),
            self, self.information.setFocus)
        QShortcut(QKeySequence(self.tr('F12')),
            self, self.searchBox.setFocus)
        self.fileOffline.triggered.connect(self.handleWorkOffline)
        self.fileRefresh.triggered.connect(self.handleRefresh)
        self.fileCancel.triggered.connect(self.handleCancelTask)
        self.fileQuit.triggered.connect(self.close)
        self.toolsStatistics.triggered.connect(
            lambda: self.handleStatistics())
        self.toolsCopy.triggered.connect(self.handleCopyList)
        self.toolsClear.triggered.connect(self.handleClearBookmarks)
        self.helpManual.triggered.connect(lambda: self.handleManual())
        self.helpAbout.triggered.connect(lambda: self.handleAbout())
        self.helpAboutQt.triggered.connect(lambda: self.handleAboutQt())
        self.filters.itemSelectionChanged.connect(self.handleFilterActivated)
        self.filters.itemExpanded.connect(self.handleFilterExpanded)
        self.searchBox.editTextChanged.connect(self.handleSearchChanged)
        self.searchFiles.clicked.connect(self.handleFileDialog)
        self.backButton.clicked.connect(self.handleBackButton)
        self.forwardButton.clicked.connect(self.handleForwardButton)
        self.bookmarkButton.clicked.connect(self.handleBookmarkButton)
        self.bookmarkMenu.triggered.connect(self.handleShowBookmark)
        self.bookmarkMenu.aboutToShow.connect(self.handleBookmarkMenu)
        self.filterButtons.buttonClicked.connect(self.updateSearchConditions)
        self.typeButtons.buttonClicked.connect(self.updateSearchConditions)
        self.otherButtons.mapped[QWidget].connect(self.updateSearchConditions)
        self.packages.expanded.connect(self.handleGroupExpanded)
        self.packages.header().sortIndicatorChanged.connect(
            self.handleSortChanged)
        self.packages.selectionModel().selectionChanged.connect(
            self.handlePackageChanged)
        self.packages.doubleClicked.connect(self.handlePackageDoubleClick)
        self.information.currentChanged.connect(self.handleInformationChanged)
        self.details.customContextMenuRequested.connect(
            self.handleContextMenu)
        self.details.anchorClicked.connect(self.handleLinkActivated)
        self.tree.customContextMenuRequested.connect(self.handleContextMenu)
        self.tree.anchorClicked.connect(self.handleLinkActivated)
        self.files.customContextMenuRequested.connect(self.handleContextMenu)
        self.log.customContextMenuRequested.connect(self.handleContextMenu)
        self.cache.customContextMenuRequested.connect(self.handleContextMenu)
        self.backup.customContextMenuRequested.connect(self.handleContextMenu)
        self.showFindBar.triggered.connect(self.handleShowFind)
        self.findEdit.textChanged.connect(self.handleFindChanged)
        self.findNext.clicked.connect(lambda: self.handleFindNext())
        self.findPrevious.clicked.connect(self.handleFindPrevious)
        self.findClose.clicked.connect(self.findBar.hide)
        settings = qApp.settings()
        settings.beginGroup('window')
        geometry = settings.value('geometry', None, 'QByteArray')
        if geometry is not None:
            self.restoreGeometry(geometry)
        state = settings.value('central-splitter', None, 'QByteArray')
        if state is not None:
            self.centralSplitter.restoreState(state)
        state = settings.value('left-splitter', None, 'QByteArray')
        if state is not None:
            self.leftSplitter.restoreState(state)
        state = settings.value('right-splitter', None, 'QByteArray')
        if state is not None:
            self.rightSplitter.restoreState(state)
        settings.endGroup()
        settings.beginGroup('layout')
        for column, flag in enumerate(settings.value('columns', '')):
            self.packages.setColumnHidden(column, column and flag == '0')
        settings.endGroup()
        settings.beginGroup('options')
        if settings.value('work-offline', False):
            self.fileOffline.setChecked(True)
            self.handleWorkOffline(True)
        elif settings.value('include-aur', False):
            self.scopeAUR.setChecked(True)
            self.updateSearchConditions(self.scopeAUR)
        settings.endGroup()
        settings.beginGroup('search')
        strings = settings.value('strings', None, 'QStringList')
        if strings is not None:
            self.searchBox.model().setStringList(
                strings[:self.searchBox.maxCount()])
        settings.endGroup()
        settings.beginGroup('bookmarks')
        names = settings.value('names', None, 'QStringList')
        if names is not None:
            self._bookmarks.extend(names)
        settings.deleteLater()
        sys.excepthook = self.handleExceptions

    def setup(self):
        self.filters.clear()
        self.packages.model().setRowCount(0)
        self.setCurrentPackage(None)
        self.setDisabled(True, True)
        Cache.set_path(qApp.cacheDirectory())
        if self.keyFiles.isChecked():
            self.updateSearchConditions(self.keyFiles)
        self.statusBar().showMessage(
            self.tr('Initializing package data. Please wait...'))
        self.setActive(True, Callback.BackendInitialize)
        backend.initialize()
        self.updateFilters()

    def eventFilter(self, widget, event):
        if event.type() == QEvent.StatusTip and not len(event.tip()):
            return True
        elif (event.type() == QEvent.Shortcut and
              isinstance(widget, QGroupBox)):
            target = None
            for child in widget.children():
                if hasattr(child, 'setFocus'):
                    if target is None:
                        target = child
                    if isinstance(child, QRadioButton) and child.isChecked():
                        target = child
                        break
            if target is not None:
                target.setFocus(Qt.ShortcutFocusReason)
                return True
        elif (event.type() == QEvent.Show and
            widget is self.searchBox.view() and
            not self.searchBox.currentText()):
            view = self.searchBox.view()
            view.setCurrentIndex(view.model().index(0, 0))
        elif (self._active and isinstance(event, QInputEvent) and
             (widget is self.filters or widget is self.filters.viewport())):
            return True
        elif (event.type() == QEvent.MouseButtonPress and
              widget is self.information):
            if event.button() == Qt.XButton1:
                self.handleBackButton()
            elif event.button() == Qt.XButton2:
                self.handleForwardButton()
        elif isinstance(event, Callback):
            items, exception, duration = event.data
            del event.data
            self.setActive(False)
            self.statusBar().clearMessage()
            if event.type() == Callback.BackendInitialize:
                self.setDisabled(False, True)
            elif event.type() == Callback.ListItems:
                self.searchButton.setIcon(self.iconSearch)
                if items is not None:
                    self.filters.clearSelection()
                    self.listItems(items)
                    self.showCount(duration)
            elif items is not None:
                if event.type() == Callback.LoadCategories:
                    self.loadCategories(items)
                elif event.type() == Callback.LoadCategory:
                    self.listItems(items)
            if exception is not None:
                raise exception
            return True
        elif (widget is self.bookmarkMenu and
              event.type() == QEvent.KeyPress and
              event.key() == Qt.Key_Delete):
            action = widget.activeAction()
            if action is not None:
                widget.hide()
                if self.messageBox(self.tr('Delete Bookmark'), self.tr(
                    'Okay to delete bookmark <b>%s</b>?'
                    % action.text()), 'Yes No:', 'Question'):
                    try:
                        self._bookmarks.remove(action.text())
                    except IndexError:
                        pass
        return QMainWindow.eventFilter(self, widget, event)

    def closeEvent(self, event):
        settings = qApp.settings()
        settings.beginGroup('window')
        settings.setValue('geometry', self.saveGeometry())
        settings.setValue(
            'central-splitter', self.centralSplitter.saveState())
        settings.setValue('left-splitter', self.leftSplitter.saveState())
        settings.setValue('right-splitter', self.rightSplitter.saveState())
        settings.endGroup()
        settings.beginGroup('layout')
        settings.setValue(
            'columns', ''.join(str(item[2]) for item in self.columnInfo()))
        settings.endGroup()
        settings.beginGroup('options')
        settings.setValue('work-offline', self.fileOffline.isChecked())
        settings.endGroup()
        settings.beginGroup('search')
        settings.setValue('strings', self.searchBox.model().stringList())
        settings.endGroup()
        settings.beginGroup('bookmarks')
        settings.setValue('names', self._bookmarks)
        settings.deleteLater()
        try:
            backend.release()
        except DatabaseError:
            pass
        event.accept()

    def changeEvent(self, event):
        if event.type() == QEvent.PaletteChange:
            qApp.setOverrideCursor(Qt.BusyCursor)
            self.setCurrentPackage(self.currentPackage())
            self.updateInformation()
            qApp.restoreOverrideCursor()
        QMainWindow.changeEvent(self, event)

    def messageBox(self, title, text, buttons='Ok', icon='Information',
                   details=None, fragment=True):
        dialog = QMessageBox(self)
        dialog.setIcon(getattr(QMessageBox, icon))
        dialog.setWindowTitle('%s - %s' % (title, qApp.applicationTitle()))
        dialog.setTextFormat(Qt.RichText)
        if fragment:
            text = '<body style="white-space: pre">%s</body>' % text
        dialog.setText(text)
        if details:
            dialog.setDetailedText(details)
        for name in buttons.split():
            name, escape, default = (
                name.strip(':'), name.startswith(':'), name.endswith(':'))
            button = getattr(QMessageBox, name)
            dialog.addButton(button)
            if default:
                dialog.setDefaultButton(button)
            if escape:
                dialog.setEscapeButton(button)
        result = None
        if not dialog.exec_() & int(QMessageBox.Cancel | QMessageBox.Close):
            role = dialog.buttonRole(dialog.clickedButton())
            if role == QMessageBox.AcceptRole or role == QMessageBox.YesRole:
                result = True
            elif role == QMessageBox.RejectRole or role == QMessageBox.NoRole:
                result = False
        dialog.deleteLater()
        return result

    def openLink(self, url):
        import webbrowser
        url = QUrl(url)
        try:
            if not url.isValid():
                raise webbrowser.Error(
                    self.tr('The specified URL is invalid.'))
            if not webbrowser.open(url.toString()):
                raise webbrowser.Error(
                    self.tr('Failed to start external browser.'))
        except webbrowser.Error as exception:
            self.messageBox(
                self.tr('Open Url'), self.tr(
                '<br>Could not open url: <br><b>%s</b><br><br>%s<br>'
                % (url.toString(), exception)), 'Ok', 'Warning')

    def processException(self, cls, exception, traceback):
        if isinstance(exception, Traceback):
            print(exception)
            details = str(exception)
        else:
            sys.__excepthook__(cls, exception, traceback)
            details = Traceback.format(cls, exception, traceback)
        return details

    def handleExceptions(self, cls=None, exception=None, traceback=None):
        if not self._aborting:
            while qApp.overrideCursor() is not None:
                qApp.restoreOverrideCursor()
            if isinstance(exception, NetworkError):
                url = QUrl.fromEncoded(
                    bytes(exception.url, 'ascii')).toString()
                if len(url) > 80:
                    url = '%s ...' % url[:80]
                self.messageBox(
                    self.tr('Network Error'), self.tr(
                    '<br>Could not fetch url:<br><b>%s</b><br><br>%s<br>'
                    % (url, exception)), 'Ok', 'Warning')
            elif isinstance(exception, PatternError):
                self.messageBox(self.tr('Search'), self.tr(
                    '<br>Invalid search pattern.<br>'
                    '<br>reason: %s'
                    '<br>source: %s<br>'
                    % (exception, exception.text)), 'Ok', 'Warning')
            elif isinstance(exception, DatabaseError):
                self._aborting = int(self.messageBox(
                    self.tr('Critical Error'), self.tr(
                    '<br>Could not initialise backend:<br><br>%s.<br>'
                    % exception), 'Abort', 'Critical') is False)
            elif not isinstance(exception, KeyboardInterrupt):
                details = self.processException(cls, exception, traceback)
                url = qApp.applicationUrl('issues')
                self._aborting = int(self.messageBox(
                    self.tr('Error'), self.tr(
                    '<br>An unhandled exception occurred.<br>'
                    '<br>Please make a <a href="%s">bug report</a> using '
                    'the details below.<br>'
                    % url), 'Ok Abort', 'Warning', details) is False)
        if self._aborting:
            if self._aborting == 1:
                self._aborting += 1
                self.messageBox(self.tr('Information'), self.tr(
                    '<br>The application will now close down.<br>'
                    ), 'Ok')
                self.close()
            else:
                try:
                    self.processException(cls, exception, traceback)
                except Exception:
                    try:
                        sys.__excepthook__(cls, exception, traceback)
                        sys.__excepthook__(*sys.exc_info())
                    except Exception:
                        print('ERROR: could not process exceptions')
                finally:
                    qApp.quit()

    def handleWorkOffline(self, on):
        backend.set_offline(on)
        if self.scopeAUR.isChecked():
            self.scopeAUR.setChecked(False)
            self.updateSearchConditions(self.scopeAUR)
        self.scopeAUR.setDisabled(
            on or self.keyFiles.isChecked() or
            self.scopeGroups.isChecked())
        self.setCategoriesDisabled(on)

    def handleRefresh(self):
        self.setup()

    @delayed
    def handleStatistics(self):
        self.messageBox(self.tr('Statistics'),
                        self.format.statistics(backend.statistics()),
                        'Ok', 'NoIcon', None, False)

    def summarize(self):
        root = self.packages.model().invisibleRootItem()
        for index in range(root.rowCount()):
            yield root.child(index, 0).data(Qt.UserRole)

    def handleCopyList(self):
        text = self.format.list(self.summarize())
        qApp.clipboard().setText(text)

    @delayed
    def handleManual(self):
        if self._help is None:
            self._help = HelpDialog()
        self._help.show()

    @delayed
    def handleAbout(self):
        if self._about is None:
            self._about = AboutDialog()
        self._about.exec_()

    @delayed
    def handleAboutQt(self):
        QMessageBox.aboutQt(self, qApp.applicationTitle())

    def handleFilterActivated(self):
        selection = self.filters.selectedItems()
        if selection and not self._active:
            self.statusBar().clearMessage()
            state, location = selection[0].data(0, Qt.UserRole)
            if state & State.Group:
                self.listItems(backend.list_groups(location))
            elif state & State.Category:
                if location:
                    self.setActive(True, Callback.LoadCategory)
                    backend.list_category(location)
            else:
                self.listItems(backend.list_packages(state, location))

    def handleFilterExpanded(self, item=None):
        if item is None or item.childCount():
            return
        filters, location = item.data(0, Qt.UserRole)
        if filters & State.Category:
            if not self._active:
                self.statusBar().showMessage(
                    self.tr('Loading categories. Please wait...'))
                self.setCallback(Callback.LoadCategories)
                backend.list_categories()
        else:
            parent = self.addFilter(self.tr('Installed'),
                filters | State.Installed, location, item)
            self.addFilter(self.tr('Explicit'),
                filters | State.Explicit, location, parent)
            self.addFilter(self.tr('Dependency'),
                filters | State.Dependency, location, parent)
            self.addFilter(self.tr('Optional'),
                filters | State.Optional, location, parent)
            self.addFilter(self.tr('Orphan'),
                filters | State.Orphan, location, parent)
            parent.setExpanded(not location)
            self.addFilter(self.tr('Non-Installed'),
                filters | State.NonInstalled, location, item)
            self.addFilter(self.tr('Updates'),
                filters | State.Update, location, item)
            if not filters & State.Foreign:
                self.addFilter(self.tr('Groups'),
                    filters | State.Group, location, item)

    def addFilter(self, title, filters=0, location=None, parent=None):
        if parent is None:
            parent = self.filters
        item = QTreeWidgetItem(parent, [title])
        item.setData(0, Qt.UserRole, (filters, location))
        if parent is self.filters and location is not None:
            item.setIcon(0, self.iconRepository)
            item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        elif filters & State.Category and location is None:
            item.setIcon(0, self.iconCategory)
        else:
            item.setIcon(0, self.iconFilter)
        return item

    def updateFilters(self):
        self.filters.clear()
        item = self.addFilter(self.tr('All'), location='')
        item.setExpanded(True)
        repositories = backend.list_repositories()
        local = repositories.pop()
        for name in repositories:
            self.addFilter(name.title(), location=name)
        self.addFilter(self.tr('Foreign'), State.Foreign, local)
        self.addFilter(self.tr('Categories'), State.Category)
        self.setCategoriesDisabled(self.fileOffline.isChecked())

    def setCategoriesDisabled(self, on):
        categories = self.filters.topLevelItem(
            self.filters.topLevelItemCount() - 1)
        if categories is not None:
            categories.setDisabled(on)
            if on:
                categories.setExpanded(False)
                categories.setChildIndicatorPolicy(
                    QTreeWidgetItem.DontShowIndicator)
            else:
                categories.setChildIndicatorPolicy(
                    QTreeWidgetItem.ShowIndicator)

    def loadCategories(self, categories):
        parent = self.filters.topLevelItem(
            self.filters.topLevelItemCount() - 1)
        if categories and parent is not None:
            for name, items in categories:
                child = self.addFilter(name, State.Category, None, parent)
                for name, target in items:
                    self.addFilter(name, State.Category, target, child)

    def updateSearchKeys(self, button, qualifier=False):
        on = button.isChecked()
        for child in self.keyGroup.findChildren(QCheckBox):
            if child is not button:
                child.setEnabled(not on and not qualifier)
                child.setChecked(False)

    def updateSearchConditions(self, button):
        if button is self.keyFiles:
            on = button.isChecked()
            self.updateSearchKeys(button)
            self.keyNames.setChecked(not on)
            self.keyDescriptions.setChecked(not on)
            self.scopePackages.setChecked(True)
            self.scopeGroups.setEnabled(not on)
            self.scopeAUR.setEnabled(
                not on and not self.fileOffline.isChecked())
            self.scopeAUR.setChecked(False)
            on = on and not Cache.has_files()
            self.scopeAll.setEnabled(not on)
            if on:
                self.scopeInstalled.setChecked(True)
            self.scopeNonInstalled.setEnabled(not on)
        elif self.typeButtons.id(button) >= 0:
            if self.scopeGroups.isEnabled():
                on = self.scopeGroups.isChecked()
                self.updateSearchKeys(self.scopeGroups)
                self.keyNames.setChecked(True)
                self.keyNames.setEnabled(True)
                self.keyDescriptions.setChecked(not on)
                self.scopeAUR.setEnabled(
                    not on and not self.fileOffline.isChecked())
                self.scopeAUR.setChecked(False)
        elif button is self.scopeAUR:
            on = button.isChecked()
            maintainer = self.keyMaintainer.isChecked()
            self.updateSearchKeys(button, maintainer)
            self.keyNames.setChecked(not maintainer)
            self.keyNames.setEnabled(not maintainer)
            self.keyDescriptions.setChecked(not maintainer)
            self.keyDescriptions.setEnabled(not maintainer)
            self.keyMaintainer.setEnabled(True)
            self.keyMaintainer.setChecked(maintainer)
            self.scopePackages.setChecked(on)
            self.scopeGroups.setEnabled(not on and not maintainer)
        elif button is self.keyMaintainer:
            on = button.isChecked()
            aur = self.scopeAUR.isChecked()
            self.updateSearchKeys(button, aur)
            self.keyNames.setChecked(not on)
            self.keyNames.setEnabled(not on)
            self.keyDescriptions.setChecked(not on)
            self.keyDescriptions.setEnabled(not on)
            self.scopePackages.setChecked(on)
            self.scopeGroups.setEnabled(not on)
        self.searchBox.setEnabled(any(
            child.isChecked() for child in self.keyGroup.children()
            if hasattr(child, 'isChecked')
            ))
        self.searchFiles.setVisible(self.keyFiles.isChecked())
        self.handleSearchChanged()

    def handleSearchChanged(self, text=None):
        if text is None:
            text = self.searchBox.currentText()
        self.searchButton.setEnabled(
            bool(self.searchBox.isEnabled() and text))
        qApp.processEvents()

    def handleSearchActivated(self):
        if self._active:
            self.searchButton.setIcon(self.iconSearch)
            self.handleCancelTask()
            return
        text = self.searchBox.currentText()
        if not text:
            return
        self.statusBar().clearMessage()
        index = self.searchBox.findText(text)
        if index > 0:
            self.searchBox.removeItem(index)
        if index != 0:
            self.searchBox.insertItem(0, text)
            count = self.searchBox.count()
            if count > self.searchBox.maxCount():
                self.searchBox.removeItem(count - 1)
        self.searchBox.setCurrentIndex(0)
        filters = State.Installed | State.NonInstalled | State.Update
        if self.scopeInstalled.isChecked():
            filters = State.Installed
        elif self.scopeNonInstalled.isChecked():
            filters = State.NonInstalled | State.Update
        if self.scopeAUR.isChecked():
            filters |= State.AUR
        if self.scopeGroups.isChecked():
            filters |= State.Group
        keys = []
        if self.keyNames.isChecked():
            keys.append('name')
        if self.keyDescriptions.isChecked():
            keys.append('description')
        if self.keyDepends.isChecked():
            keys.append('depends')
        if self.keyProvides.isChecked():
            keys.append('provides')
        if self.keyReplaces.isChecked():
            keys.append('replaces')
        if self.keyOptional.isChecked():
            keys.append('optdepends')
        if self.keyMaintainer.isChecked():
            keys.append('maintainer')
        if self.keyFiles.isChecked():
            keys.append('files')
            filters &= ~State.AUR
        self.searchButton.setIcon(self.iconStop)
        self.setActive(True, Callback.ListItems)
        backend.find(text, filters, keys)

    def handleCancelTask(self):
        self.setActive(False)
        self.statusBar().showMessage(
            self.tr('The current task was cancelled'), 5000)

    def setDisabled(self, disabled, setup=False):
        self.fileOffline.setDisabled(disabled)
        self.fileRefresh.setDisabled(disabled)
        if setup:
            self.toolsStatistics.setDisabled(disabled)
            self.toolsCopy.setDisabled(disabled)
            self.bookmarkMenu.setDisabled(disabled)
            if disabled:
                try:
                    self.searchBox.lineEdit().returnPressed.disconnect(
                        self.handleSearchActivated)
                except TypeError:
                    pass
                try:
                    self.searchButton.clicked.disconnect(
                        self.handleSearchActivated)
                except TypeError:
                    pass
            else:
                self.searchBox.lineEdit().returnPressed.connect(
                    self.handleSearchActivated)
                self.searchButton.clicked.connect(
                    self.handleSearchActivated)

    def setActive(self, activated, identifier=None):
        self._active = activated
        self.setDisabled(activated)
        self.progress.reset()
        self.progress.setValue(0)
        if activated:
            self.progress.setRange(0, 0)
            self.progress.show()
        else:
            self.progress.setRange(0, 1)
            self.progress.hide()
        self.setCallback(identifier)

    def setCallback(self, identifier):
        if identifier is not None:
            start = time.time()
            def callback(items, exception):
                duration = time.time() - start
                qApp.postEvent(self.centralWidget(),
                    Callback(identifier, items, exception, duration))
            backend.set_callback(callback)
        else:
            backend.set_callback(None)

    def handleFileDialog(self):
        path = self.getPath('choose')
        if path is not None:
            self.searchBox.setEditText(path)

    def getPath(self, mode, filename=''):
        dialog = QFileDialog(self)
        dialog.setFilter(dialog.filter() | QDir.Hidden)
        if mode == 'choose':
            dialog.setWindowTitle(dialog.tr('Choose File'))
            dialog.setFileMode(QFileDialog.ExistingFile)
            dialog.setDirectory(QDir.root())
        elif mode == 'saveas':
            dialog.setAcceptMode(QFileDialog.AcceptSave)
            dialog.setFileMode(QFileDialog.AnyFile)
            dialog.setDirectory(QDir.home())
            dialog.selectFile(filename)
        result = None
        if dialog.exec_() == QFileDialog.Accepted:
            files = dialog.selectedFiles()
            if len(files):
                result = files[0]
        dialog.deleteLater()
        return result

    def handleGroupExpanded(self, index):
        item = self.packages.model().itemFromIndex(index)
        if item is not None and item.columnCount() <= 1:
            self.statusBar().clearMessage()
            summary = item.data(Qt.UserRole)
            packages = backend.list_group(summary.repository, summary.name)
            self.listItems(packages, item)

    def handleSortChanged(self, index=0, order=None):
        model = self.packages.model()
        item = model.horizontalHeaderItem(index)
        if order is None:
            order = item.data(Qt.InitialSortOrderRole)
        model.setSortRole(item.data())
        self.packages.sortByColumn(index, order)

    def handleInformationChanged(self, index):
        tab = self.information.widget(index)
        if tab is not None:
            tab.layout().addWidget(self.findBar)
        self.updateInformation(index)

    def handlePackageChanged(self, selected, deselected):
        row = selected.indexes()
        if row:
            item = self.packages.model().itemFromIndex(row[0])
            summary = item.data(Qt.UserRole)
            if not summary.state & State.Group:
                qApp.setOverrideCursor(Qt.BusyCursor)
                self.clearHistory()
                package = backend.get_package(summary)
                self.setCurrentPackage(package)
                self.updateInformation()
                qApp.restoreOverrideCursor()

    def handlePackageDoubleClick(self, index):
        row = self.packages.selectedIndexes()
        if row:
            item = self.packages.model().itemFromIndex(row[0])
            print(item.data(Qt.UserRole))
            #result = subprocess.call(["xterm", "-e", "sudo", "pacman", "-S", item.data(Qt.UserRole).name])
            result = subprocess.call(["xterm", "-e", "yaourt", "-S", item.data(Qt.UserRole).name])
            if result == 0:
                self.handleRefresh()

    def handleExportInformation(self):
        widget = self.informationWidget()
        package = self.currentPackage()
        if widget is not None and package is not None:
            source = widget.objectName()
            name = '%s-%s.%s' % (package['name'], package['version'], source)
            path = self.getPath('saveas', name)
            if path is not None:
                file = QFile(path)
                if file.open(QFile.WriteOnly):
                    stream = QTextStream(file)
                    stream << self.format.file(widget.toPlainText(), source)
                    file.close()
                if file.error() != QFile.NoError:
                    self.messageBox(
                        self.tr('IO Error'), self.tr(
                        '<br>Could not save file:<br><b>%s</b><br><br>%s<br>'
                        % (path, file.errorString())), 'Ok', 'Warning')

    def handleContextMenu(self, pos=None):
        widget = self.informationWidget()
        if widget is not None:
            menu = widget.createStandardContextMenu(pos)
            menu.addSeparator()
            menu.addAction(self.showFindBar)
            menu.addSeparator()
            action = menu.addAction(self.tr('Export...'),
                self.handleExportInformation)
            action.setEnabled(not widget.document().isEmpty())
            action = menu.addAction(self.tr('Send To List'))
            targets = self.findTargets(widget, pos)
            if targets:
                action.triggered.connect(
                    lambda: self.handleSendToList(targets))
            else:
                action.setEnabled(False)
            menu.exec_(widget.viewport().mapToGlobal(pos))
            menu.deleteLater()

    def findTargets(self, browser, pos):
        targets = []
        if pos is not None:
            def find_targets(block):
                iterator = block.begin()
                while not iterator.atEnd():
                    fragment = iterator.fragment()
                    if fragment is not None:
                        format = fragment.charFormat()
                        if format.isAnchor():
                            target = format.anchorHref()
                            if target and len(format.anchorNames()):
                                yield target
                    iterator += 1
            page = browser.objectName()
            cursor = browser.cursorForPosition(pos)
            if page == 'tree':
                position = cursor.position()
                cursor.movePosition(QTextCursor.Start)
                while not cursor.atEnd():
                    table = cursor.currentTable()
                    if table is None:
                        cursor.movePosition(QTextCursor.NextBlock)
                    else:
                        cursor = table.lastCursorPosition()
                        cursor.movePosition(QTextCursor.NextBlock)
                        if position > cursor.position():
                            block = cursor.block()
                            while block.isValid():
                                targets.extend(find_targets(block))
                                block = block.next()
                        break
            elif page == 'details':
                table = cursor.currentTable()
                if table and table.cellAt(cursor).column() == 1:
                    targets.extend(find_targets(cursor.block()))
        return targets

    def handleSendToList(self, targets):
        self.setActive(True, Callback.ListItems)
        backend.list_targets(targets)

    def handleShowFind(self):
        self.findBar.show()
        self.findEdit.setFocus()

    def handleFindChanged(self, text):
        self.findNext.setEnabled(bool(text))
        self.findPrevious.setEnabled(bool(text))
        self.handleFindNext(text, True)

    def handleFindNext(self, text=None, incremental=False, backwards=False):
        widget = self.informationWidget()
        if widget is not None:
            if text is None:
                text = self.findEdit.text()
            position = 0
            found = False
            cursor = widget.textCursor()
            if text:
                flags = QTextDocument.FindFlags(0)
                if backwards:
                    flags |= QTextDocument.FindBackward
                if self.findCase.isChecked():
                    flags |= QTextDocument.FindCaseSensitively
                position = cursor.selectionStart()
                if incremental:
                    cursor.setPosition(position)
                    widget.setTextCursor(cursor)
                found = widget.find(text, flags)
                if not found:
                    if backwards:
                        cursor.movePosition(QTextCursor.End)
                    else:
                        cursor.movePosition(QTextCursor.Start)
                    widget.setTextCursor(cursor)
                    found = widget.find(text, flags)
            if not found:
                cursor.setPosition(position)
                widget.setTextCursor(cursor)
            if not found and text:
                self.findEdit.setStyleSheet(
                    'color: white; background-color: lightcoral')
            else:
                self.findEdit.setStyleSheet('')

    def handleFindPrevious(self):
        self.handleFindNext(backwards=True)

    def handleLinkActivated(self, url):
        self.navigate(url, False)

    def navigate(self, url, rebase):
        widget = self.informationWidget()
        if widget is not None:
            widget.clearFocus()
            widget.setFocus()
        if url.host():
            self.openLink(url)
        else:
            if rebase:
                self.clearHistory()
            self.setCurrentPackage(backend.get_package(url.toString()))
            self.packages.clearSelection()
            self.updateInformation()

    def clearHistory(self):
        del self._history[:]
        self._index = 0

    def updateHistory(self, name):
        if name:
            if not self._history or name != self._history[self._index]:
                del self._history[self._index + 1:]
                self._history.append(name)
                self._index = len(self._history) - 1
        else:
            self.clearHistory()
        self.backButton.setDisabled(self._index < 1)
        self.forwardButton.setDisabled(
            self._index >= len(self._history) - 1)

    def navigateHistory(self, back):
        self._index += (1 - 2 * bool(back))
        self.navigate(QUrl(self._history[self._index]), False)

    def handleBackButton(self):
        if self._index > 0:
            self.navigateHistory(True)

    def handleForwardButton(self):
        if self._index < len(self._history) - 1:
            self.navigateHistory(False)

    def handleBookmarkButton(self):
        package = self.currentPackage()
        if package is not None:
            name = package['name']
            try:
                index = self._bookmarks.index(name)
            except ValueError:
                index = -1
            else:
                if index:
                    del self._bookmarks[index]
            if index:
                self._bookmarks.insert(0, name)
                if len(self._bookmarks) > 16:
                    del self._bookmarks[-1]

    def handleShowBookmark(self, action=None):
        if action is not None:
            self.navigate(QUrl(action.text()), True)

    def handleBookmarkMenu(self):
        self.bookmarkMenu.clear()
        for bookmark in sorted(self._bookmarks):
            self.bookmarkMenu.addAction(bookmark)

    def handleClearBookmarks(self):
        self.bookmarkMenu.clear()
        del self._bookmarks[:]

    def currentPackage(self):
        return self._package

    def setCurrentPackage(self, package):
        self._package = package
        for index in range(self.information.count()):
            widget = self.information.widget(index).findChild(QTextBrowser)
            widget.clear()
            self.information.setTabEnabled(index,
                package is not None or widget.objectName() == 'details')
        self.updateHistory(package and package['name'])
        self.bookmarkButton.setEnabled(bool(package or self._bookmarks))

    def informationWidget(self, index=None):
        if index is None:
            index = self.information.currentIndex()
        tab = self.information.widget(index)
        if tab is not None and self.information.isTabEnabled(index):
            return tab.findChild(QTextBrowser)

    def updateInformation(self, index=None):
        widget = self.informationWidget(index)
        package = self.currentPackage()
        if (package is not None and widget is not None and
            widget.document().isEmpty()):
            qApp.setOverrideCursor(Qt.BusyCursor)
            widget.setHtml(
                self.format.information(package, widget.objectName()))
            qApp.restoreOverrideCursor()

    def iconFromState(self, state):
        if state & State.Orphan:
            return self.iconOrphan
        if state & State.Dependency:
            return self.iconDependency
        if state & State.Optional:
            return self.iconOptional
        if state & (State.Explicit | State.Installed):
            return self.iconInstalled
        if state & State.Upgrade:
            return self.iconUpgrade
        if state & State.Downgrade:
            return self.iconDowngrade
        return QIcon()

    def listItems(self, items, parent=None):
        if parent is None:
            parent = self.packages.model().invisibleRootItem()
        parent.setRowCount(0)
        disabled = self.packages.palette().color(
            QPalette.Disabled, QPalette.WindowText)
        for item in items:
            status = self.iconFromState(item.state)
            row = (
                QStandardItem(item.name),
                QStandardItem(item.version),
                QStandardItem(item.repository),
                QStandardItem(status, self.format.status(item.state, False)),
                QStandardItem(self.format.date(item.date, False)),
                QStandardItem(self.format.size(item.size)),
                QStandardItem(self.format.number(item.votes)),
                QStandardItem(self.format.number(item.popularity)),
                )
            row[0].setData(item, Qt.UserRole)
            row[4].setData(item.date, Qt.UserRole)
            row[5].setData(item.size, Qt.UserRole)
            row[6].setData(item.votes, Qt.UserRole)
            row[7].setData(item.popularity, Qt.UserRole)
            if item.state & State.NonInstalled:
                row[5].setForeground(disabled)
            if item.state & State.Group:
                row[0].appendRow(QStandardItem())
                row[0].setIcon(self.iconGroup)
            else:
                row[0].setIcon(self.iconPackage)
            parent.appendRow(row)
        if not parent.index().isValid():
            self.packages.scrollToTop()
        self.handleSortChanged()
        self.showCount()

    def showCount(self, duration=None):
        count = self.packages.model().invisibleRootItem().rowCount()
        if count == 0:
            message = self.tr('Found no matching items')
        elif count == 1:
            message = self.tr('Found 1 matching item')
        else:
            message = self.tr('Found %d matching items' % count)
        if duration is not None:
            message = self.tr('%s (%.3g seconds)' % (message, duration))
        self.statusBar().showMessage(message, 15000)

    def columnInfo(self):
        model = self.packages.model()
        for column in range(model.columnCount()):
            yield (column, model.horizontalHeaderItem(column).text(),
                   int(not self.packages.isColumnHidden(column)))

    def handleHeaderMenu(self, pos):
        menu = QMenu()
        for column, text, shown in self.columnInfo():
            action = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(shown)
            action.setEnabled(bool(column))
            action.setData(column)
        action = menu.exec_(self.packages.mapToGlobal(pos))
        if action is not None:
            self.packages.setColumnHidden(
                action.data(), not action.isChecked())


class Formatter(Format, QObject):
    def __init__(self, parent=None):
        Format.__init__(self)
        QObject.__init__(self, parent)

    def colours(self):
        return {
            'body-text': 'palette(text)',
            'body-back': 'palette(base)',
            'table-border': 'palette(mid)',
            'label-text': 'palette(window-text)',
            'label-back': 'palette(window)',
            'tree-lines': qApp.palette().color(
                QPalette.Disabled, QPalette.Text).name(),
            }

    def symbols(self):
        metrics = QFontMetrics(QFont('monospace'))
        symbols = {'angle': '\u251C', 'tee': '\u2570',
                   'line': '\u2500', 'stem': '\u2502'}
        for symbol in symbols.values():
            if not metrics.inFontUcs4(ord(symbol)):
                break
        else:
            return symbols
        return Format.symbols(self)

    def status(self, state, strict=True):
        if strict or state & (State.Installed | State.Update):
            return Format.status(self, state)
        return ''

    def icon(self, state):
        if state & State.Orphan:
            return ':/icons/orphan.png'
        if state & State.Dependency:
            return ':/icons/dependency.png'
        if state & State.Optional:
            return ':/icons/optional.png'
        if state & (State.Explicit | State.Installed):
            return ':/icons/installed.png'
        if state & State.Upgrade:
            return ':/icons/upgrade.png'
        if state & State.Downgrade:
            return ':/icons/downgrade.png'
        return ''


class Callback(QEvent):
    ListItems = QEvent.registerEventType()
    LoadCategories = QEvent.registerEventType()
    LoadCategory = QEvent.registerEventType()
    BackendInitialize = QEvent.registerEventType()

    def __init__(self, *args):
        QEvent.__init__(self, args[0])
        self.data = args[1:]


class AboutDialog(QDialog, Ui_AboutDialog):
    def __init__(self):
        QDialog.__init__(self, qApp.window())
        self.setupUi(self)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        from sys import version as py_version
        from PyQt5.QtCore import qVersion, PYQT_VERSION_STR
        url = qApp.applicationUrl()
        title = qApp.applicationTitle()
        self.setWindowTitle('About - %s' % title)
        self.title.setText(
            """<h2>%s %s</h2>""" % (title, qApp.applicationVersion())
            )
        self.details.setText(self.tr("""
            <div align="center">
            <p>A utility for browsing pacman databases and the AUR</p>
            <p>Copyright &copy; 2010-2017, kachelaqa<br>
            &lt;kachelaqa@gmail.com&gt;</p>
            <p><a href="%s">%s</a></p>
            <p>Using:<br>Qt %s<br>Python %s<br>PyQt %s<br>libalpm %s</p>
            </div>
            """
            % (url, url, qVersion(), py_version.split()[0],
               PYQT_VERSION_STR, backend.version())
            ))
        self.information.currentChanged.connect(self.handleInformationChanged)
        self.details.linkActivated.connect(qApp.window().openLink)

    def handleInformationChanged(self, index):
        tab = self.information.widget(index)
        if tab is self.licenseTab:
            if self.license.document().isEmpty():
                stream = QFile(':/LICENSE')
                if stream.open(QFile.ReadOnly):
                    self.license.setPlainText(str(stream.readAll(), 'utf-8'))
                    stream.close()


class HelpDialog(QDialog, Ui_HelpDialog):
    def __init__(self):
        QDialog.__init__(self, qApp.window())
        self.setupUi(self)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowTitle('Manual - %s' % qApp.applicationTitle())
        stream = QFile(':/doc/manual.html')
        if stream.open(QFile.ReadOnly):
            self.browser.setHtml(str(stream.readAll(), 'utf-8'))
            stream.close()
        self.browser.anchorClicked.connect(qApp.window().openLink)
