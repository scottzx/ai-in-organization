#!/usr/bin/env python3
"""Receive a bounded static-site artifact through a dedicated SSH forced command."""

from __future__ import annotations

import fcntl
import gzip
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
SITE_URL = 'https://www.dreammate.work/report/ai-transformation-2026/'
RELEASE_MARKER = '.report-mirror-release.json'
OWNER = {'version': 1, 'repository': 'https://github.com/scottzx/ai-in-organization.git'}
MAX_BYTES = 1024 ** 3
MAX_ENTRIES = 10_000
MAX_TAR_BYTES = MAX_BYTES + 64 * 1024 ** 2
CHUNK_BYTES = 1024 ** 2
LOG = logging.getLogger('report-mirror-receive')


class ReceiveError(Exception):
    """A fixed diagnostic, never containing input command or archive contents."""


def parse_command(command: str) -> str:
    match = re.fullmatch(r'publish ([0-9a-f]{40})', command)
    if not match:
        raise ReceiveError('Only publish followed by one full lowercase commit SHA is accepted')
    return match[1]


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


def valid_release(release: Path, commit: str) -> bool:
    if (release.is_symlink() or not release.is_dir()
            or not read_marker(release / RELEASE_MARKER, release_metadata(commit))):
        return False
    try:
        check_site(release)
    except ReceiveError:
        return False
    return True


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
    return name


def extract_artifact(artifact: Path, site: Path) -> None:
    paths = set()
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
                    content_bytes += member.size
                    if member.size < 0 or content_bytes > MAX_BYTES:
                        raise ReceiveError('Archive file content exceeds the 1 GiB limit')
                    destination.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
                    with archive.extractfile(member) as content, destination.open('xb') as output:
                        shutil.copyfileobj(content, output, CHUNK_BYTES)
                    destination.chmod(0o644)
            # Reach the actual gzip EOF to check CRC/truncation and bound padding.
            while bounded.read(CHUNK_BYTES):
                pass
    except (tarfile.TarError, EOFError, gzip.BadGzipFile):
        raise ReceiveError('Artifact is not a complete gzip tar archive') from None
    if not content_bytes:
        raise ReceiveError('Archive has no file content')


def receive(command: str, stream) -> None:
    commit = parse_command(command)
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
        release = releases / commit
        if os.path.lexists(release) and not valid_release(release, commit):
            raise ReceiveError('Existing release has no matching marker; refusing to overwrite it')
        with tempfile.TemporaryDirectory(prefix='.incoming-', dir=releases) as incoming:
            incoming = Path(incoming)
            artifact = incoming / 'artifact.tar.gz'
            site = incoming / 'site'
            site.mkdir(mode=0o755)
            save_input(stream, artifact)
            extract_artifact(artifact, site)
            check_site(site)
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
