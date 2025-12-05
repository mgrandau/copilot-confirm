#!/usr/bin/env python3
"""Installation script for Copilot Confirm agent files.

Provides CLI and programmatic installation of VS Code Copilot agent customizations
(agents + instructions) to local repos or global VS Code config.

Business: Enables consistent Copilot behavior across workspaces via reusable agents.
Provides confirmation workflow that prevents destructive operations w/o user approval.

Features:
    • Local install → .github/agents/ + .github/instructions/
    • Global install → VS Code User prompts/ directory
    • Auto-detect VS Code variant (stable/Insiders)
    • Cross-platform: Windows, macOS, Linux
    • Dry-run mode for preview
    • Protocol-based DI for testability

Usage:
    CLI: `copilot-confirm --global --insiders --dry-run`
    Programmatic: `installer = create_installer(); installer.install_local()`
"""

import argparse
import logging
import os
import platform
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

# Public API
__all__ = [
    # Factory & entry points
    "create_installer",
    "setup_logging",
    "main",
    # Core classes
    "AgentInstaller",
    "InstallationResult",
    "FileMapping",
    # Supporting classes
    "PathResolver",
    "EditorDetector",
    "OperatingSystem",
    # Protocols (for custom implementations)
    "FileSystemProtocol",
    "EnvironmentProtocol",
]

# Constants
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ============================================================================
# Enums
# ============================================================================


class OperatingSystem(Enum):
    """Supported operating systems for path resolution.

    Business: Enables cross-platform VS Code config path construction.
    Each value matches platform.system() output for direct comparison.

    Attributes:
        WINDOWS: Windows OS ("Windows")
        DARWIN: macOS ("Darwin")
        LINUX: Linux distributions ("Linux")
    """

    WINDOWS = "Windows"
    DARWIN = "Darwin"
    LINUX = "Linux"


# ============================================================================
# Protocols (Dependency Abstractions)
# ============================================================================


class FileSystemProtocol(Protocol):
    """Protocol for filesystem operations, enabling test mocking.

    Business: Abstracts I/O for dependency injection. Tests use MockFileSystem
    to verify behavior w/o real disk access.

    Attributes:
        exists: Check path existence
        mkdir: Create directory (w/ parents option)
        copy_file: Copy file preserving metadata
        get_cwd: Get current working directory
    """

    def exists(self, path: Path) -> bool:
        """Check if a path exists."""
        ...

    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:
        """Create a directory."""
        ...

    def copy_file(self, src: Path, dst: Path) -> None:
        """Copy a file from src to dst."""
        ...

    def get_cwd(self) -> Path:
        """Get the current working directory."""
        ...


class EnvironmentProtocol(Protocol):
    """Protocol for environment operations, enabling test mocking.

    Business: Abstracts platform/env detection for DI. Tests use MockEnvironment
    to simulate different OS/env configurations.

    Attributes:
        get_system: Get OS name (Windows/Darwin/Linux)
        get_env_var: Get environment variable w/ default
        get_home: Get user home directory path
    """

    def get_system(self) -> str:
        """Get the operating system name."""
        ...

    def get_env_var(self, name: str, default: str = "") -> str:
        """Get an environment variable."""
        ...

    def get_home(self) -> Path:
        """Get the user's home directory."""
        ...


# ============================================================================
# Default Implementations
# ============================================================================


# NOTE: Methods marked pragma: no cover - tested via integration tests
class RealFileSystem:
    """Production filesystem implementation using pathlib/shutil.

    Business: Provides actual disk I/O for production installation.

    Technical: Thin wrapper around Path and shutil. copy_file uses copy2
    to preserve file metadata (timestamps, permissions).
    """

    def exists(self, path: Path) -> bool:  # pragma: no cover
        return path.exists()

    def mkdir(
        self, path: Path, parents: bool = False, exist_ok: bool = False
    ) -> None:  # pragma: no cover
        path.mkdir(parents=parents, exist_ok=exist_ok)

    def copy_file(self, src: Path, dst: Path) -> None:  # pragma: no cover
        shutil.copy2(src, dst)

    def get_cwd(self) -> Path:  # pragma: no cover
        return Path.cwd()


# NOTE: Methods marked pragma: no cover - tested via integration tests
class RealEnvironment:
    """Production environment implementation using platform/os modules.

    Business: Provides actual OS/env detection for production path resolution.

    Technical: Thin wrapper around platform.system(), os.environ, Path.home().
    """

    def get_system(self) -> str:  # pragma: no cover
        return platform.system()

    def get_env_var(self, name: str, default: str = "") -> str:  # pragma: no cover
        return os.environ.get(name, default)

    def get_home(self) -> Path:  # pragma: no cover
        return Path.home()


# ============================================================================
# Logging Configuration
# ============================================================================


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    logger_name: str = "copilot_confirm",
) -> logging.Logger:
    """Configure logging w/ console and optional file handlers.

    Creates isolated logger w/ emoji-formatted console output and optional
    detailed file logging. Clears existing handlers to prevent duplicates
    across multiple calls.

    Business: Provides user-friendly installation feedback via emoji indicators
    (✅ success, ❌ error, 📁 paths) while enabling debug traces for troubleshooting.

    Args:
        level: Log level ∈ {DEBUG, INFO, WARNING, ERROR, CRITICAL}. Default: INFO.
        log_file: Optional file path for persistent logs. Parent dirs created
            if missing.
        logger_name: Logger name for isolation. Default: "copilot_confirm".

    Returns:
        logging.Logger: Configured logger w/ 1-2 handlers (console + optional file).
        Console uses simple format; file uses timestamped detailed format.

    Raises:
        OSError: If log_file parent dir creation fails (permissions, disk full).
        ValueError: If level not valid logging level string.

    Examples:
        ```python
        logger = setup_logging(level="DEBUG", log_file=Path("/tmp/install.log"))
        logger.info("✅ Installation complete")
        ```

    Technical: O(1). Thread-safe via logging module. ~0.1ms setup time.
    Propagation disabled to prevent duplicate output via root logger.
    """
    # Validate log level before using
    valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    level_upper = level.upper()
    if level_upper not in valid_levels:
        raise ValueError(
            f"Invalid log level '{level}'. Must be one of: {', '.join(valid_levels)}"
        )

    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level_upper))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter with emoji support
    formatter = logging.Formatter(fmt="%(message)s", datefmt=LOG_DATE_FORMAT)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        # Use more detailed format for file output
        file_formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt=LOG_DATE_FORMAT,
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


# ============================================================================
# Domain Models
# ============================================================================


@dataclass(frozen=True, slots=True)
class FileMapping:
    """Immutable mapping of source → destination relative paths.

    Business: Defines file copy operations for installation. Frozen for safety
    (can't accidentally modify during iteration).

    Attributes:
        src_relative: Source path relative to agent_files_dir.
        dst_relative: Destination path relative to target install dir.

    Examples:
        ```python
        mapping = FileMapping("agents/foo.md", "prompts/foo.md")
        src = agent_dir / mapping.src_relative
        dst = target_dir / mapping.dst_relative
        ```
    """

    src_relative: str
    dst_relative: str


@dataclass(frozen=True, slots=True)
class InstallationResult:
    """Immutable result of an installation operation.

    Business: Provides structured success/failure info for CLI exit codes
    and programmatic error handling. Frozen for safety.

    Attributes:
        success: True if ≥1 file copied (or dry-run completed).
        files_copied: Count of files successfully copied.
        target_dir: Destination directory path.
        error_message: Human-readable error if success=False, else None.
        files_failed: Count of files that failed to copy (missing source, etc.).

    Examples:
        ```python
        if result.success:
            print(f"Installed {result.files_copied} files to {result.target_dir}")
        else:
            print(f"Failed: {result.error_message}")
        ```
    """

    success: bool
    files_copied: int
    target_dir: Path
    error_message: str | None = None
    files_failed: int = 0


# ============================================================================
# Core Business Logic
# ============================================================================


class PathResolver:
    """Cross-platform path resolution for VS Code config and local install.

    Business: Abstracts OS-specific path differences. Maps editor names to
    config directories. Finds git repo root for local .github installation.

    Attributes:
        EDITOR_PATHS: Nested dict mapping OS → editor → path components.
        env: EnvironmentProtocol for OS/home detection.
        fs: FileSystemProtocol for exists checks.
        system: Detected OperatingSystem enum value.

    Technical: Initialized once per installer. Path lookups are O(1) dict access.
    """

    # Editor configuration paths by OS
    EDITOR_PATHS: dict[OperatingSystem, dict[str, list[str]]] = {
        OperatingSystem.WINDOWS: {
            "Code": ["Code", "User"],
            "Code-Insiders": ["Code - Insiders", "User"],
        },
        OperatingSystem.LINUX: {
            "Code": [".config", "Code", "User"],
            "Code-Insiders": [".config", "Code - Insiders", "User"],
        },
        OperatingSystem.DARWIN: {
            "Code": ["Library", "Application Support", "Code", "User"],
            "Code-Insiders": [
                "Library",
                "Application Support",
                "Code - Insiders",
                "User",
            ],
        },
    }

    def __init__(self, env: EnvironmentProtocol, fs: FileSystemProtocol):
        """Initialize path resolver w/ platform detection.

        Detects OS from env.get_system() and stores for path resolution.
        Validates OS is supported (Windows/macOS/Linux).

        Business: Enables cross-platform path resolution for VS Code config dirs.

        Args:
            env: Environment ops (system detection, env vars, home dir).
            fs: Filesystem ops (exists, mkdir, copy, cwd).

        Raises:
            ValueError: If OS not in {Windows, Darwin, Linux}.

        Examples:
            ```python
            resolver = PathResolver(RealEnvironment(), RealFileSystem())
            config = resolver.get_vscode_config_dir("Code")
            ```
        """
        self.env = env
        self.fs = fs
        # Convert platform.system() string to OperatingSystem enum
        system_str = env.get_system()
        try:
            self.system = OperatingSystem(system_str)
        except ValueError:
            # Fallback for unsupported systems
            raise ValueError(f"Unsupported operating system: {system_str}") from None

    def get_vscode_config_dir(self, editor: str) -> Path | None:
        """Get VS Code config directory for current OS and editor variant.

        Resolves platform-specific config path:
        - Windows: %APPDATA%/Code/User or %APPDATA%/Code - Insiders/User
        - macOS: ~/Library/Application Support/Code/User
        - Linux: ~/.config/Code/User

        Business: Locates correct prompts/ parent dir for global agent installation.

        Args:
            editor: Editor variant ∈ {"Code", "Code-Insiders"}.

        Returns:
            Path: Config dir path, or None if editor unsupported or APPDATA missing.

        Examples:
            ```python
            path = resolver.get_vscode_config_dir("Code-Insiders")
            # Linux: ~/.config/Code - Insiders/User
            ```

        Technical: O(1). No I/O (path construction only). Thread-safe.
        """
        if editor not in self.EDITOR_PATHS[self.system]:
            return None

        path_parts = self.EDITOR_PATHS[self.system][editor]

        if self.system == OperatingSystem.WINDOWS:
            appdata = self.env.get_env_var("APPDATA")
            if not appdata:
                return None
            base = Path(appdata)
        else:
            base = self.env.get_home()

        result = base
        for part in path_parts:
            result = result / part

        return result

    def get_local_install_dir(self) -> Path:
        """Get .github directory for repo-local agent installation.

        Walks up directory tree from cwd to find .git, returns sibling .github.
        Falls back to cwd/.github if not in git repo.

        Business: Enables per-repo agent customization via .github/agents/.

        Returns:
            Path: .github directory (may not exist yet). Always returns valid path.

        Examples:
            ```python
            # In /home/user/myrepo/src/ with /home/user/myrepo/.git existing
            path = resolver.get_local_install_dir()
            # Returns: /home/user/myrepo/.github
            ```

        Technical: O(d) where d=directory depth. 1 exists() check per level.
        """
        current = self.fs.get_cwd()

        # Walk up directory tree to find .git
        while current.parent != current:  # Stop at filesystem root
            if self.fs.exists(current / ".git"):
                return current / ".github"
            current = current.parent

        # If not in a git repo, use current directory
        return self.fs.get_cwd() / ".github"


class EditorDetector:
    """Detects installed VS Code variants by checking config directories.

    Business: Enables auto-detection for --global install w/o explicit editor flag.
    Prioritizes Insiders since developers using it prefer bleeding-edge features.

    Attributes:
        SUPPORTED_EDITORS: ["Code-Insiders", "Code"] - check order matters.
        DEFAULT_EDITOR: Fallback editor when none detected ("Code").
        path_resolver: For getting config dir paths.
        fs: For exists() checks.

    Technical: O(n) detection where n=len(SUPPORTED_EDITORS). 1-2 exists() calls.
    """

    # Check Insiders first since users running Insiders typically prefer it
    SUPPORTED_EDITORS: list[str] = ["Code-Insiders", "Code"]
    # Default fallback when no editor config directory found
    DEFAULT_EDITOR: str = "Code"

    def __init__(self, path_resolver: PathResolver, fs: FileSystemProtocol):
        """Initialize editor detector with path resolution and filesystem access.

        Business: Wires up dependencies for auto-selecting VS Code variant
        during global install when user doesn't specify --editor flag.

        Args:
            path_resolver: Path resolution service for config directories.
            fs: File system operations provider for exists() checks.
        """
        self.path_resolver = path_resolver
        self.fs = fs

    def detect_installed_editor(self) -> str:
        """Auto-detect installed VS Code variant by checking config dirs.

        Checks Insiders first (developers prefer bleeding-edge), then stable.
        Returns "Code" as fallback if neither found.

        Business: Enables --global install w/o requiring explicit editor flag.

        Returns:
            str: Editor name ∈ {"Code-Insiders", "Code"}. Always returns valid name.

        Examples:
            ```python
            editor = detector.detect_installed_editor()
            # "Code-Insiders" if ~/.config/Code - Insiders/User exists
            ```

        Technical: O(n) where n=SUPPORTED_EDITORS length (2). 1-2 exists() calls.
        """
        for editor in self.SUPPORTED_EDITORS:
            config_dir = self.path_resolver.get_vscode_config_dir(editor)
            if config_dir and self.fs.exists(config_dir):
                return editor

        # Default fallback if no editor config found
        return self.DEFAULT_EDITOR


class AgentInstaller:
    """Core installer: copies agent files to local or global destinations.

    Business: Main installation logic. Supports local (.github/) for per-repo
    customization and global (VS Code prompts/) for system-wide availability.
    Provides dry-run mode for safe preview.

    Attributes:
        SOURCE_FILES: Single source of truth for agent file paths.
        LOCAL_FILES: FileMapping list for local install (agents/ + instructions/).
        GLOBAL_FILES: FileMapping list for global install (prompts/).
        agent_files_dir: Source directory containing files to install.
        fs: FileSystemProtocol for I/O operations.
        path_resolver: PathResolver for target path resolution.
        editor_detector: EditorDetector for auto-detection.
        logger: Logger for user feedback.

    Technical: Stateless after init. All methods return InstallationResult.
    Uses DI for testability - no direct I/O, all via protocols.
    """

    # Single source of truth for agent file paths (relative to agent_files_dir)
    SOURCE_FILES: list[str] = [
        "agents/copilot_confirm.agent.md",
        "instructions/confirmation_workflow.instructions.md",
    ]

    # Local install: preserve directory structure under .github/
    LOCAL_FILES: list[FileMapping] = [FileMapping(src, src) for src in SOURCE_FILES]

    # Global install: flatten to prompts/ directory
    GLOBAL_FILES: list[FileMapping] = [
        FileMapping(src, f"prompts/{Path(src).name}") for src in SOURCE_FILES
    ]

    def __init__(
        self,
        agent_files_dir: Path,
        fs: FileSystemProtocol,
        path_resolver: PathResolver,
        editor_detector: EditorDetector,
        logger: logging.Logger,
    ):
        """Initialize agent installer with all required dependencies.

        Business: Wires up installer for local/global agent file installation.
        Uses DI pattern for testability - all I/O via injected protocols.

        Args:
            agent_files_dir: Directory containing agent files to install.
            fs: File system operations provider for read/write/mkdir.
            path_resolver: Path resolution service for target directories.
            editor_detector: Editor detection service for --global auto-detect.
            logger: Logger instance for user feedback during install.
        """
        self.agent_files_dir = agent_files_dir
        self.fs = fs
        self.path_resolver = path_resolver
        self.editor_detector = editor_detector
        self.logger = logger

    def _validate_source_files(self) -> bool:
        """Validate that the agent files directory exists before installation.

        Business: Fail-fast validation prevents confusing errors during file
        copy phase. Users see clear error message if package is corrupted.

        Returns:
            True if agent_files_dir exists and is accessible, False otherwise.
            Logs error message with path on failure.
        """
        if not self.fs.exists(self.agent_files_dir):
            self.logger.error(
                f"❌ Error: Agent files directory not found: {self.agent_files_dir}"
            )
            return False
        return True

    def install_files(
        self, target_dir: Path, files: list[FileMapping], dry_run: bool = False
    ) -> InstallationResult:
        """Copy agent files from source to target directory.

        Validates source dir exists, creates target dirs as needed, copies files.
        Dry-run mode logs planned operations w/o filesystem writes.

        Business: Core installation logic for both local and global targets.
        Provides preview mode to verify paths before committing changes.

        Args:
            target_dir: Destination base directory (e.g., ~/.config/Code/User).
            files: FileMapping list w/ src_relative and dst_relative paths.
            dry_run: If True, log planned copies w/o writing. Default: False.

        Returns:
            InstallationResult: success=True if ≥1 file copied (or dry-run),
            files_copied count, target_dir, error_message if failed.

        Raises:
            None (errors captured in InstallationResult.error_message).

        Examples:
            ```python
            result = installer.install_files(Path("/target"), mappings, dry_run=True)
            if result.success:
                print(f"Would copy {result.files_copied} files")
            ```

        Technical: O(n) where n=len(files). Creates dirs w/ parents=True.
        """
        if not self._validate_source_files():
            return InstallationResult(
                success=False,
                files_copied=0,
                target_dir=target_dir,
                error_message="Agent files directory not found",
            )

        self.logger.info(f"📁 Target directory: {target_dir}")

        if dry_run:
            self._print_dry_run(target_dir, files)
            return InstallationResult(
                success=True,
                files_copied=len(files),
                target_dir=target_dir,
            )

        return self._perform_installation(target_dir, files)

    def _print_dry_run(self, target_dir: Path, files: list[FileMapping]) -> None:
        """Display preview of files that would be copied during installation.

        Business: Enables --dry-run mode for users to verify installation paths
        before committing changes. Essential for cautious deployments.

        Args:
            target_dir: Destination base directory for installation.
            files: FileMapping list with source and destination paths.

        Returns:
            None (outputs to logger).
        """
        self.logger.info("\n🔍 DRY RUN - Files that would be copied:")
        for file_map in files:
            src = self.agent_files_dir / file_map.src_relative
            dst = target_dir / file_map.dst_relative
            self.logger.info(f"  {src} -> {dst}")

    def _perform_installation(
        self, target_dir: Path, files: list[FileMapping]
    ) -> InstallationResult:
        """Execute file copy operations w/ error handling.

        Creates target directories, copies each file, logs progress w/ emoji.
        Skips missing source files w/ warning. Catches OSError for graceful failure.

        Business: Atomic-ish installation - creates all dirs first, then copies.
        Partial success possible (some files copied before error).

        Args:
            target_dir: Destination base dir. Subdirs created as needed.
            files: FileMapping list. Missing sources skipped w/ warning.

        Returns:
            InstallationResult: success=True if ≥1 file copied, files_copied count,
            error_message on OSError or zero copies.

        Examples:
            ```python
            result = installer._perform_installation(target, mappings)
            # Logs: ✅ Copied: agents/copilot_confirm.agent.md
            ```

        Technical: O(n) copies. Uses shutil.copy2 (preserves metadata). ~1ms/file.
        """
        copied = 0
        failed = 0
        try:
            # Create target directories
            for file_map in files:
                dst = target_dir / file_map.dst_relative
                self.fs.mkdir(dst.parent, parents=True, exist_ok=True)

            # Copy files
            for file_map in files:
                src = self.agent_files_dir / file_map.src_relative
                dst = target_dir / file_map.dst_relative

                if not self.fs.exists(src):
                    self.logger.warning(f"⚠️  Warning: Source file not found: {src}")
                    failed += 1
                    continue

                self.fs.copy_file(src, dst)
                self.logger.info(f"✅ Copied: {file_map.dst_relative}")
                copied += 1

            if copied > 0:
                self.logger.info(
                    f"\n🎉 Successfully installed {copied} file(s) to {target_dir}"
                )
                return InstallationResult(
                    success=True,
                    files_copied=copied,
                    target_dir=target_dir,
                    files_failed=failed,
                )

            self.logger.error("\n❌ No files were copied")
            return InstallationResult(
                success=False,
                files_copied=0,
                target_dir=target_dir,
                error_message="No files were copied",
                files_failed=failed,
            )

        except OSError as e:
            error_msg = f"Error during installation: {e}"
            self.logger.error(f"❌ {error_msg}")
            return InstallationResult(
                success=False,
                files_copied=copied,
                target_dir=target_dir,
                error_message=error_msg,
                files_failed=len(files) - copied,
            )

    def install_local(self, dry_run: bool = False) -> InstallationResult:
        """Install agent files to repo-local .github directory.

        Copies agents to .github/agents/ and instructions to .github/instructions/.
        Auto-detects git repo root, falls back to cwd if not in repo.

        Business: Enables per-repo Copilot customization. Files tracked in git
        for team sharing. Overrides global agents when present.

        Args:
            dry_run: If True, preview installation w/o writing. Default: False.

        Returns:
            InstallationResult: success, files_copied (typically 2), target_dir.

        Examples:
            ```python
            result = installer.install_local(dry_run=True)
            # Logs: 📁 Target directory: /home/user/myrepo/.github
            ```

        Technical: Calls get_local_install_dir() + install_files(). O(d+n).
        """
        target_dir = self.path_resolver.get_local_install_dir()
        self.logger.info("📦 Installing locally to repository...")
        return self.install_files(target_dir, self.LOCAL_FILES, dry_run)

    def install_global(
        self, editor: str | None = None, dry_run: bool = False
    ) -> InstallationResult:
        """Install agent files globally to VS Code config prompts/ directory.

        Copies agents and instructions to User/prompts/ for system-wide availability.
        Auto-detects editor if not specified, preferring Insiders.

        Business: Enables Copilot customization across all workspaces. Files
        available to all repos w/o per-repo setup. Use --insiders for Insiders.

        Args:
            editor: "Code" or "Code-Insiders". Auto-detected if None.
            dry_run: If True, preview installation w/o writing. Default: False.

        Returns:
            InstallationResult: success, files_copied, target_dir, error_message
            if editor config dir not found.

        Examples:
            ```python
            result = installer.install_global(editor="Code-Insiders", dry_run=True)
            # Logs: 🌍 Installing globally for Code-Insiders...
            ```

        Technical: Calls get_vscode_config_dir() + install_files(). O(n) copies.
        """
        if editor is None:
            editor = self.editor_detector.detect_installed_editor()
            self.logger.info(f"🔍 Auto-detected editor: {editor}")

        config_dir = self.path_resolver.get_vscode_config_dir(editor)

        if config_dir is None or not self.fs.exists(config_dir):
            error_msg = f"Could not find {editor} configuration directory"
            self.logger.error(f"❌ Error: {error_msg}")
            self.logger.error(f"   Expected location: {config_dir}")
            self.logger.info(
                "\n💡 Tip: Use --insiders flag to install for VS Code Insiders"
            )
            return InstallationResult(
                success=False,
                files_copied=0,
                target_dir=config_dir or Path(),
                error_message=error_msg,
            )

        self.logger.info(f"🌍 Installing globally for {editor}...")
        return self.install_files(config_dir, self.GLOBAL_FILES, dry_run)


# ============================================================================
# Factory Functions
# ============================================================================


def create_installer(
    agent_files_dir: Path | None = None,
    logger: logging.Logger | None = None,
) -> AgentInstaller:
    """Factory: Create AgentInstaller w/ production dependencies.

    Wires up RealFileSystem, RealEnvironment, PathResolver, EditorDetector.
    Auto-detects agent_files_dir from package location if not specified.

    Business: Single entry point for programmatic installation. Handles all
    dependency wiring so callers just call install_local() or install_global().

    Args:
        agent_files_dir: Source dir w/ agents/ and instructions/. Default:
            <package_dir>/agent_files/.
        logger: Logger instance. Default: creates via setup_logging().

    Returns:
        AgentInstaller: Fully configured installer ready for install_*() calls.

    Raises:
        ValueError: If auto-detected OS unsupported (via PathResolver).

    Examples:
        ```python
        installer = create_installer()
        result = installer.install_global(editor="Code-Insiders")
        ```

    Technical: O(1). No I/O during construction. Dependencies injected for testability.
    """
    if agent_files_dir is None:
        agent_files_dir = Path(__file__).parent / "agent_files"

    if logger is None:
        logger = setup_logging()

    fs = RealFileSystem()
    env = RealEnvironment()

    path_resolver = PathResolver(env, fs)
    editor_detector = EditorDetector(path_resolver, fs)

    return AgentInstaller(
        agent_files_dir=agent_files_dir,
        fs=fs,
        path_resolver=path_resolver,
        editor_detector=editor_detector,
        logger=logger,
    )


# ============================================================================
# CLI Entry Point
# ============================================================================


def main() -> int:
    """CLI entry point for copilot-confirm installation → exit code.

    Parses args, configures logging, creates installer, executes install.
    Returns exit code for testability (caller handles sys.exit).

    Business: Provides user-friendly CLI for installing Copilot agents.
    Supports local (default) and global modes, dry-run preview, debug logging.

    Args:
        None (reads sys.argv)

    Returns:
        int: Exit code. 0=success, 1=failure or invalid args.

    Raises:
        SystemExit: Only from argparse --help/--version.

    Examples:
        ```python
        # Direct testing
        code = main()
        assert code == 0
        ```

        ```bash
        copilot-confirm --global --insiders --dry-run
        copilot-confirm --local --log-level DEBUG
        ```

    Technical: Uses argparse. Mutually exclusive --global/--local enforced.
    """
    from .__version__ import __version__

    parser = argparse.ArgumentParser(
        description="Install Copilot Confirm agent files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Install locally to current repository (default)
  copilot-confirm

  # Install globally to VS Code
  copilot-confirm --global

  # Install globally to VS Code Insiders
  copilot-confirm --global --insiders

  # Dry run to see what would be installed
  copilot-confirm --global --dry-run

  # Enable debug logging
  copilot-confirm --log-level DEBUG

  # Save logs to file
  copilot-confirm --global --log-file install.log
        """,
    )

    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program version and exit",
    )

    parser.add_argument(
        "--global",
        "-g",
        dest="install_global",
        action="store_true",
        help="Install globally to VS Code configuration directory (default: local)",
    )

    parser.add_argument(
        "--local",
        "-l",
        dest="install_local",
        action="store_true",
        help="Install locally to .github directory (default)",
    )

    parser.add_argument(
        "--insiders",
        "-i",
        action="store_true",
        help="Install for VS Code Insiders instead of stable VS Code",
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be installed without actually copying files",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO)",
    )

    parser.add_argument(
        "--log-file",
        type=Path,
        help="Write logs to specified file in addition to console",
    )

    args = parser.parse_args()

    # Can't specify both
    if args.install_global and args.install_local:
        print("❌ Error: Cannot specify both --global and --local")
        return 1

    # Configure logging
    logger = setup_logging(level=args.log_level, log_file=args.log_file)

    # Create installer with production dependencies
    installer = create_installer(logger=logger)

    # Show system info
    logger.info(f"🖥️  System: {platform.system()}")
    logger.info("")

    # Perform installation
    if args.install_global:
        editor = (
            EditorDetector.SUPPORTED_EDITORS[0]  # Code-Insiders
            if args.insiders
            else EditorDetector.DEFAULT_EDITOR  # Code
        )
        result = installer.install_global(editor, args.dry_run)
    else:
        result = installer.install_local(args.dry_run)

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
