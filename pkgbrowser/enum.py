# Copyright (C) 2010-2017, kachelaqa <kachelaqa@gmail.com>


class State(object):
    from pkgbrowser import alpm
    NonInstalled = alpm.PKG_STATUS_NONINSTALLED
    Installed = alpm.PKG_STATUS_INSTALLED
    Explicit = alpm.PKG_STATUS_EXPLICIT
    Dependency = alpm.PKG_STATUS_DEPENDENCY
    Optional = alpm.PKG_STATUS_OPTIONAL
    Orphan = alpm.PKG_STATUS_ORPHAN
    Foreign = alpm.PKG_STATUS_FOREIGN
    Upgrade = alpm.PKG_STATUS_UPGRADE
    Downgrade = alpm.PKG_STATUS_DOWNGRADE
    Update = Upgrade | Downgrade
    AUR = alpm.PKG_STATUS_MAX
    Group = alpm.PKG_STATUS_MAX << 1
    Category = alpm.PKG_STATUS_MAX << 2
    Unknown = alpm.PKG_STATUS_MAX << 3
    Database = alpm.PKG_STATUS_MAX << 4
    del alpm

class Validation(object):
    from pkgbrowser import alpm
    Unknown = alpm.PKG_VALIDATION_UNKNOWN
    Nothing = alpm.PKG_VALIDATION_NONE
    Md5sum = alpm.PKG_VALIDATION_MD5SUM
    Sha256sum = alpm.PKG_VALIDATION_SHA256SUM
    Signature = alpm.PKG_VALIDATION_SIGNATURE
    del alpm

class Backup(object):
    from pkgbrowser import alpm
    Unknown = alpm.PKG_BACKUP_UNKNOWN
    Unmodified = alpm.PKG_BACKUP_UNMODIFIED
    Modified = alpm.PKG_BACKUP_MODIFIED
    Missing = alpm.PKG_BACKUP_MISSING
    Unreadable = alpm.PKG_BACKUP_UNREADABLE
    del alpm

class Source(object):
    Local = 1
    Sync = 2
    Foreign = 4
    Group = 8
    AUR = 16
