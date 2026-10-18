#!/usr/bin/env python3
"""Receive a bounded static-site artifact through a dedicated SSH forced command."""

from __future__ import annotations

import fcntl
import errno
import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import uuid


WORK_ROOT = Path('/opt/ai-report-mirror')
PUBLIC_ROOT = Path('/var/www/report.dreammate.work')
SITE_NAME = 'ai-transformation-2026'
SITE_URL = 'https://research.dreammate.work/report/ai-transformation-2026/'
LEGACY_SITE_URL = 'https://www.dreammate.work/report/ai-transformation-2026/'
RELEASE_MARKER = '.report-mirror-release.json'
FILE_MANIFEST = '.report-files.json'
OWNER = {'version': 1, 'repository': 'https://github.com/scottzx/ai-in-organization.git'}
MAX_BYTES = 1024 ** 3
MAX_FILES = 10_000
MAX_ENTRIES = 10_001
MAX_MANIFEST_BYTES = 16 * 1024 ** 2
MAX_TAR_BYTES = MAX_BYTES + 64 * 1024 ** 2
CHUNK_BYTES = 1024 ** 2
LOG = logging.getLogger('report-mirror-receive')


class ReceiveError(Exception):
    """A fixed diagnostic, never containing input command or archive contents."""


def parse_command(command: str) -> tuple[str, str | None]:
    if command == 'manifest':
        return 'manifest', None
    match = re.fullmatch(r'publish ([0-9a-f]{40})', command)
    if not match:
        raise ReceiveError('Only manifest or publish with one full lowercase commit SHA is accepted')
    return 'publish', match[1]


def require_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise ReceiveError('A configured directory is missing or is a symlink')


def release_metadata(commit: str) -> dict:
    return {**OWNER, 'commit': commit, 'site_url': SITE_URL}


def read_marker(path: Path, expected: dict) -> bool:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        return False
    try:
        return json.loads(path.read_text(encoding='utf-8')) == expected
    except (OSError, ValueError):
        return False


def check_site(site: Path) -> None:
    for name in ('index.html', 'search-index.json'):
        path = site / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            raise ReceiveError('Artifact needs a nonempty index.html and search-index.json')
    try:
        with (site / 'search-index.json').open(encoding='utf-8') as stream:
            search = json.load(stream)
    except (OSError, ValueError):
        raise ReceiveError('Search index is not valid JSON') from None
    if not isinstance(search, (dict, list)) or not search:
        raise ReceiveError('Search index must be a nonempty JSON object or array')


def valid_release(release: Path, commit: str, *, allow_legacy: bool = False) -> bool:
    expected = release_metadata(commit)
    matching = read_marker(release / RELEASE_MARKER, expected)
    if allow_legacy and not matching:
        matching = read_marker(release / RELEASE_MARKER, {**expected, 'site_url': LEGACY_SITE_URL})
    if (release.is_symlink() or not release.is_dir()
            or not matching):
        return False
    try:
        check_site(release)
    except ReceiveError:
        return False
    return True


def relative_path(name: str) -> str:
    if (not isinstance(name, str) or not name or name.startswith('/') or '\\' in name
            or any(ord(char) < 32 or ord(char) == 127 for char in name)
            or re.match(r'^[A-Za-z]:', name) or len(name.encode('utf-8')) > 4096
            or any(part in ('', '.', '..') for part in name.split('/'))
            or name in (RELEASE_MARKER, FILE_MANIFEST)):
        raise ReceiveError('Manifest contains an unsupported path')
    return name


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReceiveError('JSON contains duplicate keys')
        result[key] = value
    return result


def validate_manifest(data) -> dict:
    if (not isinstance(data, dict) or set(data) != {'version', 'files'}
            or type(data['version']) is not int or data['version'] != 1
            or not isinstance(data['files'], dict) or len(data['files']) > MAX_FILES):
        raise ReceiveError('Invalid file manifest schema or file count')
    total = 0
    for name, info in data['files'].items():
        relative_path(name)
        if (not isinstance(info, dict) or set(info) != {'sha256', 'size'}
                or not isinstance(info['sha256'], str)
                or not re.fullmatch(r'[0-9a-f]{64}', info['sha256'])
                or type(info['size']) is not int or info['size'] < 0):
            raise ReceiveError('Invalid file manifest entry')
        total += info['size']
        if total > MAX_BYTES:
            raise ReceiveError('Manifest file content exceeds the 1 GiB limit')
    return data


def load_manifest(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ReceiveError('Artifact needs a bounded regular file manifest')
    try:
        return validate_manifest(json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_object))
    except (ValueError, UnicodeError):
        raise ReceiveError('File manifest is not valid JSON') from None


def current_release() -> Path | None:
    require_directory(PUBLIC_ROOT)
    require_directory(PUBLIC_ROOT / 'releases')
    live = PUBLIC_ROOT / SITE_NAME
    if not os.path.lexists(live):
        return None
    check_live_link(live)
    match = re.fullmatch(r'releases/([0-9a-f]{40})', os.readlink(live))
    if not match:
        raise ReceiveError('Current report link has an unexpected target')
    release = PUBLIC_ROOT / 'releases' / match[1]
    if not valid_release(release, match[1], allow_legacy=True):
        raise ReceiveError('Current report has no valid ownership marker')
    return release


def open_regular(root: Path, name: str):
    relative_path(name)
    path = root
    for part in name.split('/')[:-1]:
        path /= part
        require_directory(path)
    descriptor = os.open(root / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    stream = os.fdopen(descriptor, 'rb')
    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
        stream.close()
        raise ReceiveError('Base file is not regular')
    return stream


def stream_info(stream) -> dict:
    digest = hashlib.sha256()
    total = 0
    while chunk := stream.read(CHUNK_BYTES):
        total += len(chunk)
        if total > MAX_BYTES:
            raise ReceiveError('File exceeds the 1 GiB limit')
        digest.update(chunk)
    return {'sha256': digest.hexdigest(), 'size': total}


def release_manifest(release: Path) -> dict:
    files = {}
    directories = [(release, '')]
    total = 0
    while directories:
        directory, prefix = directories.pop()
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            name = prefix + entry.name
            if entry.is_symlink():
                raise ReceiveError('Current release contains a symlink')
            if name in (RELEASE_MARKER, FILE_MANIFEST):
                if not entry.is_file(follow_symlinks=False):
                    raise ReceiveError('Current release metadata is not regular')
                continue
            relative_path(name)
            if entry.is_dir(follow_symlinks=False):
                directories.append((Path(entry.path), name + '/'))
            elif entry.is_file(follow_symlinks=False):
                if len(files) >= MAX_FILES:
                    raise ReceiveError('Current release exceeds the file count limit')
                with open_regular(release, name) as stream:
                    info = stream_info(stream)
                files[name] = info
                total += info['size']
                if total > MAX_BYTES:
                    raise ReceiveError('Current release exceeds the 1 GiB limit')
            else:
                raise ReceiveError('Current release contains a special file')
    return validate_manifest({'version': 1, 'files': dict(sorted(files.items()))})


def check_live_link(live: Path) -> None:
    if os.path.lexists(live) and not live.is_symlink():
        raise ReceiveError('Live report path is not a symlink; refusing to replace it')


def switch_release(public_root: Path, commit: str) -> None:
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ReceiveError('Unexpected commit identifier')
    if not valid_release(public_root / 'releases' / commit, commit):
        raise ReceiveError('Release has no matching completion marker')
    live = public_root / SITE_NAME
    check_live_link(live)
    temporary = public_root / f'.{SITE_NAME}.next-{uuid.uuid4().hex}'
    os.symlink(f'releases/{commit}', temporary)
    try:
        os.replace(temporary, live)
    finally:
        if temporary.is_symlink():
            temporary.unlink()


def save_input(stream, destination: Path) -> None:
    """Consume stdin completely, with a bound on the compressed artifact."""
    total = 0
    with destination.open('xb') as output:
        while chunk := stream.read(CHUNK_BYTES):
            total += len(chunk)
            if total > MAX_BYTES:
                raise ReceiveError('Compressed artifact exceeds the 1 GiB limit')
            output.write(chunk)
    if total == 0:
        raise ReceiveError('Artifact is empty')


class TarLimitReader:
    """Bound all decompression, including tar metadata and trailing gzip data."""

    def __init__(self, stream):
        self.stream = stream
        self.total = 0

    def read(self, size=-1):
        allowed = MAX_TAR_BYTES - self.total
        data = self.stream.read(min(size, allowed + 1) if size >= 0 else allowed + 1)
        self.total += len(data)
        if self.total > MAX_TAR_BYTES:
            raise ReceiveError('Expanded archive exceeds the permitted tar size')
        return data


def member_path(member: tarfile.TarInfo) -> str:
    name = member.name
    if (name.startswith('/') or '\\' in name
            or any(ord(char) < 32 or ord(char) == 127 for char in name)
            or re.match(r'^[A-Za-z]:', name)):
        raise ReceiveError('Archive contains an unsupported path')
    # Standard `tar -C _site .` emits ./ and ./file; no directory is stripped.
    while name.startswith('./'):
        name = name[2:]
    if name in ('', '.'):
        if not member.isdir():
            raise ReceiveError('Archive root entry must be a directory')
        return ''
    if name.endswith('/'):
        name = name[:-1]
    if any(part in ('', '.', '..') for part in name.split('/')):
        raise ReceiveError('Archive contains an unsupported path')
    if name == RELEASE_MARKER:
        raise ReceiveError('Archive must not provide the receiver completion marker')
    if name != FILE_MANIFEST:
        relative_path(name)
    return name


def extract_artifact(artifact: Path, site: Path) -> dict:
    paths = set()
    uploaded = {}
    content_bytes = 0
    try:
        with gzip.open(artifact, 'rb') as compressed:
            bounded = TarLimitReader(compressed)
            with tarfile.open(fileobj=bounded, mode='r|') as archive:
                for member in archive:
                    if len(paths) >= MAX_ENTRIES:
                        raise ReceiveError('Archive exceeds the 10000 entry limit')
                    if (member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE) or member.issparse()
                            or member.mode & 0o6000):
                        raise ReceiveError('Archive contains a link or unsupported file type')
                    name = member_path(member)
                    if name in paths:
                        raise ReceiveError('Archive contains duplicate paths')
                    paths.add(name)
                    if not name:
                        continue
                    destination = site / name
                    if member.isdir():
                        destination.mkdir(parents=True, mode=0o755, exist_ok=True)
                        destination.chmod(0o755)
                        continue
                    if name == FILE_MANIFEST:
                        if member.size > MAX_MANIFEST_BYTES:
                            raise ReceiveError('File manifest exceeds its size limit')
                    else:
                        content_bytes += member.size
                    if member.size < 0 or content_bytes > MAX_BYTES:
                        raise ReceiveError('Archive file content exceeds the 1 GiB limit')
                    destination.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
                    digest = hashlib.sha256()
                    total = 0
                    with archive.extractfile(member) as content, destination.open('xb') as output:
                        while chunk := content.read(CHUNK_BYTES):
                            output.write(chunk)
                            digest.update(chunk)
                            total += len(chunk)
                    uploaded[name] = {'sha256': digest.hexdigest(), 'size': total}
                    destination.chmod(0o644)
            # Reach the actual gzip EOF to check CRC/truncation and bound padding.
            while bounded.read(CHUNK_BYTES):
                pass
    except (tarfile.TarError, EOFError, gzip.BadGzipFile):
        raise ReceiveError('Artifact is not a complete gzip tar archive') from None
    if FILE_MANIFEST not in uploaded:
        raise ReceiveError('Archive needs a complete file manifest')
    return uploaded


def reuse_file(base: Path, site: Path, name: str, expected: dict) -> None:
    destination = site / name
    destination.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
    with open_regular(base, name) as source:
        status = os.fstat(source.fileno())
        if status.st_size != expected['size'] or stream_info(source) != expected:
            raise ReceiveError('Base file does not match the requested SHA and size')
        linked = False
        if stat.S_IMODE(status.st_mode) == 0o644:
            try:
                os.link(base / name, destination, follow_symlinks=False)
                linked = True
            except OSError as error:
                if error.errno not in (errno.EXDEV, errno.EPERM, errno.EACCES,
                                       errno.EMLINK, errno.ENOSYS, errno.EOPNOTSUPP):
                    raise
        if linked:
            linked_status = destination.lstat()
            if (not stat.S_ISREG(linked_status.st_mode)
                    or (linked_status.st_dev, linked_status.st_ino) != (status.st_dev, status.st_ino)):
                raise ReceiveError('Base file changed while linking')
        else:
            source.seek(0)
            with destination.open('xb') as output:
                shutil.copyfileobj(source, output, CHUNK_BYTES)
            destination.chmod(0o644)


def complete_site(site: Path, uploaded: dict, base: Path | None) -> dict:
    manifest = load_manifest(site / FILE_MANIFEST)
    files = manifest['files']
    changes = set(uploaded) - {FILE_MANIFEST}
    if not changes <= set(files):
        raise ReceiveError('Archive contains a file absent from the complete manifest')
    for name, expected in files.items():
        if name in changes:
            if uploaded[name] != expected:
                raise ReceiveError('Uploaded file does not match its manifest SHA and size')
        elif base is None:
            raise ReceiveError('Artifact omits a file and no valid base release is available')
        else:
            reuse_file(base, site, name, expected)
    check_site(site)
    (site / FILE_MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
    (site / FILE_MANIFEST).chmod(0o644)
    return manifest


def receive(command: str, stream, output=None) -> None:
    operation, commit = parse_command(command)
    if operation == 'manifest':
        base = current_release()
        if base is None:
            raise ReceiveError('No current report is available')
        result = release_manifest(base)
        (output if output is not None else sys.stdout).write(
            json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n')
        return
    require_directory(WORK_ROOT)
    require_directory(PUBLIC_ROOT)
    descriptor = os.open(WORK_ROOT / 'receive.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a') as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise ReceiveError('Lock is not a regular file')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ReceiveError('Another report publication is in progress') from None
        releases = PUBLIC_ROOT / 'releases'
        releases.mkdir(mode=0o755, exist_ok=True)
        require_directory(releases)
        live = PUBLIC_ROOT / SITE_NAME
        check_live_link(live)
        base = current_release()
        release = releases / commit
        if os.path.lexists(release) and not valid_release(release, commit):
            raise ReceiveError('Existing release has no matching marker; refusing to overwrite it')
        with tempfile.TemporaryDirectory(prefix='.incoming-', dir=releases) as incoming:
            incoming = Path(incoming)
            artifact = incoming / 'artifact.tar.gz'
            site = incoming / 'site'
            site.mkdir(mode=0o755)
            save_input(stream, artifact)
            uploaded = extract_artifact(artifact, site)
            manifest = complete_site(site, uploaded, base)
            if os.path.lexists(release) and release_manifest(release) != manifest:
                raise ReceiveError('Existing commit has different static file content')
            if not os.path.lexists(release):
                marker = site / RELEASE_MARKER
                marker.write_text(json.dumps(release_metadata(commit), sort_keys=True) + '\n', encoding='utf-8')
                marker.chmod(0o644)
                # Ignore sender permissions and the SSH session's umask.
                for directory, _, _ in os.walk(site):
                    Path(directory).chmod(0o755)
                os.replace(site, release)
            # Existing matching releases are idempotent, after consuming and
            # validating all input. Unrecognized directories are never replaced.
            switch_release(PUBLIC_ROOT, commit)
        LOG.info('Published %s at %s', commit[:12], SITE_URL)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        receive(os.environ.get('SSH_ORIGINAL_COMMAND', ''), sys.stdin.buffer)
    except ReceiveError as error:
        LOG.error('%s; live report unchanged', error)
        return 1
    except Exception as error:
        LOG.error('Publication failed (%s); live report unchanged', type(error).__name__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
