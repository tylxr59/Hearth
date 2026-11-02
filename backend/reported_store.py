"""Atomic owner-only reported-state custody. Never stores command intent."""

import os
import secrets
import stat
from pathlib import Path

from backend.reported_cache import LIMIT, decode, encode
from backend.validation import Invalid

NAME = "reported-state.json"


def directory(path):
    path = Path(path).absolute()
    if path.resolve() != path:
        raise Invalid("literal private reported-state directory required")
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        s = os.fstat(fd)
        if s.st_uid != os.getuid() or s.st_mode & 0o077:
            raise Invalid("owner-only reported-state directory required")
        return fd
    except BaseException:
        os.close(fd)
        raise


def checked_name(name):
    if name not in (NAME, "local-pairing.json"):
        raise Invalid("fixed private document name required")
    return name


def read_fd(root, name=NAME, decoder=decode):
    try:
        fd = os.open(
            checked_name(name),
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=root,
        )
    except FileNotFoundError:
        return None
    try:
        s = os.fstat(fd)
        if (
            not stat.S_ISREG(s.st_mode)
            or s.st_uid != os.getuid()
            or s.st_mode & 0o777 != 0o600
            or s.st_nlink != 1
            or s.st_size > LIMIT
        ):
            raise Invalid("private bounded reported-state file required")
        with os.fdopen(os.dup(fd), "rb") as stream:
            raw = stream.read(LIMIT + 1)
        return decoder(raw)
    finally:
        os.close(fd)


def load(path, name=NAME, decoder=decode):
    root = directory(path)
    try:
        return read_fd(root, name, decoder)
    finally:
        os.close(root)


def save(path, data, name=NAME, encoder=encode, decoder=decode):
    checked_name(name)
    raw = encoder(data)
    root = directory(path)
    temporary = ".reported-" + secrets.token_hex(16) + ".new"
    created = False
    try:
        read_fd(root, name, decoder)  # Refuse an unexpected existing inode; don't follow/repair it.
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=root,
        )
        created = True
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=root, dst_dir_fd=root)
        created = False
        os.fsync(root)
        if read_fd(root, name, decoder) != decoder(raw):
            raise Invalid("reported-state custody readback failed")
    finally:
        if created:
            os.unlink(temporary, dir_fd=root)
        os.close(root)
