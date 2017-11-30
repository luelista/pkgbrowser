from cpython.pycapsule cimport PyCapsule_New, PyCapsule_GetPointer
from libc.string cimport const_char, memcpy, strcmp, strcpy, strlen, strcasecmp
from libc.stdlib cimport malloc, free
from libc.stdio cimport sprintf, snprintf
from libc.errno cimport errno, EACCES, ENOENT

cdef extern from "ctype.h" nogil:
    int toupper(int ch)

cdef extern from "unistd.h" nogil:
    enum: R_OK
    int access (const_char *, int)

cdef extern from "linux/limits.h":
    cdef int PATH_MAX

cdef extern from "alpm.h":
    ctypedef unsigned int size_t
    ctypedef long int alpm_time_t
    ctypedef long int off_t
    ctypedef enum alpm_errno_t:
        ALPM_ERR_NOT_A_FILE
        ALPM_ERR_NOT_A_DIR
    ctypedef enum alpm_siglevel_t:
        ALPM_SIG_USE_DEFAULT
    ctypedef enum alpm_pkgreason_t:
        ALPM_PKG_REASON_EXPLICIT
        ALPM_PKG_REASON_DEPEND
    ctypedef enum alpm_pkgvalidation_t:
        ALPM_PKG_VALIDATION_UNKNOWN
        ALPM_PKG_VALIDATION_NONE
        ALPM_PKG_VALIDATION_MD5SUM
        ALPM_PKG_VALIDATION_SHA256SUM
        ALPM_PKG_VALIDATION_SIGNATURE
    ctypedef struct alpm_handle_t:
        pass
    ctypedef struct alpm_db_t:
        pass
    ctypedef struct alpm_pkg_t:
        pass
    ctypedef struct alpm_list_t:
        void * data
    ctypedef struct alpm_group_t:
        char * name
        alpm_list_t * packages
    ctypedef struct alpm_depend_t:
        char * name
    ctypedef struct alpm_file_t:
        char * name
    ctypedef struct alpm_filelist_t:
        size_t count
        alpm_file_t * files
    ctypedef struct alpm_backup_t:
        char * name
        char * hash
    alpm_handle_t * alpm_initialize(const_char *, const_char *, alpm_errno_t *)
    int alpm_release(alpm_handle_t *)
    const_char * alpm_version()
    alpm_errno_t alpm_errno(alpm_handle_t *)
    const_char * alpm_strerror(alpm_errno_t)
    char * alpm_compute_md5sum(const char *)
    alpm_list_t * alpm_get_syncdbs(alpm_handle_t *)
    alpm_db_t * alpm_get_localdb(alpm_handle_t *)
    alpm_db_t * alpm_register_syncdb(alpm_handle_t *, const_char *, alpm_siglevel_t)
    alpm_group_t * alpm_db_get_group(alpm_db_t *, const_char *)
    alpm_list_t * alpm_db_get_groupcache(alpm_db_t *)
    alpm_list_t * alpm_db_get_pkgcache(alpm_db_t *)
    alpm_pkg_t * alpm_db_get_pkg(alpm_db_t *, const_char *)
    const_char * alpm_db_get_name(alpm_db_t *)
    int alpm_option_add_cachedir(alpm_handle_t *, const_char *)
    int alpm_option_set_arch(alpm_handle_t *, const_char *)
    int alpm_option_set_logfile(alpm_handle_t *, const_char *)
    const_char * alpm_option_get_root(alpm_handle_t *)
    const_char * alpm_option_get_logfile(alpm_handle_t *)
    alpm_list_t * alpm_option_get_cachedirs(alpm_handle_t *)
    int alpm_option_add_cachedir(alpm_handle_t *, const_char *)
    const_char * alpm_pkg_get_desc(alpm_pkg_t *)
    alpm_list_t * alpm_pkg_get_provides(alpm_pkg_t *)
    alpm_list_t * alpm_pkg_get_conflicts(alpm_pkg_t *)
    alpm_list_t * alpm_pkg_get_groups(alpm_pkg_t *)
    const_char * alpm_pkg_get_url(alpm_pkg_t *)
    alpm_list_t * alpm_pkg_get_licenses(alpm_pkg_t *)
    alpm_list_t * alpm_pkg_get_optdepends(alpm_pkg_t *)
    alpm_list_t * alpm_pkg_get_replaces(alpm_pkg_t *)
    alpm_list_t * alpm_pkg_get_backup(alpm_pkg_t *)
    alpm_filelist_t * alpm_pkg_get_files(alpm_pkg_t *)
    int alpm_pkg_has_scriptlet(alpm_pkg_t *pkg)
    alpm_time_t alpm_pkg_get_installdate(alpm_pkg_t *)
    alpm_pkgreason_t alpm_pkg_get_reason(alpm_pkg_t *)
    off_t alpm_pkg_get_isize(alpm_pkg_t *)
    const_char * alpm_pkg_get_arch(alpm_pkg_t *)
    const_char * alpm_pkg_get_version(alpm_pkg_t *)
    const_char * alpm_pkg_get_packager(alpm_pkg_t *)
    alpm_time_t alpm_pkg_get_builddate(alpm_pkg_t *)
    const_char * alpm_pkg_get_name(alpm_pkg_t *)
    off_t alpm_pkg_get_size(alpm_pkg_t *)
    alpm_list_t * alpm_pkg_get_depends(alpm_pkg_t *)
    alpm_db_t * alpm_pkg_get_db(alpm_pkg_t *)
    alpm_list_t * alpm_pkg_compute_requiredby(alpm_pkg_t *)
    alpm_list_t * alpm_pkg_compute_optionalfor(alpm_pkg_t *)
    alpm_pkgvalidation_t alpm_pkg_get_validation(alpm_pkg_t *)
    int alpm_pkg_vercmp(const_char *, const_char *)
    int alpm_pkg_load(alpm_handle_t *, const_char *, int, alpm_siglevel_t, alpm_pkg_t **)
    char * alpm_dep_compute_string(alpm_depend_t *)
    alpm_list_t * alpm_list_next(alpm_list_t *)
    alpm_list_t * alpm_list_add(alpm_list_t *, void *)
    alpm_list_t * alpm_list_join(alpm_list_t *, alpm_list_t *)
    void alpm_list_free(alpm_list_t *)


cdef enum:
    STATUS_NULL = 0
    STATUS_NONINSTALLED = 1 << 0
    STATUS_INSTALLED = 1 << 1
    STATUS_EXPLICIT = 1 << 2
    STATUS_DEPENDENCY = 1 << 3
    STATUS_OPTIONAL = 1 << 4
    STATUS_ORPHAN = 1 << 5
    STATUS_FOREIGN = 1 << 6
    STATUS_UPGRADE = 1 << 7
    STATUS_DOWNGRADE = 1 << 8
    STATUS_MAX = 1 << 9

cdef enum:
    DATA_TYPE_DEFAULT = 0
    DATA_TYPE_DEPENDS = 1

cdef enum pkg_vcs_t:
    VCS_NULL = 0
    VCS_GIT = 1
    VCS_SVN = 2
    VCS_HG = 3
    VCS_BZR = 4
    VCS_CVS = 5
    VCS_DARCS = 6

cdef enum:
    BACKUP_UNKNOWN = 0
    BACKUP_UNMODIFIED = 1
    BACKUP_MODIFIED = 2
    BACKUP_MISSING = 3
    BACKUP_UNREADABLE = 4

cdef alpm_handle_t *handle = NULL
cdef unicode fs_encoding = u'utf-8'
cdef unicode fs_errors = u'surrogateescape'

cdef bytes to_bytes(object pstr, unicode encoding=u'utf-8', unicode errors=u'strict'):
    if isinstance(pstr, unicode):
        return pstr.encode(encoding, errors)
    elif isinstance(pstr, bytes):
        return pstr
    elif isinstance(pstr, bytearray):
        return bytes(pstr)
    raise ValueError('expected string value, got %s' % type(pstr))

cdef unicode to_unicode(char *cstr, bint release=False,
                        unicode encoding=u'utf-8', unicode errors=u'strict'):
    cdef unicode pstr

    if cstr is not NULL:
        try:
            pstr = cstr.decode(encoding, errors)
            return pstr
        finally:
            if release:
                free(cstr)

cdef alpm_list_t* to_alpm_list(object capsule):
    if capsule is not None:
        return <alpm_list_t *>PyCapsule_GetPointer(capsule, NULL)

cdef alpm_db_t* to_alpm_db(object capsule):
    if capsule is not None:
        return <alpm_db_t *>PyCapsule_GetPointer(capsule, NULL)

cdef alpm_depend_t* to_alpm_dep(object capsule):
    if capsule is not None:
        return <alpm_depend_t *>PyCapsule_GetPointer(capsule, NULL)

cdef alpm_group_t* to_alpm_group(object capsule):
    if capsule is not None:
        return <alpm_group_t *>PyCapsule_GetPointer(capsule, NULL)

cdef alpm_pkg_t* to_alpm_pkg(object capsule):
    if capsule is not None:
        return <alpm_pkg_t *>PyCapsule_GetPointer(capsule, NULL)

cdef object to_capsule(void *ptr):
    if ptr is not NULL:
        return PyCapsule_New(ptr, NULL, NULL)

cdef char* join_list(alpm_list_t *list, const_char *start, const_char *end, int dtype):
    cdef alpm_list_t *node
    cdef char *buffer
    cdef const_char *cstr
    cdef int length = 0, pos = 0
    cdef size_t start_len = strlen(start)
    cdef size_t end_len = strlen(end)
    cdef size_t str_len = 0

    if list is not NULL:
        node = list
        while node is not NULL:
            if dtype == DATA_TYPE_DEPENDS:
                cstr = (<alpm_depend_t *>node.data).name
            else:
                cstr = <const_char *>node.data
            if cstr is not NULL:
                length += start_len + strlen(cstr) + end_len
            node = alpm_list_next(node)
        if length:
            length += 1
            buffer = <char *>malloc(sizeof(char) * length)
            if buffer is not NULL:
                buffer[0] = '\0'
                node = list
                while node is not NULL:
                    if pos and end_len:
                        memcpy(buffer + pos, end, end_len)
                        pos += end_len
                    if start_len:
                        memcpy(buffer + pos, start, start_len)
                        pos += start_len
                    if dtype == DATA_TYPE_DEPENDS:
                        cstr = (<alpm_depend_t *>node.data).name
                    else:
                        cstr = <const_char *>node.data
                    if cstr is not NULL:
                        str_len = strlen(cstr)
                        memcpy(buffer + pos, cstr, str_len + 1)
                        pos += str_len
                        buffer[pos] = '\0'
                    node = alpm_list_next(node)
                return buffer

cdef alpm_list_t* create_dep_list(alpm_list_t *deps):
    cdef alpm_list_t *list = NULL
    cdef alpm_list_t *node

    node = deps
    while node is not NULL:
        list = alpm_list_add(list, alpm_dep_compute_string(<alpm_depend_t *>node.data))
        node = alpm_list_next(node)
    return list

cdef const_char* find_pkg_repository(alpm_pkg_t *pkg):
    cdef alpm_list_t *dbs
    cdef alpm_db_t *db
    cdef const_char *name

    if handle is not NULL and pkg is not NULL:
        if alpm_pkg_get_installdate(pkg):
            name = alpm_pkg_get_name(pkg)
            dbs = alpm_get_syncdbs(handle)
            while dbs is not NULL:
                db = <alpm_db_t *>dbs.data
                if alpm_db_get_pkg(db, name) is not NULL:
                    return alpm_db_get_name(db)
                dbs = alpm_list_next(dbs)
        return alpm_db_get_name(alpm_pkg_get_db(pkg))

cdef alpm_pkg_t* filter_by_func(const_char *target, alpm_list_t *(*func)(alpm_pkg_t *), int local):
    cdef alpm_list_t *dbsnode = NULL
    cdef alpm_list_t *pkgnode
    cdef alpm_list_t *datnode
    cdef alpm_db_t *db
    cdef alpm_pkg_t *pkg
    cdef const_char *candidate

    if handle is not NULL and target is not NULL:
        dbsnode = alpm_list_add(dbsnode, alpm_get_localdb(handle))
        if not local:
            dbsnode = alpm_list_join(dbsnode, alpm_get_syncdbs(handle))
        while dbsnode is not NULL:
            db = <alpm_db_t *>dbsnode.data
            pkgnode = alpm_db_get_pkgcache(db)
            while pkgnode is not NULL:
                pkg = <alpm_pkg_t *>pkgnode.data
                datnode = func(pkg)
                while datnode is not NULL:
                    candidate = (<alpm_depend_t *>datnode.data).name
                    if strcmp(candidate, target) == 0:
                        return pkg
                    datnode = alpm_list_next(datnode)
                pkgnode = alpm_list_next(pkgnode)
            dbsnode = alpm_list_next(dbsnode)

cdef pkg_vcs_t check_vcs(const_char *name):
    cdef const_char **vcs = ['-git', '-svn', '-hg', '-bzr', '-cvs', '-darcs']
    cdef size_t i, vcs_len, name_len

    if name is not NULL:
        name_len = strlen(name)
        for i in range(6):
            vcs_len = strlen(vcs[i])
            if name_len > vcs_len and strcmp(name + name_len - vcs_len, vcs[i]) == 0:
                return <pkg_vcs_t>(i + 1)
    return VCS_NULL

def initialize(object proot, object pdbpath):
    global handle, fs_encoding
    cdef alpm_errno_t err
    cdef bytes root, dbpath

    import sys
    fs_encoding = sys.getfilesystemencoding()
    root = to_bytes(proot, fs_encoding, fs_errors)
    dbpath = to_bytes(pdbpath, fs_encoding, fs_errors)
    handle = alpm_initialize(root, dbpath, &err)
    if handle is NULL:
        return <int>err
    return 0

def release():
    if handle is not NULL:
        return alpm_release(handle)
    return -1

def version():
    return to_unicode(<char *>alpm_version())

def is_initialized():
    return handle is not NULL

ERR_NOT_A_FILE = ALPM_ERR_NOT_A_FILE
ERR_NOT_A_DIR =  ALPM_ERR_NOT_A_DIR

def error_number():
    if handle is not NULL:
        return <int>alpm_errno(handle)
    return 0

def error_string(int err):
    cdef char *cstr
    cdef const_char *strerr = ''

    if err < 0:
        if handle is not NULL:
            strerr = alpm_strerror(alpm_errno(handle))
    else:
        strerr = alpm_strerror(<alpm_errno_t>err)
    cstr = <char *>malloc(sizeof(char) * (strlen(strerr) + 1))
    if cstr is not NULL:
        strcpy(cstr, strerr)
        cstr[0] = toupper(cstr[0])
        return to_unicode(cstr, True)

def get_localdb():
    if handle is not NULL:
        return to_capsule(alpm_get_localdb(handle))

def get_syncdbs():
    if handle is not NULL:
        return to_capsule(alpm_get_syncdbs(handle))

def register_syncdb(object pname):
    cdef bytes name

    if handle is not NULL:
        name = to_bytes(pname)
        return to_capsule(alpm_register_syncdb(handle, name, ALPM_SIG_USE_DEFAULT))

def db_get_name(object pdb):
    cdef alpm_db_t *db

    db = to_alpm_db(pdb)
    if db is not NULL:
        return to_unicode(<char *>alpm_db_get_name(db))

def db_get_pkg(object pdb, object pname):
    cdef alpm_db_t *db
    cdef bytes name

    db = to_alpm_db(pdb)
    if db is not NULL:
        name = to_bytes(pname)
        return to_capsule(alpm_db_get_pkg(db, name))

def db_get_groupcache(object pdb):
    cdef alpm_db_t *db

    db = to_alpm_db(pdb)
    if db is not NULL:
        return to_capsule(alpm_db_get_groupcache(db))

def db_get_pkgcache(object pdb):
    cdef alpm_db_t *db

    db = to_alpm_db(pdb)
    if db is not NULL:
        return to_capsule(alpm_db_get_pkgcache(db))

def db_get_group(object pdb, object pname):
    cdef alpm_db_t *db
    cdef bytes name

    db = to_alpm_db(pdb)
    if db is not NULL:
        name = to_bytes(pname)
        return to_capsule(alpm_db_get_group(db, name))

def db_find_provider(object pname, int local):
    cdef bytes name = to_bytes(pname)

    return to_capsule(filter_by_func(name, alpm_pkg_get_provides, local))

def db_find_replacer(object pname, int local):
    cdef bytes name = to_bytes(pname)

    return to_capsule(filter_by_func(name, alpm_pkg_get_replaces, local))

def option_set_arch(object parch):
    cdef bytes arch

    if handle is not NULL:
        arch = to_bytes(parch)
        return alpm_option_set_arch(handle, arch)
    return -1

def option_get_logfile():
    if handle is not NULL:
        return to_unicode(<char*>alpm_option_get_logfile(handle), False, fs_encoding, fs_errors)

def option_set_logfile(object plogfile):
    cdef bytes logfile = to_bytes(plogfile, fs_encoding, fs_errors)

    if handle is not NULL:
        return alpm_option_set_logfile(handle, logfile)
    return -1

def option_get_cachedirs():
    cdef list cachedirs = []

    if handle is not NULL:
        node = alpm_option_get_cachedirs(handle)
        while node is not NULL:
            cachedirs.append(to_unicode(<char *>node.data, False, fs_encoding, fs_errors))
            node = alpm_list_next(node)
    return cachedirs

def option_add_cachedir(object pcachedir):
    cdef bytes cachedir = to_bytes(pcachedir, fs_encoding, fs_errors)

    if handle is not NULL:
        return alpm_option_add_cachedir(handle, cachedir)
    return -1

def option_get_syncdb(object ptarget):
    cdef alpm_list_t *node
    cdef alpm_db_t *db
    cdef const_char *name
    cdef bytes target

    if handle is not NULL and ptarget is not None:
        target = to_bytes(ptarget)
        node = alpm_get_syncdbs(handle)
        while node is not NULL:
            db = <alpm_db_t *>node.data
            if db is not NULL:
                name = alpm_db_get_name(db)
                if strcmp(name, target) == 0:
                    return to_capsule(db)
            node = alpm_list_next(node)

def group_get_name(object pgroup):
    cdef alpm_group_t *group

    group = to_alpm_group(pgroup)
    if group is not NULL and group.name is not NULL:
        return to_unicode(group.name)

def group_get_pkgs(object pgroup):
    cdef alpm_group_t *group

    group = to_alpm_group(pgroup)
    if group is not NULL and group.packages is not NULL:
        return to_capsule(group.packages)

def dep_compute_string(object pdep):
    cdef alpm_depend_t *dep
    cdef char *cstr

    dep = to_alpm_dep(pdep)
    if dep is not NULL:
        cstr = alpm_dep_compute_string(dep)
        return to_unicode(cstr, True)

def pkg_get_conflicts(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_capsule(create_dep_list(alpm_pkg_get_conflicts(pkg)))

def pkg_get_provides(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_capsule(create_dep_list(alpm_pkg_get_provides(pkg)))

def pkg_get_replaces(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_capsule(create_dep_list(alpm_pkg_get_replaces(pkg)))

def pkg_get_name(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_unicode(<char *>alpm_pkg_get_name(pkg))

def pkg_get_arch(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_unicode(<char *>alpm_pkg_get_arch(pkg))

def pkg_get_desc(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_unicode(<char *>alpm_pkg_get_desc(pkg))

def pkg_get_url(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_unicode(<char *>alpm_pkg_get_url(pkg))

def pkg_get_version(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_unicode(<char *>alpm_pkg_get_version(pkg))

def pkg_get_isize(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return alpm_pkg_get_isize(pkg)

def pkg_get_size(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return alpm_pkg_get_size(pkg)

def pkg_get_builddate(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return alpm_pkg_get_builddate(pkg)

def pkg_get_installdate(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return alpm_pkg_get_installdate(pkg)

def pkg_has_scriptlet(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return bool(alpm_pkg_has_scriptlet(pkg))

def pkg_get_backup(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_capsule(alpm_pkg_get_backup(pkg))

def pkg_compute_requiredby(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_capsule(alpm_pkg_compute_requiredby(pkg))

def pkg_compute_optionalfor(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_capsule(alpm_pkg_compute_optionalfor(pkg))

def pkg_get_depends(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_capsule(alpm_pkg_get_depends(pkg))

def pkg_get_groups(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_capsule(alpm_pkg_get_groups(pkg))

def pkg_get_licenses(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_capsule(alpm_pkg_get_licenses(pkg))

def pkg_get_optdepends(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_capsule(alpm_pkg_get_optdepends(pkg))

PKG_VALIDATION_UNKNOWN = ALPM_PKG_VALIDATION_UNKNOWN
PKG_VALIDATION_NONE = ALPM_PKG_VALIDATION_NONE
PKG_VALIDATION_MD5SUM = ALPM_PKG_VALIDATION_MD5SUM
PKG_VALIDATION_SHA256SUM = ALPM_PKG_VALIDATION_SHA256SUM
PKG_VALIDATION_SIGNATURE = ALPM_PKG_VALIDATION_SIGNATURE

def pkg_get_validation(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return <int>alpm_pkg_get_validation(pkg)

def pkg_vercmp(object pa, object pb):
    cdef bytes a = to_bytes(pa)
    cdef bytes b = to_bytes(pb)

    return alpm_pkg_vercmp(a, b)

def pkg_load(object ppath, int full):
    cdef alpm_pkg_t *pkg = NULL
    cdef bytes path

    if handle != NULL and ppath is not None:
        path = to_bytes(ppath, fs_encoding, fs_errors)
        alpm_pkg_load(handle, path, full, ALPM_SIG_USE_DEFAULT, &pkg)
        return to_capsule(pkg)

def pkg_get_repository(object ppkg):
    cdef alpm_pkg_t *pkg

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        return to_unicode(<char *>find_pkg_repository(pkg))

def pkg_get_fullname(object ppkg):
    cdef alpm_pkg_t *pkg
    cdef char *fullname

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        fullname = <char *>malloc(sizeof(char) * PATH_MAX)
        if fullname is not NULL:
            sprintf(fullname, '%s-%s', alpm_pkg_get_name(pkg), alpm_pkg_get_version(pkg))
            return to_unicode(fullname, True)

def pkg_get_packager(object ppkg):
    cdef alpm_pkg_t *pkg
    cdef const_char *packager

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        packager = alpm_pkg_get_packager(pkg)
        if packager is not NULL:
            if strcasecmp(packager, 'unknown packager') != 0:
                return to_unicode(<char *>packager)

PKG_STATUS_NULL = STATUS_NULL
PKG_STATUS_NONINSTALLED = STATUS_NONINSTALLED
PKG_STATUS_INSTALLED = STATUS_INSTALLED
PKG_STATUS_EXPLICIT = STATUS_EXPLICIT
PKG_STATUS_DEPENDENCY = STATUS_DEPENDENCY
PKG_STATUS_OPTIONAL = STATUS_OPTIONAL
PKG_STATUS_ORPHAN = STATUS_ORPHAN
PKG_STATUS_FOREIGN = STATUS_FOREIGN
PKG_STATUS_UPGRADE = STATUS_UPGRADE
PKG_STATUS_DOWNGRADE = STATUS_DOWNGRADE
PKG_STATUS_MAX = STATUS_MAX

def pkg_get_status(object ppkg):
    cdef int status = STATUS_NULL
    cdef alpm_pkgreason_t reason
    cdef alpm_db_t *db
    cdef alpm_pkg_t *pkg
    cdef alpm_pkg_t *local
    cdef const_char *name

    pkg = to_alpm_pkg(ppkg)
    if handle is not NULL and pkg is not NULL:
        db = alpm_get_localdb(handle)
        if db is not NULL:
            name = alpm_pkg_get_name(pkg)
            local = alpm_db_get_pkg(db, name)
            if local is not NULL:
                status = STATUS_INSTALLED
                if strcmp(find_pkg_repository(pkg), alpm_db_get_name(db)) == 0:
                    status = status | STATUS_FOREIGN
                reason = alpm_pkg_get_reason(local)
                if reason == ALPM_PKG_REASON_EXPLICIT:
                    status = status | STATUS_EXPLICIT
                elif reason == ALPM_PKG_REASON_DEPEND:
                    if alpm_pkg_compute_requiredby(local) is not NULL:
                        status |= STATUS_DEPENDENCY
                    elif alpm_pkg_compute_optionalfor(local) is not NULL:
                        status |= STATUS_OPTIONAL
                    else:
                        status = status | STATUS_ORPHAN
            else:
                status = STATUS_NONINSTALLED
    return status

def pkg_check_update(object pname, object pversion):
    cdef int status = STATUS_NULL
    cdef alpm_db_t *db
    cdef alpm_pkg_t *local
    cdef const_char *current
    cdef bytes name, version

    if handle is not NULL and pname is not None and pversion is not None:
        db = alpm_get_localdb(handle)
        name = to_bytes(pname)
        local = alpm_db_get_pkg(db, name)
        if db is not NULL and local is not NULL:
            current = alpm_pkg_get_version(local)
            version = to_bytes(pversion)
            if current is not NULL and strcmp(current, version) != 0:
                if alpm_pkg_vercmp(current, version) < 0:
                    status = STATUS_UPGRADE | STATUS_NONINSTALLED
                elif check_vcs(name) == VCS_NULL:
                    status = STATUS_DOWNGRADE | STATUS_NONINSTALLED
    return status

PKG_VCS_NULL = VCS_NULL
PKG_VCS_GIT = VCS_GIT
PKG_VCS_SVN = VCS_SVN
PKG_VCS_HG = VCS_HG
PKG_VCS_BZR = VCS_BZR
PKG_VCS_CVS = VCS_CVS
PKG_VCS_DARCS = VCS_DARCS

def pkg_check_vcs(object pname):
    cdef bytes name = to_bytes(pname)

    return check_vcs(name)

def pkg_join_files(object ppkg):
    cdef alpm_pkg_t *pkg
    cdef alpm_filelist_t *files
    cdef const_char *name
    cdef char *cstr
    cdef size_t i, pos = 0, length = 0

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        files = alpm_pkg_get_files(pkg)
        if files is not NULL:
            for i in range(files.count):
                length += strlen(files.files[i].name) + 2
            if length:
                cstr = <char *>malloc(sizeof(char) * (length + 2))
                if cstr is not NULL:
                    cstr[0] = '\0'
                    if files.count:
                        memcpy(cstr + pos, '\n', 1)
                        pos += 1
                        for i in range(files.count):
                            memcpy(cstr + pos, '/', 1)
                            pos += 1
                            name = files.files[i].name
                            length = strlen(name)
                            memcpy(cstr + pos, name, length + 1)
                            pos += length
                            memcpy(cstr + pos, '\n', 1)
                            pos += 1
                            cstr[pos] = '\0'
                    return to_unicode(cstr, True)

def pkg_join_depends(object ppkg):
    cdef alpm_pkg_t *pkg
    cdef char *cstr

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        cstr = join_list(alpm_pkg_get_depends(pkg), '', '\n', DATA_TYPE_DEPENDS)
        return to_unicode(cstr, True)

def pkg_join_provides(object ppkg):
    cdef alpm_pkg_t *pkg
    cdef char *cstr

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        cstr = join_list(alpm_pkg_get_provides(pkg), '', '\n', DATA_TYPE_DEPENDS)
        return to_unicode(cstr, True)

def pkg_join_replaces(object ppkg):
    cdef alpm_pkg_t *pkg
    cdef char *cstr

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        cstr = join_list(alpm_pkg_get_replaces(pkg), '', '\n', DATA_TYPE_DEPENDS)
        return to_unicode(cstr, True)

def pkg_join_optdepends(object ppkg):
    cdef alpm_pkg_t *pkg
    cdef char *cstr

    pkg = to_alpm_pkg(ppkg)
    if pkg is not NULL:
        cstr = join_list(alpm_pkg_get_optdepends(pkg), '', '\n', DATA_TYPE_DEPENDS)
        return to_unicode(cstr, True)

def list_join_str(object plist, object psep):
    cdef alpm_list_t *list
    cdef char *cstr
    cdef bytes sep

    list = to_alpm_list(plist)
    if list is not NULL:
        sep = to_bytes(psep)
        cstr = join_list(list, '', sep, DATA_TYPE_DEFAULT)
        return to_unicode(cstr, True)

def list_next(object plist):
    cdef alpm_list_t *list

    list = to_alpm_list(plist)
    if list is not NULL:
        return to_capsule(alpm_list_next(list))

def list_get_str(object pnode):
    cdef alpm_list_t *node

    node = to_alpm_list(pnode)
    if node is not NULL:
        return to_unicode(<char *>node.data)

def list_get_db(object pnode):
    cdef alpm_list_t *node

    node = to_alpm_list(pnode)
    if node is not NULL:
        return to_capsule(<alpm_db_t *>node.data)

def list_get_group(object pnode):
    cdef alpm_list_t *node

    node = to_alpm_list(pnode)
    if node is not NULL:
        return to_capsule(<alpm_group_t *>node.data)

def list_get_pkg(object pnode):
    cdef alpm_list_t *node

    node = to_alpm_list(pnode)
    if node is not NULL:
        return to_capsule(<alpm_pkg_t *>node.data)

def list_get_dep(object pnode):
    cdef alpm_list_t *node

    node = to_alpm_list(pnode)
    if node is not NULL:
        return to_capsule(<alpm_depend_t *>node.data)

PKG_BACKUP_UNKNOWN = BACKUP_UNKNOWN
PKG_BACKUP_UNMODIFIED = BACKUP_UNMODIFIED
PKG_BACKUP_MODIFIED = BACKUP_MODIFIED
PKG_BACKUP_MISSING = BACKUP_MISSING
PKG_BACKUP_UNREADABLE = BACKUP_UNREADABLE

def list_get_backup(object pnode):
    cdef alpm_list_t *node
    cdef alpm_backup_t *backup
    cdef char *path
    cdef char *md5sum
    cdef int status

    node = to_alpm_list(pnode)
    if node is not NULL:
        backup = <alpm_backup_t *>node.data
        if backup.name is not NULL and backup.hash is not NULL:
            path = <char *>malloc(sizeof(char) * PATH_MAX)
            if path is not NULL:
                status = BACKUP_UNKNOWN
                snprintf(path, PATH_MAX, '%s%s', alpm_option_get_root(handle), backup.name)
                if access(path, R_OK) == 0:
                    md5sum = alpm_compute_md5sum(path)
                    if md5sum is not NULL:
                        if strcmp(md5sum, backup.hash) != 0:
                            status = BACKUP_MODIFIED
                        else:
                            status = BACKUP_UNMODIFIED
                elif errno == EACCES:
                    status = BACKUP_UNREADABLE
                elif errno == ENOENT:
                    status = BACKUP_MISSING
                return (status, to_unicode(path, True, fs_encoding, fs_errors))
