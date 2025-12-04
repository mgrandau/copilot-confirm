#!/usr/bin/env python3
"""
Installation script for Copilot Confirm.

Installs agent files (chatmodes and instructions) to either:
- Local: .github/ directory in current repository (default)
- Global: VS Code/Insiders configuration directory
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

# ============================================================================
# Enums
# ============================================================================


class OperatingSystem(Enum):
    """Supported operating systems."""

    WINDOWS = "Windows"
    DARWIN = "Darwin"
    LINUX = "Linux"


# ============================================================================
# Protocols (Dependency Abstractions)
# ============================================================================


class FileSystemProtocol(Protocol):
    """Protocol for file system operations, enabling test mocking."""

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
    """Protocol for environment operations, enabling test mocking."""

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


class RealFileSystem:
    """Real file system implementation for production use."""

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


class RealEnvironment:
    """Real environment implementation for production use."""

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
    """
    Configure logging with console and optional file handlers.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        logger_name: Name of the logger to configure

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create formatter with emoji support
    formatter = logging.Formatter(fmt="%(message)s", datefmt="%Y-%m-%d %H:%M:%S")

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
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


# ============================================================================
# Domain Models
# ============================================================================


@dataclass(frozen=True)
class FileMapping:
    """Represents a file to be copied with source and destination paths."""

    src_relative: str
    dst_relative: str


@dataclass(frozen=True)
class InstallationResult:
    """Result of an installation operation."""

    success: bool
    files_copied: int
    target_dir: Path
    error_message: str | None = None


# ============================================================================
# Core Business Logic
# ============================================================================


class PathResolver:
    """Resolves paths for different installation targets and editors."""

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
        """
        Initialize the path resolver.

        Args:
            env: Environment operations provider
            fs: File system operations provider
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
        """
        Get the VS Code configuration directory for the current OS.

        Args:
            editor: Editor variant name

        Returns:
            Path to the config directory or None if not supported
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
        """
        Get the local .github directory for repository-specific installation.

        Returns:
            Path to .github directory
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
    """Detects installed VS Code variants."""

    SUPPORTED_EDITORS = ["Code", "Code-Insiders"]

    def __init__(self, path_resolver: PathResolver, fs: FileSystemProtocol):
        """
        Initialize the editor detector.

        Args:
            path_resolver: Path resolution service
            fs: File system operations provider
        """
        self.path_resolver = path_resolver
        self.fs = fs

    def detect_installed_editor(self) -> str:
        """
        Auto-detect which VS Code variant is installed.

        Returns:
            Editor name from SUPPORTED_EDITORS
        """
        for editor in self.SUPPORTED_EDITORS:
            config_dir = self.path_resolver.get_vscode_config_dir(editor)
            if config_dir and self.fs.exists(config_dir):
                return editor

        # Default to Code if none found
        return "Code"


class AgentInstaller:
    """Handles installation of agent files to local or global locations."""

    # Files to install
    FILES_TO_INSTALL: list[FileMapping] = [
        FileMapping(
            "chatmodes/copilot_confirm.chatmode.md",
            "prompts/copilot_confirm.chatmode.md",
        ),
        FileMapping(
            "instructions/confirmation_workflow.instructions.md",
            "prompts/confirmation_workflow.instructions.md",
        ),
    ]

    def __init__(
        self,
        agent_files_dir: Path,
        fs: FileSystemProtocol,
        path_resolver: PathResolver,
        editor_detector: EditorDetector,
        logger: logging.Logger,
    ):
        """
        Initialize the agent installer.

        Args:
            agent_files_dir: Directory containing agent files to install
            fs: File system operations provider
            path_resolver: Path resolution service
            editor_detector: Editor detection service
            logger: Logger instance for output
        """
        self.agent_files_dir = agent_files_dir
        self.fs = fs
        self.path_resolver = path_resolver
        self.editor_detector = editor_detector
        self.logger = logger

    def _validate_source_files(self) -> bool:
        """
        Validate that the agent files directory exists.

        Returns:
            True if valid, False otherwise
        """
        if not self.fs.exists(self.agent_files_dir):
            self.logger.error(
                f"❌ Error: Agent files directory not found: {self.agent_files_dir}"
            )
            return False
        return True

    def install_files(
        self, target_dir: Path, dry_run: bool = False
    ) -> InstallationResult:
        """
        Copy agent files to target directory.

        Args:
            target_dir: Destination directory
            dry_run: If True, only simulate the installation

        Returns:
            InstallationResult with operation details
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
            self._print_dry_run(target_dir)
            return InstallationResult(
                success=True,
                files_copied=len(self.FILES_TO_INSTALL),
                target_dir=target_dir,
            )

        return self._perform_installation(target_dir)

    def _print_dry_run(self, target_dir: Path) -> None:
        """Print dry run information."""
        self.logger.info("\n🔍 DRY RUN - Files that would be copied:")
        for file_map in self.FILES_TO_INSTALL:
            src = self.agent_files_dir / file_map.src_relative
            dst = target_dir / file_map.dst_relative
            self.logger.info(f"  {src} -> {dst}")

    def _perform_installation(self, target_dir: Path) -> InstallationResult:
        """
        Perform the actual file installation.

        Args:
            target_dir: Destination directory

        Returns:
            InstallationResult with operation details
        """
        try:
            # Create target directories
            for file_map in self.FILES_TO_INSTALL:
                dst = target_dir / file_map.dst_relative
                self.fs.mkdir(dst.parent, parents=True, exist_ok=True)

            # Copy files
            copied = 0
            for file_map in self.FILES_TO_INSTALL:
                src = self.agent_files_dir / file_map.src_relative
                dst = target_dir / file_map.dst_relative

                if not self.fs.exists(src):
                    self.logger.warning(f"⚠️  Warning: Source file not found: {src}")
                    continue

                self.fs.copy_file(src, dst)
                self.logger.info(f"✅ Copied: {file_map.dst_relative}")
                copied += 1

            if copied > 0:
                self.logger.info(
                    f"\n🎉 Successfully installed {copied} file(s) to {target_dir}"
                )
                return InstallationResult(
                    success=True, files_copied=copied, target_dir=target_dir
                )

            self.logger.error("\n❌ No files were copied")
            return InstallationResult(
                success=False,
                files_copied=0,
                target_dir=target_dir,
                error_message="No files were copied",
            )

        except Exception as e:
            error_msg = f"Error during installation: {e}"
            self.logger.error(f"❌ {error_msg}")
            return InstallationResult(
                success=False,
                files_copied=0,
                target_dir=target_dir,
                error_message=error_msg,
            )

    def install_local(self, dry_run: bool = False) -> InstallationResult:
        """
        Install to local .github directory.

        Args:
            dry_run: If True, only simulate the installation

        Returns:
            InstallationResult with operation details
        """
        target_dir = self.path_resolver.get_local_install_dir()
        self.logger.info("📦 Installing locally to repository...")
        return self.install_files(target_dir, dry_run)

    def install_global(
        self, editor: str | None = None, dry_run: bool = False
    ) -> InstallationResult:
        """
        Install to global VS Code configuration directory.

        Args:
            editor: Specific editor to install for (auto-detected if None)
            dry_run: If True, only simulate the installation

        Returns:
            InstallationResult with operation details
        """
        if editor is None:
            editor = self.editor_detector.detect_installed_editor()
            self.logger.info(f"🔍 Auto-detected editor: {editor}")

        config_dir = self.path_resolver.get_vscode_config_dir(editor)

        if config_dir is None or not self.fs.exists(config_dir):
            error_msg = f"Could not find {editor} configuration directory"
            self.logger.error(f"❌ Error: {error_msg}")
            self.logger.error(f"   Expected location: {config_dir}")
            self.logger.info("\n💡 Tip: You can specify the editor with --editor")
            return InstallationResult(
                success=False,
                files_copied=0,
                target_dir=config_dir or Path(),
                error_message=error_msg,
            )

        self.logger.info(f"🌍 Installing globally for {editor}...")
        return self.install_files(config_dir, dry_run)


# ============================================================================
# Factory Functions
# ============================================================================


def create_installer(
    agent_files_dir: Path | None = None,
    logger: logging.Logger | None = None,
) -> AgentInstaller:
    """
    Create an AgentInstaller with production dependencies.

    Args:
        agent_files_dir: Directory containing agent files (auto-detected if None)
        logger: Logger instance (creates default if None)

    Returns:
        Configured AgentInstaller instance
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


def main() -> None:
    """Main entry point for the installation script."""
    parser = argparse.ArgumentParser(
        description="Install Copilot Confirm agent files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Install locally to current repository (default)
  python -m copilot_confirm.install

  # Install globally to VS Code
  python -m copilot_confirm.install --global

  # Install to specific editor
  python -m copilot_confirm.install --global --editor "Code-Insiders"

  # Dry run to see what would be installed
  python -m copilot_confirm.install --global --dry-run

  # Enable debug logging
  python -m copilot_confirm.install --log-level DEBUG

  # Save logs to file
  python -m copilot_confirm.install --global --log-file install.log
        """,
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
        "--editor",
        "-e",
        choices=["Code", "Code-Insiders"],
        help="Specify which editor to install for (auto-detected if not specified)",
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

    # Default to local if neither specified
    if not args.install_global and args.install_local:
        args.install_local = True

    # Can't specify both
    if args.install_global and args.install_local:
        print("❌ Error: Cannot specify both --global and --local")
        sys.exit(1)

    # Configure logging
    logger = setup_logging(level=args.log_level, log_file=args.log_file)

    # Create installer with production dependencies
    installer = create_installer(logger=logger)

    # Show system info
    env = RealEnvironment()
    logger.info(f"🖥️  System: {env.get_system()}")
    logger.info("")

    # Perform installation
    if args.install_global:
        result = installer.install_global(args.editor, args.dry_run)
    else:
        result = installer.install_local(args.dry_run)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
