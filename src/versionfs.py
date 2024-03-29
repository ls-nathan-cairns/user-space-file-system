#!/usr/bin/env python

# Nathan Cairns
# ncai762

from __future__ import with_statement

import logging

import os
import sys
import errno
import filecmp
from shutil import copyfile
from glob import glob

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

VERSION_STR = ".versiondir/.versions/%s.%s.%s"

class VersionFS(LoggingMixIn, Operations):
    def __init__(self):
        # get current working directory as place for versions tree
        self.root = os.path.join(os.getcwd(), '.versiondir')
        # check to see if the versions directory already exists
        if os.path.exists(self.root):
            print 'Version directory already exists.'
        else:
            print 'Creating version directory.'
            os.mkdir(self.root)
        self.current_file = None

    # Helpers
    # =======

    def _full_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        path = os.path.join(self.root, partial)
        return path

    def _create_tmp_file(self, full_path):
        # Create tmp file for checking changes
        self.current_file = "%s%s" % (full_path, ".tmp")
        print '** Creating tmp file **'
        copyfile(full_path, self.current_file)

    def _create_new_version(self, tmp_full_path):
        # Make sure .versions dir exists
        versions_path = os.path.join(self.root, '.versions')
        if not os.path.exists(versions_path):
            os.mkdir(versions_path)

        # Get relevant path data
        basename = os.path.basename(tmp_full_path)
        print '** Creating new version **'
        split = basename.split('.')

        # Glob the version files
        search_string = VERSION_STR % (split[0], '.'.join(split[1:len(split)-1]), '*')
        files = glob(search_string)
        files.sort()

        # Ensure list is 5 elements long
        files[len(files):] = [None] * (5 - len(files))

        # Shimmy the versions
        for i, f in reversed(list(enumerate(files))):
            if f is not None:
                if i == 4:
                    os.remove(f)
                else:
                    rename_to = VERSION_STR % (split[0], '.'.join(split[1:len(split) - 1]), i + 3)
                    os.rename(f, rename_to)

        # Save tmp as 2nd newest version
        rename_to = VERSION_STR % (split[0], '.'.join(split[1:len(split) - 1]), 2)
        os.rename(tmp_full_path, rename_to)

    # Filesystem methods
    # ==================

    def access(self, path, mode):
        # print "access:", path, mode
        full_path = self._full_path(path)
        if not os.access(full_path, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        # print "chmod:", path, mode
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        # print "chown:", path, uid, gid
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):
        # print "getattr:", path
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path, fh):
        # print "readdir:", path
        full_path = self._full_path(path)

        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        for r in dirents:
            if r != '.versions':
                yield r

    def readlink(self, path):
        # print "readlink:", path
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        # print "mknod:", path, mode, dev
        return os.mknod(self._full_path(path), mode, dev)

    def rmdir(self, path):
        # print "rmdir:", path
        full_path = self._full_path(path)
        return os.rmdir(full_path)

    def mkdir(self, path, mode):
        # print "mkdir:", path, mode
        return os.mkdir(self._full_path(path), mode)

    def statfs(self, path):
        # print "statfs:", path
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        # print "unlink:", path
        return os.unlink(self._full_path(path))

    def symlink(self, name, target):
        # print "symlink:", name, target
        return os.symlink(target, self._full_path(name))

    def rename(self, old, new):
        # print "rename:", old, new
        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, target, name):
        # print "link:", target, name
        return os.link(self._full_path(name), self._full_path(target))

    def utimens(self, path, times=None):
        # print "utimens:", path, times
        return os.utime(self._full_path(path), times)

    # File methods
    # ============

    def open(self, path, flags):
        print '** open:', path, '**'
        full_path = self._full_path(path)

        # Create tmp file to check changes
        self._create_tmp_file(full_path)

        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        print '** create:', path, '**'
        full_path = self._full_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        print '** read:', path, '**'
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        print '** write:', path, '**'
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        print '** truncate:', path, '**'
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        print '** flush', path, '**'
        return os.fsync(fh)

    def release(self, path, fh):
        print '** release', path, '**'

        # Compare current file with file being released if they are different do versioning
        full_path = self._full_path(path)
        if self.current_file is not None and not filecmp.cmp(full_path, self.current_file, False):
            print '** Files were not equal **'
            self._create_new_version(self.current_file)
            self.current_file = None

        # Delete the tmp file if it exists
        if self.current_file is not None:
            os.remove(self.current_file)
            self.current_file = None
            print '** Deleted tmp file **'

        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        print '** fsync:', path, '**'
        return self.flush(path, fh)


def main(mountpoint):
    FUSE(VersionFS(), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    #logging.basicConfig(level=logging.DEBUG)
    main(sys.argv[1])
