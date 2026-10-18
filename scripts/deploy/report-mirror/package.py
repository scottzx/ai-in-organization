#!/usr/bin/env python3
"""Package changed static files plus a complete manifest; standard library only."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import tarfile
import tempfile


FILE_MANIFEST = '.report-files.json'
RELEASE_MARKER = '.report-mirror-release.json'
MAX_FILES = 10_000
MAX_BYTES = 1024 ** 3
MAX_MANIFEST_BYTES = 16 * 1024 ** 2
CHUNK_BYTES = 1024 ** 2


def relative_path(name: str) -> str:
    if (not isinstance(name, str) or not name or name.startswith('/') or '\\' in name
            or any(ord(char) < 32 or ord(char) == 127 for char in name)
            or re.match(r'^[A-Za-z]:', name) or len(name.encode('utf-8')) > 4096
            or any(part in ('', '.', '..') for part in name.split('/'))
            or name in (RELEASE_MARKER, FILE_MANIFEST)):
        raise ValueError('Unsupported manifest path')
    return name


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def validate_manifest(data) -> dict:
    if (not isinstance(data, dict) or set(data) != {'version', 'files'}
            or type(data['version']) is not int or data['version'] != 1
            or not isinstance(data['files'], dict) or len(data['files']) > MAX_FILES):
        raise ValueError('Invalid manifest schema or file count')
    total = 0
    for name, info in data['files'].items():
        relative_path(name)
        if (not isinstance(info, dict) or set(info) != {'sha256', 'size'}
                or not isinstance(info['sha256'], str)
                or not re.fullmatch(r'[0-9a-f]{64}', info['sha256'])
                or type(info['size']) is not int or info['size'] < 0):
            raise ValueError('Invalid manifest file entry')
        total += info['size']
        if total > MAX_BYTES:
            raise ValueError('Manifest file content exceeds 1 GiB')
    return data


def file_info(path: Path) -> dict:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as source:
        status = os.fstat(source.fileno())
        if not stat.S_ISREG(status.st_mode):
            raise ValueError('Site contains a nonregular file')
        if status.st_size > MAX_BYTES:
            raise ValueError('Site file exceeds 1 GiB')
        digest = hashlib.sha256()
        size = 0
        while chunk := source.read(CHUNK_BYTES):
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError('Site file exceeds 1 GiB')
            digest.update(chunk)
    return {'sha256': digest.hexdigest(), 'size': size}


def site_manifest(site: Path) -> dict:
    files = {}
    directories = [(site, '')]
    total = 0
    while directories:
        directory, prefix = directories.pop()
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            name = prefix + entry.name
            if entry.is_symlink():
                raise ValueError('Site must not contain symlinks')
            if name in (FILE_MANIFEST, RELEASE_MARKER):
                if not entry.is_file(follow_symlinks=False):
                    raise ValueError('Site metadata is not a regular file')
                continue
            relative_path(name)
            if entry.is_dir(follow_symlinks=False):
                directories.append((Path(entry.path), name + '/'))
            elif entry.is_file(follow_symlinks=False):
                if len(files) >= MAX_FILES:
                    raise ValueError('Site exceeds 10000 files')
                files[name] = file_info(Path(entry.path))
                total += files[name]['size']
                if total > MAX_BYTES:
                    raise ValueError('Site content exceeds 1 GiB')
            else:
                raise ValueError('Site contains a special file')
    return validate_manifest({'version': 1, 'files': dict(sorted(files.items()))})


def package(site: Path, base_manifest: Path, output: Path) -> dict:
    if site.is_symlink() or not site.is_dir():
        raise ValueError('Site must be a regular directory')
    if output.resolve().is_relative_to(site.resolve()):
        raise ValueError('Output must be outside the site directory')
    if (base_manifest.is_symlink() or not base_manifest.is_file()
            or base_manifest.stat().st_size > MAX_MANIFEST_BYTES):
        raise ValueError('Base manifest must be a bounded regular file')
    base = validate_manifest(json.loads(base_manifest.read_text(encoding='utf-8'), object_pairs_hook=unique_object))
    current = site_manifest(site)
    payload = (json.dumps(current, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    if len(payload) > MAX_MANIFEST_BYTES:
        raise ValueError('Complete manifest exceeds its size limit')
    changes = [name for name, info in current['files'].items() if base['files'].get(name) != info]
    with tempfile.NamedTemporaryFile(prefix='.report-package-', dir=output.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with tarfile.open(temporary, 'w:gz', format=tarfile.PAX_FORMAT) as archive:
            member = tarfile.TarInfo(FILE_MANIFEST)
            member.size = len(payload)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(payload))
            for name in changes:
                descriptor = os.open(site / name, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(descriptor, 'rb') as source:
                    status = os.fstat(source.fileno())
                    if not stat.S_ISREG(status.st_mode) or status.st_size != current['files'][name]['size']:
                        raise ValueError('Site changed while packaging')
                    member = tarfile.TarInfo(name)
                    member.size = status.st_size
                    member.mode = 0o644
                    archive.addfile(member, source)
        archive_bytes = temporary.stat().st_size
        if archive_bytes > MAX_BYTES:
            raise ValueError('Compressed artifact exceeds 1 GiB')
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {'files': len(current['files']), 'changed_files': len(changes),
            'changed_bytes': sum(current['files'][name]['size'] for name in changes),
            'archive_bytes': archive_bytes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', required=True, type=Path)
    parser.add_argument('--base-manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(package(args.site, args.base_manifest, args.output)))
    except (OSError, ValueError) as error:
        parser.exit(1, f'Packaging failed: {error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
