#!/usr/bin/env python3
"""Build the public GitHub report in an isolated cache and publish atomically."""

from __future__ import annotations

import fcntl
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import uuid


WORK_ROOT = Path('/opt/ai-report-mirror')
PUBLIC_ROOT = Path('/var/www/report.dreammate.work')
REPOSITORY = 'https://github.com/scottzx/ai-in-organization.git'
BRANCH = 'main'
REF_URL = f'https://api.github.com/repos/scottzx/ai-in-organization/git/ref/heads/{BRANCH}'
ARCHIVE_URL = 'https://codeload.github.com/scottzx/ai-in-organization/tar.gz/{commit}'
SITE_NAME = 'ai-transformation-2026'
SITE_URL = os.environ.get('REPORT_SITE_URL', f'https://report.dreammate.work/{SITE_NAME}/').rstrip('/') + '/'
CACHE_MARKER = '.report-mirror-cache.json'
RELEASE_MARKER = '.report-mirror-release.json'
OWNER = {'version': 1, 'repository': REPOSITORY}
LOG = logging.getLogger('report-mirror')


class UpdateError(Exception):
    """A safe, credential-free message suitable for the service journal."""


def child_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        'PYTHONNOUSERSITE': '1',
        'PYTHONDONTWRITEBYTECODE': '1',
        'REPORT_SITE_URL': SITE_URL,
    })
    return env


def run_step(label: str, args: list[str], *, cwd: Path | None = None,
             timeout: int = 120, capture: bool = False) -> str:
    """Never log child output: network errors can contain credential URLs."""
    LOG.info('%s', label)
    try:
        process = subprocess.Popen(
            args, cwd=cwd, env=child_environment(), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
    except OSError:
        raise UpdateError(f'{label}: could not start command') from None
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise UpdateError(f'{label}: timed out after {timeout}s') from None
    if process.returncode:
        raise UpdateError(f'{label}: command failed (exit {process.returncode})')
    return output.decode('utf-8', errors='strict').strip() if capture else ''


def require_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise UpdateError('A configured directory is missing or is a symlink')


def read_marker(path: Path, expected: dict) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        return json.loads(path.read_text(encoding='utf-8')) == expected
    except (OSError, ValueError):
        return False


def prepare_cache() -> Path:
    cache = WORK_ROOT / 'cache'
    try:
        cache.mkdir(mode=0o700)
    except FileExistsError:
        require_directory(cache)
        if not read_marker(cache / CACHE_MARKER, OWNER):
            raise UpdateError('Cache ownership marker is missing or invalid; inspect it manually')
    else:
        (cache / CACHE_MARKER).write_text(json.dumps(OWNER) + '\n', encoding='utf-8')

    return cache


def curl_arguments(url: str) -> list[str]:
    # --disable must be first: do not load credentials or options from .curlrc.
    return ['curl', '--disable', '--fail', '--silent', '--show-error',
            '--connect-timeout', '10', '--max-time', '120',
            '--proto', '=https', '--header', 'User-Agent: ai-report-mirror', url]


def latest_commit() -> str:
    response = run_step('Read public main reference', curl_arguments(REF_URL), capture=True)
    try:
        data = json.loads(response)
        commit = data['object']['sha']
        valid = (data['ref'] == f'refs/heads/{BRANCH}' and data['object']['type'] == 'commit'
                 and isinstance(commit, str) and re.fullmatch(r'[0-9a-f]{40}', commit))
    except (ValueError, TypeError, KeyError):
        valid = False
    if not valid:
        raise UpdateError('Public API returned an unexpected branch reference')
    return commit


def download_archive(cache: Path, commit: str) -> Path:
    archive = cache / f'{commit}.tar.gz'
    if os.path.lexists(archive):
        if archive.is_symlink() or not archive.is_file():
            raise UpdateError('Archive cache path is not a regular file')
        return archive
    with tempfile.NamedTemporaryFile(prefix='.download-', suffix='.tar.gz', dir=cache, delete=False) as file:
        temporary = Path(file.name)
    try:
        run_step('Download official source archive',
                 curl_arguments(ARCHIVE_URL.format(commit=commit)) + ['--output', str(temporary)])
        os.replace(temporary, archive)
    finally:
        if temporary.is_file():
            temporary.unlink()
    return archive


def release_metadata(commit: str) -> dict:
    return {**OWNER, 'commit': commit, 'site_url': SITE_URL}


def valid_release(release: Path, commit: str) -> bool:
    return (not release.is_symlink() and release.is_dir()
            and (release / 'index.html').is_file()
            and not (release / 'index.html').is_symlink()
            and read_marker(release / RELEASE_MARKER, release_metadata(commit)))


def check_live_link(live: Path) -> None:
    if os.path.lexists(live) and not live.is_symlink():
        raise UpdateError('The live report path is not a symlink; refusing to replace it')


def switch_release(public_root: Path, commit: str) -> None:
    """Replace only this report's link; retain all existing release directories."""
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise UpdateError('Unexpected commit identifier')
    release = public_root / 'releases' / commit
    if not valid_release(release, commit):
        raise UpdateError('Release is incomplete or has no matching ownership marker')
    live = public_root / SITE_NAME
    check_live_link(live)
    temporary = public_root / f'.{SITE_NAME}.next-{uuid.uuid4().hex}'
    os.symlink(f'releases/{commit}', temporary)
    try:
        os.replace(temporary, live)
    finally:
        if temporary.is_symlink():
            temporary.unlink()


def extract_source(archive_path: Path, source: Path) -> None:
    # Codeload adds one top-level directory. Validate every member before writing,
    # strip that prefix, and reject links, traversal, and special files.
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        paths = []
        for member in members:
            parts = member.name.rstrip('/').split('/')
            if (any(part in ('', '.', '..') for part in parts)
                    or '\\' in member.name or '\x00' in member.name
                    or not (member.isfile() or member.isdir())
                    or (len(parts) == 1 and not member.isdir())
                    or member.mode & 0o6000):
                raise UpdateError('Source archive contains an unsupported path or file type')
            paths.append(PurePosixPath(*parts))
        if (not paths or len({path.parts[0] for path in paths}) != 1
                or not any(len(path.parts) > 1 and member.isfile()
                           for member, path in zip(members, paths))):
            raise UpdateError('Source archive must have one top-level directory')
        for member, path in zip(members, paths):
            if len(path.parts) == 1:
                continue
            destination = source.joinpath(*path.parts[1:])
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as content, destination.open('xb') as output:
                shutil.copyfileobj(content, output)
            destination.chmod(member.mode & 0o777)


def build_release(cache: Path, commit: str, releases: Path) -> None:
    release = releases / commit
    if os.path.lexists(release):
        if not valid_release(release, commit):
            raise UpdateError('An unrecognized release directory already exists; inspect it manually')
        LOG.info('Reuse previously completed release %s', commit[:12])
        return
    archive_path = download_archive(cache, commit)
    # Source always stays outside the web root. Only the generated _site moves in.
    with tempfile.TemporaryDirectory(prefix='report-build-', dir=WORK_ROOT) as temporary:
        build_root = Path(temporary)
        source = build_root / 'source'
        source.mkdir()
        extract_source(archive_path, source)
        for script in ('validate.py', 'validate-middle.py', 'build-site.py'):
            run_step(f'Run {script}', [sys.executable, str(source / 'scripts' / script)], cwd=source)
        site = source / '_site'
        if site.is_symlink() or not (site / 'index.html').is_file():
            raise UpdateError('Build did not produce a complete site entry')
        (site / RELEASE_MARKER).write_text(
            json.dumps(release_metadata(commit), sort_keys=True) + '\n', encoding='utf-8')
        # The final directory rename is on the public filesystem even when /opt
        # and /var/www are different mounts. No live link points at pending files.
        with tempfile.TemporaryDirectory(prefix='.pending-', dir=releases) as pending:
            staged = Path(pending) / 'site'
            shutil.move(str(site), staged)
            os.replace(staged, release)


def update() -> None:
    require_directory(WORK_ROOT)
    require_directory(PUBLIC_ROOT)
    lock_path = WORK_ROOT / 'update.lock'
    if lock_path.is_symlink():
        raise UpdateError('Lock path must not be a symlink')
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            LOG.info('Another update is running; skip')
            return
        cache = prepare_cache()
        commit = latest_commit()
        releases = PUBLIC_ROOT / 'releases'
        releases.mkdir(mode=0o755, exist_ok=True)
        require_directory(releases)
        live = PUBLIC_ROOT / SITE_NAME
        check_live_link(live)
        if live.is_symlink() and os.readlink(live) == f'releases/{commit}':
            if not valid_release(releases / commit, commit):
                raise UpdateError('Current release marker is invalid; inspect it manually')
            LOG.info('Already current: %s; skip build', commit[:12])
            return
        build_release(cache, commit, releases)
        switch_release(PUBLIC_ROOT, commit)
        LOG.info('Published %s at %s', commit[:12], SITE_URL)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        update()
    except UpdateError as error:
        LOG.error('%s; live report unchanged', error)
        return 1
    except Exception as error:
        # File names / child output may include unexpected secrets; report only
        # the exception type. No destructive recovery or cache reset is attempted.
        LOG.error('Update failed (%s); live report unchanged', type(error).__name__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
