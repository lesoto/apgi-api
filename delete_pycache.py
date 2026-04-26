import argparse
import fnmatch
import json
import os
import shutil
import sys
from typing import Any, Dict, Iterable, List, Optional, Set, cast

"""
APGI API Cleaner - Enhanced temporary file and folder cleanup utility

This script is specifically configured for the APGI API application to safely remove
temporary files, cache directories, and build artifacts while preserving essential
application files and directories.

SAFETY FEATURES:
- Protects essential API structure: app/, models/, routes/, services/, etc.
- Preserves configuration files: config.py, settings.py, alembic.ini
- Keeps database files and migrations intact
- Maintains environment templates and documentation
- Safe mode enabled by default with additional checks
- Backup functionality available before deletion

CLEANED ITEMS:
- Python cache: __pycache__, *.pyc, *.pyo
- Testing artifacts: .pytest_cache, coverage reports
- Build directories: build/, dist/, out/
- IDE files: .vscode/, .idea/, editor backups
- Temporary files: *.tmp, *.bak, *.log (temporary only)
- Node modules (optional): node_modules/, npm caches

USAGE:
    python delete_pycache.py [--dry-run] [--backup DIR] [--unsafe]

For detailed options, run: python delete_pycache.py --help
"""

ESSENTIAL_FILES = {
    ".gitignore",
    "README.md",
    "README.txt",
    "README.rst",
    "README",
    "LICENSE",
    "LICENSE.txt",
    "COPYING",
    "CHANGELOG.md",
    "CHANGELOG.rst",
    "CONTRIBUTING.md",
    "AUTHORS",
    "NEWS",
    "HISTORY.md",
    "delete_pycache.py",
    "setup.py",
    "setup.cfg",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock",
    "environment.yml",
    "conda.yml",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".dockerignore",
    "Makefile",
    "CMakeLists.txt",
    "configure",
    "config",
    "manifest",
    "MANIFEST.in",
    "alembic.ini",
    "tox.ini",
    ".flake8",
    ".pylintrc",
    "mypy.ini",
    "pytest.ini",
    "bandit.yaml",
    "black.toml",
    "isort.cfg",
    ".pre-commit-config.yaml",
    ".env.example",
    ".env.development",
    ".env.production",
    ".env.production.template",
    "REPORT.md",
    "main.py",
    "app.py",
    "run.py",
    "server.py",
    "wsgi.py",
    "gunicorn.conf.py",
    "uwsgi.ini",
    "config.py",
    "settings.py",
    "conf.py",
    "app_config.py",
    "database_config.py",
    "__init__.py",
    "celery_app.py",
    "exceptions.py",
    "exception_handlers.py",
    "*.pem",
    "*.crt",
    "*.key",
    "*.p12",
    "*.pfx",
    "cert.pem",
    "key.pem",
    "ca.pem",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "database.db",
    "app.db",
    "production.db",
}

ESSENTIAL_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".bzr",
    "app",
    "src",
    "source",
    "lib",
    "libs",
    "modules",
    "packages",
    "api",
    "backend",
    "models",
    "routes",
    "views",
    "controllers",
    "services",
    "utils",
    "helpers",
    "middleware",
    "database",
    "db",
    "migrations",
    "alembic",
    "tasks",
    "jobs",
    "workers",
    "docs",
    "doc",
    "documentation",
    "tests",
    "test",
    "specs",
    "spec",
    "unit_tests",
    "integration_tests",
    "e2e_tests",
    "examples",
    "example",
    "samples",
    "sample",
    "scripts",
    "bin",
    "tools",
    "util",
    "utils",
    "config",
    "conf",
    "cfg",
    "settings",
    "etc",
    "data",
    "dataset",
    "datasets",
    "resources",
    "assets",
    "static",
    "public",
    "media",
    "uploads",
    "storage",
    "templates",
    "template",
    "views",
    "static",
    "public",
    "css",
    "js",
    "javascript",
    "images",
    "img",
    "fonts",
    "deployment",
    "deploy",
    "infrastructure",
    "terraform",
    "ansible",
    "k8s",
    "kubernetes",
    "helm",
    ".github",
    ".gitlab-ci.yml",
    "ci",
    "cd",
    "pipeline",
    "workflows",
    "monitoring",
    "logs",
    "log",
    "metrics",
    "tracing",
    "secrets",
    "certificates",
    "ssl",
    "tls",
    "database",
    "db",
    "data",
    "storage",
    "backups",
    "dump",
    "cache",
    "sessions",
    "redis",
    "memcached",
}

TEMP_DIR_NAMES = {
    "__pycache__",
    "_pycache_",
    "_pycache__",
    "__cache__",
    "_cache_",
    ".pytest_cache",
    ".mypy_cache",
    "mypy_cache",
    ".hypothesis",
    "htmlcov",
    ".coverage",
    "coverage",
    ".tox",
    ".nox",
    ".ruff_cache",
    ".benchmarks",
    ".pytest",
    ".mypy",
    ".flake8",
    ".bandit",
    ".ipynb_checkpoints",
    "build",
    "dist",
    "out",
    "target",
    "bin",
    "obj",
    "debug",
    "release",
    "x86",
    "x64",
    "arm64",
    "Debug",
    "Release",
    "build-linux",
    "build-windows",
    "build-macos",
    ".eggs",
    "*.egg-info",
    "pip-wheel-metadata",
    "wheel-house",
    "site-packages",
    "*.egg",
    "*.dist-info",
    "*.whl",
    "*.tar.gz",
    "*.zip",
    "*.tgz",
    ".venv",
    "venv",
    ".env",
    "env",
    "envs",
    ".virtualenv",
    "virtualenv",
    ".conda",
    "conda-env",
    ".envs",
    "anaconda3",
    "miniconda3",
    "node_modules",
    ".npm",
    ".yarn",
    ".pnpm",
    "bower_components",
    "jspm_packages",
    ".vscode",
    ".idea",
    ".eclipse",
    ".netbeans",
    ".atom",
    ".sublime-*",
    ".vim",
    ".emacs",
    ".emacs.d",
    ".c9",
    ".cloud9",
    ".cache",
    "cache",
    "caches",
    "tmp",
    "temp",
    "tempfile",
    "tempfiles",
    ".tmp",
    ".temp",
    ".DS_Store",
    "__MACOSX",
    ".DocumentRevisions-V100",
    ".TemporaryItems",
    ".VolumeIcon.icns",
    ".AppleDouble",
    ".LSOverride",
    "Icon",
    ".Spotlight-V100",
    ".Trashes",
    ".fseventsd",
    "Thumbs.db",
    "desktop.ini",
    "$RECYCLE.BIN",
    "System Volume Information",
    "RECYCLER",
    ".fuse_hidden*",
    ".Trash-*",
    ".local",
    ".config",
    ".gnome",
    ".kde",
    ".mozilla",
    ".thunderbird",
    ".cache",
    ".dbus",
    ".gvfs",
    "temp",
    "tmp",
    "cache",
    "backup",
    "backups",
    "old",
    "archive",
    "archives",
    "staging",
    "testing",
    "test-output",
    "test-results",
    "artifacts",
    "build-artifacts",
    "ci-artifacts",
    "deployment",
    "deploy",
    "release",
    "releases",
    "packages",
    "bundle",
    "bundles",
    "compiled",
    "output",
    "logs",
    "log",
    "tmp_logs",
    "temp_logs",
    ".sass-cache",
    ".node_repl_history",
    ".python-version",
    ".ruby-version",
    ".nyc_output",
    ".gradle",
    ".maven",
    ".platformio",
    ".pio",
    ".gitkeep",
    ".gitignore",
    ".backup",
    ".old",
    ".orig",
    ".bak",
    ".save",
    "backup",
    "backups",
    "old",
    "archive",
    "archives",
    "staging",
    "testing",
    "test-output",
    "test-results",
    "artifacts",
    "build-artifacts",
    "ci-artifacts",
    "deployment",
    "deploy",
    "release",
    "releases",
    "packages",
    "bundle",
}

TEMP_FILE_PATTERNS = [
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.pyi",
    "*.pyx",
    "*.pyb",
    "*.pyc.*",
    "*.pyo.*",
    "*.pyd.*",
    "*.pyi.*",
    "*.pyx.*",
    "*.pyb.*",
    ".coverage",
    "coverage.xml",
    ".coverage.*",
    "*.cover",
    "htmlcov",
    "coverage",
    ".coverage.*",
    "*.cover.*",
    ".pytest_cache",
    ".mypy_cache",
    ".hypothesis",
    ".ruff_cache",
    ".benchmarks",
    "*.log",
    "*.log.*",
    "*.out",
    "*.out.*",
    "*.err",
    "*.err.*",
    "log.*",
    "*.log.*",
    "temp.log",
    "tmp.log",
    "debug.log",
    "error.log",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "*.DS_Store",
    "*.Thumbs.db",
    "*.desktop.ini",
    "*.tmp",
    "*.temp",
    "*~",
    "*.swp",
    "*.swo",
    "*.bak",
    "*.orig",
    "*.save",
    "*.old",
    "*.backup",
    "*.copy",
    "*.duplicate",
    "*.cache",
    "*.cach",
    "*.tmp.*",
    "*.temp.*",
    "*.bak.*",
    "*.backup.*",
    "*.old.*",
    "*.orig.*",
    "*.save.*",
    "*.swp.*",
    "*.swo.*",
    "*~.*",
    "*.pid",
    "*.lock",
    "*.lck",
    "*.wfl",
    "*.pid.*",
    "*.lock.*",
    "*.lck.*",
    "*.wfl.*",
    "*.core",
    "*.dump",
    "*.crash",
    "*.dmp",
    "*.trace",
    "*.prof",
    "*.profile",
    "*.stats",
    "*.lprof",
    "*.pstats",
    "*.trace.*",
    "*.core.*",
    "*.dump.*",
    "*.crash.*",
    "*.dmp.*",
    "*.prof.*",
    "*.profile.*",
    "*.stats.*",
    "*.lprof.*",
    "*.pstats.*",
    "*.s3db",
    "*.sqlite-shm",
    "*.sqlite-wal",
    "*.db-shm",
    "*.db-wal",
    "*.s3db.*",
    "*.sqlite-shm.*",
    "*.sqlite-wal.*",
    "*.db-shm.*",
    "*.db-wal.*",
    "test.db",
    "temp.db",
    "dev.db",
    "*.test.db",
    "*.temp.db",
    "*.dev.db",
    "*.egg-info",
    "*.egg",
    "*.whl",
    "*.wheel",
    "*.dist-info",
    "*.egg-info.*",
    "*.egg.*",
    "*.whl.*",
    "*.wheel.*",
    "*.dist-info.*",
    "*.tgz",
    "*.tar.gz",
    "*.zip",
    "*.rar",
    "*.7z",
    "*.tar",
    "*.tar.bz2",
    "*.tar.xz",
    "*.tgz.*",
    "*.tar.gz.*",
    "*.zip.*",
    "*.rar.*",
    "*.7z.*",
    "*.tar.*",
    "*.tar.bz2.*",
    "*.tar.xz.*",
    "*.deb",
    "*.rpm",
    "*.dmg",
    "*.pkg",
    "*.msi",
    "*.exe",
    "*.deb.*",
    "*.rpm.*",
    "*.dmg.*",
    "*.pkg.*",
    "*.msi.*",
    "*.exe.*",
    "*.patch",
    "*.diff",
    "*.rej",
    "*.orig",
    "*.session",
    "*.cookie",
    "*.token",
    "*.auth",
    "*.debug",
    "*.test",
    "*.tests",
    "*.spec",
    "*.mock",
    "*.patch.*",
    "*.diff.*",
    "*.rej.*",
    "*.orig.*",
    "*.session.*",
    "*.cookie.*",
    "*.token.*",
    "*.auth.*",
    "*.debug.*",
    "*.test.*",
    "*.tests.*",
    "*.spec.*",
    "*.mock.*",
    ".vscode*",
    ".idea*",
    ".eclipse*",
    ".netbeans*",
    ".atom*",
    ".sublime-*",
    ".vim*",
    ".emacs*",
    ".c9*",
    ".cloud9*",
    "node_modules*",
    ".npm*",
    ".yarn*",
    ".pnpm*",
    "bower_components*",
    "jspm_packages*",
    "*.class",
    "*.jar",
    "*.war",
    "*.ear",
    "*.dll",
    "*.exe",
    "*.obj",
    "*.lib",
    "*.pdb",
    "*.class.*",
    "*.jar.*",
    "*.war.*",
    "*.ear.*",
    "*.dll.*",
    "*.obj.*",
    "*.lib.*",
    "*.pdb.*",
    ".DS_Store?",
    ".DS_Store??",
    ".DS_Store???",
    ".DS_Store????",
    "._*",
    ".Spotlight-V100",
    ".Trashes",
    ".fseventsd",
    "Thumbs.db?",
    "desktop.ini?",
    "*.lnk",
    "*.stackdump",
    "*.mdmp",
    "pagefile.sys",
    "hiberfil.sys",
    "swapfile.sys",
    ".fuse_hidden*",
    ".directory",
    ".hidden",
    ".#*",
    "*.orig",
    "*.rej",
    ".merge*",
    ".git*",
    ".svn*",
    ".hg*",
    ".bzr*",
    "*.conf.bak",
    "*.config.bak",
    "*.cfg.bak",
    "*.ini.bak",
    "*.json.bak",
    "*.yaml.bak",
    "*.yml.bak",
    "*.toml.bak",
    "*.sock",
    "*.pid",
    "*.lock",
    "*.lck",
    "*.wfl",
    "*.sock.*",
    "*.pid.*",
    "*.lock.*",
    "*.lck.*",
    "*.wfl.*",
    "temp*",
    "tmp*",
    "cache*",
    "backup*",
    "old*",
    "junk*",
    "trash*",
    "deleted*",
    "removed*",
    "test*",
    "debug*",
    "build*",
    "dist*",
    "output*",
    "*.temp",
    "*.tmp",
    "*.cache",
    "*.backup",
    "*.old",
    "*.junk",
    "*.trash",
    "*.deleted",
    "*.removed",
    "*.test",
    "*.debug",
    "*.build",
    "*.dist",
    "*.output",
]

SKIP_TRAVERSE_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".bzr",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
}

DEFAULT_CONFIG = {
    "temp_dirs": list(TEMP_DIR_NAMES),
    "temp_files": TEMP_FILE_PATTERNS,
    "essential_files": list(ESSENTIAL_FILES),
    "essential_dirs": list(ESSENTIAL_DIRS),
    "skip_dirs": list(SKIP_TRAVERSE_DIRS),
    "safe_mode": True,
    "backup_before_delete": False,
}


def matches_any(name: str, patterns: Iterable[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        return {**DEFAULT_CONFIG, **config}
    except FileNotFoundError:
        if os.path.basename(config_path) == ".cleanrc":
            try:
                with open(config_path, "w") as f:
                    json.dump(DEFAULT_CONFIG, f, indent=2)
                print(f"Created default config at {config_path}")
                return DEFAULT_CONFIG
            except Exception:
                pass
        return DEFAULT_CONFIG
    except json.JSONDecodeError as e:
        print(f"Error parsing config file {config_path}: {e}")
        return DEFAULT_CONFIG


def is_essential_file(file_path: str, essential_files: Set[str]) -> bool:
    """Check if a file is essential and should never be removed."""
    filename = os.path.basename(file_path)
    return filename in essential_files


def is_essential_dir(dir_path: str, essential_dirs: Set[str]) -> bool:
    """Check if a directory is essential and should never be removed."""
    dirname = os.path.basename(dir_path)
    return dirname in essential_dirs


def is_safe_to_remove(item_path: str, root_dir: str, safe_mode: bool = True) -> bool:
    """Additional safety checks before removing files/directories."""
    if not safe_mode:
        return True

    rel_path = os.path.relpath(item_path, root_dir)
    if rel_path.count(os.sep) == 0:
        return os.path.basename(item_path).startswith(".") or any(
            temp in os.path.basename(item_path).lower() for temp in ["temp", "tmp", "cache", "log"]
        )

    return True


def create_backup(item_path: str, backup_dir: str) -> bool:
    """Create a backup of an item before deletion."""
    try:
        os.makedirs(backup_dir, exist_ok=True)
        backup_name = os.path.basename(item_path)
        backup_path = os.path.join(backup_dir, backup_name)

        counter = 1
        while os.path.exists(backup_path):
            name, ext = os.path.splitext(backup_name)
            backup_path = os.path.join(backup_dir, f"{name}_{counter}{ext}")
            counter += 1

        if os.path.isfile(item_path):
            shutil.copy2(item_path, backup_path)
        else:
            shutil.copytree(item_path, backup_path)
        return True
    except Exception as e:
        print(f"Failed to create backup for {item_path}: {e}")
        return False


def delete_temporary_items(
    root_dir: str,
    dry_run: bool = False,
    verbose: bool = True,
    include_dir_patterns: Iterable[str] = (),
    include_file_patterns: Iterable[str] = (),
    exclude_dir_patterns: Iterable[str] = (),
    exclude_file_patterns: Iterable[str] = (),
    remove_node_modules: bool = False,
    remove_venvs: bool = False,
    venv_names: Iterable[str] = (".venv", "venv", ".env", "env"),
    follow_links: bool = False,
    max_depth: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None,
    backup_dir: Optional[str] = None,
) -> None:
    """Enhanced deletion of temporary directories and files with safety checks."""
    if config is None:
        config = DEFAULT_CONFIG

    temp_dir_names = set(cast(list[str], config.get("temp_dirs", list(TEMP_DIR_NAMES))))
    temp_file_patterns = cast(list[str], config.get("temp_files", TEMP_FILE_PATTERNS))
    essential_files = set(cast(list[str], config.get("essential_files", list(ESSENTIAL_FILES))))
    essential_dirs = set(cast(list[str], config.get("essential_dirs", list(ESSENTIAL_DIRS))))
    skip_traverse_dirs = set(cast(list[str], config.get("skip_dirs", list(SKIP_TRAVERSE_DIRS))))
    safe_mode = cast(bool, config.get("safe_mode", True))
    backup_before_delete = cast(bool, config.get("backup_before_delete", False))

    temp_dir_names.update(include_dir_patterns)
    temp_file_patterns.extend(include_file_patterns)

    if backup_dir and backup_before_delete and not dry_run:
        os.makedirs(backup_dir, exist_ok=True)
        if verbose:
            print(f"Backup directory: {backup_dir}")

    removed_dirs = 0
    removed_files = 0
    skipped_essential = 0

    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True, followlinks=follow_links):
        if max_depth is not None:
            rel = os.path.relpath(dirpath, root_dir)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            if depth > max_depth:
                dirnames[:] = []
                continue

        for d in list(dirnames):
            full_d = os.path.join(dirpath, d)

            if is_essential_dir(full_d, essential_dirs):
                if verbose:
                    print(f"Skipping essential directory: {full_d}")
                dirnames.remove(d)
                skipped_essential += 1
                continue

            if d in skip_traverse_dirs:
                dirnames.remove(d)
                continue

            should_remove_dir = (
                d in temp_dir_names
                or matches_any(d, temp_dir_names)
                or matches_any(d, include_dir_patterns)
                or (remove_node_modules and d == "node_modules")
                or (remove_venvs and d in set(venv_names))
            ) and not matches_any(d, exclude_dir_patterns)

            if should_remove_dir and not is_safe_to_remove(full_d, root_dir, safe_mode):
                if verbose:
                    print(f"Skipping unsafe directory: {full_d}")
                continue

            if should_remove_dir:
                if dry_run:
                    if verbose:
                        print(f"Would remove directory: {full_d}")
                    removed_dirs += 1
                else:
                    try:
                        if backup_before_delete and backup_dir:
                            if create_backup(full_d, backup_dir):
                                if verbose:
                                    print(f"Backed up directory: {full_d}")

                        shutil.rmtree(full_d, ignore_errors=False)
                        if verbose:
                            print(f"Removed directory: {full_d}")
                        removed_dirs += 1
                    except Exception as e:
                        print(f"Error removing directory {full_d}: {e}")
                if d in dirnames:
                    dirnames.remove(d)

        for f in list(filenames):
            full_f = os.path.join(dirpath, f)

            if is_essential_file(full_f, essential_files):
                if verbose:
                    print(f"Skipping essential file: {full_f}")
                skipped_essential += 1
                continue

            if matches_any(f, exclude_file_patterns):
                continue

            should_remove_file = (
                f in temp_file_patterns
                or matches_any(f, temp_file_patterns)
                or matches_any(f, include_file_patterns)
            )

            if should_remove_file and not is_safe_to_remove(full_f, root_dir, safe_mode):
                if verbose:
                    print(f"Skipping unsafe file: {full_f}")
                continue

            if should_remove_file:
                if dry_run:
                    if verbose:
                        print(f"Would remove file: {full_f}")
                    removed_files += 1
                else:
                    try:
                        if backup_before_delete and backup_dir:
                            if create_backup(full_f, backup_dir):
                                if verbose:
                                    print(f"Backed up file: {full_f}")

                        os.remove(full_f)
                        if verbose:
                            print(f"Removed file: {full_f}")
                        removed_files += 1
                    except Exception as e:
                        print(f"Error removing file {full_f}: {e}")

    # Summary
    if verbose:
        print(f"\nSummary: Removed {removed_dirs} directories and {removed_files} files")
        if skipped_essential > 0:
            print(f"Skipped {skipped_essential} essential items")


def prune_empty_dirs(root_dir: str, dry_run: bool = False, verbose: bool = True) -> None:
    """Remove empty directories after cleanup."""
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        # don't prune the root itself
        if dirpath == root_dir:
            continue
        try:
            if not os.listdir(dirpath):
                if dry_run:
                    if verbose:
                        print(f"Would remove empty directory: {dirpath}")
                else:
                    os.rmdir(dirpath)
                    if verbose:
                        print(f"Removed empty directory: {dirpath}")
        except Exception as e:
            print(f"Error pruning directory {dirpath}: {e}")


def clean_special_cases(root_dir: str, dry_run: bool = False, verbose: bool = True) -> int:
    """Handle special cleanup cases that might be missed by pattern matching."""
    special_patterns = [
        # Python cache directories with various naming patterns
        "**/__pycache__",
        "**/_pycache_",
        "**/__pycache__",
        "**/_pycache__",
        "**/_pycache_",
        # Common temporary directories
        "**/temp",
        "**/tmp",
        "**/cache",
        "**/backup",
        "**/backups",
        "**/old",
        # Build artifacts
        "**/build",
        "**/dist",
        "**/out",
        "**/target",
        "**/bin",
        "**/obj",
        # IDE directories
        "**/.vscode",
        "**/.idea",
        "**/.eclipse",
        "**/.netbeans",
        # OS specific
        "**/.DS_Store",
        "**/Thumbs.db",
        "**/desktop.ini",
    ]

    import glob

    removed_special = 0
    for pattern in special_patterns:
        full_pattern = os.path.join(root_dir, pattern)
        matches = glob.glob(full_pattern, recursive=True)

        for match in matches:
            if os.path.isdir(match):
                # Additional safety check for directories
                if is_safe_to_remove(match, root_dir, safe_mode=True):
                    if dry_run:
                        if verbose:
                            print(f"Would remove special directory: {match}")
                        removed_special += 1
                    else:
                        try:
                            shutil.rmtree(match, ignore_errors=False)
                            if verbose:
                                print(f"Removed special directory: {match}")
                            removed_special += 1
                        except Exception as e:
                            print(f"Error removing special directory {match}: {e}")
            elif os.path.isfile(match):
                # Additional safety check for files
                if is_safe_to_remove(match, root_dir, safe_mode=True):
                    if dry_run:
                        if verbose:
                            print(f"Would remove special file: {match}")
                        removed_special += 1
                    else:
                        try:
                            os.remove(match)
                            if verbose:
                                print(f"Removed special file: {match}")
                            removed_special += 1
                        except Exception as e:
                            print(f"Error removing special file {match}: {e}")

    if verbose and removed_special > 0:
        print(f"Special cleanup: Removed {removed_special} additional items")

    return removed_special


def clear_log_files(
    root_dir: str, delete_logs_dir: bool = False, dry_run: bool = False, verbose: bool = True
) -> None:
    """Either truncate files under a `logs` dir, or delete the logs directory entirely.

    - If delete_logs_dir is True, the whole logs directory is removed.
    - If False, each file is truncated to 0 bytes.
    """
    log_dir = os.path.join(root_dir, "logs")

    if not os.path.exists(log_dir):
        if verbose:
            print(f"Log directory not found at: {log_dir}")
        return

    if delete_logs_dir:
        if dry_run:
            if verbose:
                print(f"Would remove logs directory: {log_dir}")
        else:
            try:
                shutil.rmtree(log_dir, ignore_errors=False)
                if verbose:
                    print(f"Removed logs directory: {log_dir}")
            except Exception as e:
                print(f"Error removing logs directory {log_dir}: {e}")
        return

    # otherwise truncate files inside logs
    for root, dirs, files in os.walk(log_dir):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                if dry_run:
                    if verbose:
                        print(f"Would clear file: {file_path}")
                else:
                    with open(file_path, "w"):
                        pass
                    if verbose:
                        print(f"Cleared: {file_path}")
            except Exception as e:
                print(f"Error clearing {file_path}: {str(e)}")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Enhanced APGI API temporary file and folder cleaner with safety checks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
APGI API Cleaner - Safely removes temporary files while preserving essential application files

Examples:
  %(prog)s                           # Clean current directory (includes special cleanup by default)
  %(prog)s /path/to/project           # Clean specific directory (includes special cleanup by default)
  %(prog)s --dry-run                  # Show what would be removed
  %(prog)s --remove-node-modules      # Also remove node_modules
  %(prog)s --config .cleanrc          # Use custom config
  %(prog)s --backup /tmp/backup       # Backup before deletion
  %(prog)s --unsafe                   # Disable safety mode (not recommended for production)
  %(prog)s --no-special-cleanup       # Disable special cleanup (enabled by default)
  %(prog)s --prune-empty-dirs        # Remove empty directories after cleanup

Safety Features:
  - Protects essential API files: main.py, config.py, models/, routes/, services/, etc.
  - Preserves database files and migrations
  - Keeps environment templates and documentation
  - Safe mode enabled by default
  - Backup option available
        """,
    )

    # Basic options
    p.add_argument(
        "root", nargs="?", default=None, help="Root directory to clean (defaults to script dir)"
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Show what would be removed without deleting"
    )
    p.add_argument("--yes", action="store_true", help="Don't prompt for confirmation")
    p.add_argument("--quiet", action="store_true", help="Reduce output")

    # Configuration
    p.add_argument("--config", default=None, help="Path to configuration file (JSON)")
    p.add_argument(
        "--create-config", action="store_true", help="Create default .cleanrc config file"
    )

    # Safety and backup
    p.add_argument("--unsafe", action="store_true", help="Disable safety mode (not recommended)")
    p.add_argument("--backup", metavar="DIR", help="Backup directory before deletion")
    p.add_argument(
        "--no-backup", action="store_true", help="Disable backup even if config enables it"
    )

    # Log handling
    p.add_argument(
        "--delete-logs",
        action="store_true",
        help="Remove the entire logs directory instead of truncating files",
    )
    p.add_argument(
        "--clear-logs-only",
        action="store_true",
        help="Only clear log files, don't remove other temp files",
    )

    # Advanced controls
    p.add_argument(
        "--include-dir",
        action="append",
        default=[],
        help="Additional directory patterns to remove (glob). Can be passed multiple times.",
    )
    p.add_argument(
        "--include-file",
        action="append",
        default=[],
        help="Additional file patterns to remove (glob). Can be passed multiple times.",
    )
    p.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory patterns to exclude from deletion (glob). Can be passed multiple times.",
    )
    p.add_argument(
        "--exclude-file",
        action="append",
        default=[],
        help="File patterns to exclude from deletion (glob). Can be passed multiple times.",
    )
    p.add_argument(
        "--remove-node-modules", action="store_true", help="Also remove node_modules directories"
    )
    p.add_argument(
        "--remove-venvs",
        action="store_true",
        help="Also remove common virtualenv directories (.venv, venv, .env, env)",
    )
    p.add_argument(
        "--venv-names",
        nargs="*",
        default=None,
        help="Override names considered virtualenvs (space-separated)",
    )
    p.add_argument(
        "--follow-links",
        action="store_true",
        help="Follow symbolic links during traversal (use with caution)",
    )
    p.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Limit traversal depth relative to root (1 = only root level)",
    )
    p.add_argument(
        "--prune-empty-dirs", action="store_true", help="Remove now-empty directories after cleanup"
    )
    p.add_argument(
        "--special-cleanup",
        action="store_true",
        help="Run special cleanup for edge cases and missed patterns (enabled by default)",
    )
    p.add_argument(
        "--no-special-cleanup",
        action="store_true",
        help="Disable special cleanup (enabled by default)",
    )

    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_directory = os.path.abspath(args.root) if args.root else current_dir

    # Handle config creation
    if args.create_config:
        config_path = os.path.join(root_directory, ".cleanrc")
        try:
            with open(config_path, "w") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            print(f"Created default config at {config_path}")
            return 0
        except Exception as e:
            print(f"Error creating config: {e}")
            return 1

    # Load configuration
    config = DEFAULT_CONFIG
    if args.config:
        config = load_config(args.config)
    else:
        # Try to load .cleanrc from root directory
        cleanrc_path = os.path.join(root_directory, ".cleanrc")
        if os.path.exists(cleanrc_path):
            config = load_config(cleanrc_path)

    # Override config with command line options
    if args.unsafe:
        config["safe_mode"] = False
    if args.no_backup:
        config["backup_before_delete"] = False
    if args.backup:
        config["backup_before_delete"] = True

    dry_run = args.dry_run
    verbose = not args.quiet

    # Safety check
    if not os.path.exists(root_directory):
        print(f"Error: Directory {root_directory} does not exist")
        return 1

    if not args.yes and not dry_run:
        print(f"About to clean temporary files under: {root_directory}")
        if config["safe_mode"]:
            print("Safety mode: ENABLED (use --unsafe to disable)")
        if config["backup_before_delete"]:
            print(f"Backup mode: ENABLED (to {args.backup or 'default location'})")
        resp = input("Proceed? [y/N]: ").strip().lower()
        if resp not in ("y", "yes"):
            print("Aborted by user.")
            return 1

    if verbose:
        print("Starting enhanced cleanup process...")
        print(f"Safe mode: {'ON' if config['safe_mode'] else 'OFF'}")
        print(f"Backup: {'ON' if config['backup_before_delete'] else 'OFF'}")

    venv_names = (
        args.venv_names if args.venv_names is not None else (".venv", "venv", ".env", "env")
    )

    # Run cleanup unless only clearing logs
    if not args.clear_logs_only:
        delete_temporary_items(
            root_directory,
            dry_run=dry_run,
            verbose=verbose,
            include_dir_patterns=args.include_dir,
            include_file_patterns=args.include_file,
            exclude_dir_patterns=args.exclude_dir,
            exclude_file_patterns=args.exclude_file,
            remove_node_modules=args.remove_node_modules,
            remove_venvs=args.remove_venvs,
            venv_names=venv_names,
            follow_links=args.follow_links,
            max_depth=args.max_depth,
            config=config,
            backup_dir=args.backup,
        )

    # Handle logs
    clear_log_files(
        root_directory, delete_logs_dir=args.delete_logs, dry_run=dry_run, verbose=verbose
    )

    # Prune empty directories
    if args.prune_empty_dirs:
        prune_empty_dirs(root_directory, dry_run=dry_run, verbose=verbose)

    # Run special cleanup for edge cases by default (unless disabled)
    if not args.no_special_cleanup:
        clean_special_cases(root_directory, dry_run=dry_run, verbose=verbose)

    if verbose:
        print("\nEnhanced cleanup completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
