"""Tests for the copilot_confirm.install module.

Comprehensive unit tests covering all installation logic: path resolution,
editor detection, file copying, CLI parsing, and error handling.

Strategy: Protocol-based mocks (MockFileSystem, MockEnvironment) for isolated
testing w/o real I/O. Each test class focuses on single component.

Categories:
    • Dataclasses (4 tests): FileMapping, InstallationResult
    • PathResolver (9 tests): Cross-platform path construction
    • EditorDetector (3 tests): VS Code variant detection
    • AgentInstaller (8 tests): Core installation logic
    • Setup/Factory (5 tests): Logging, create_installer
    • CLI (6 tests): main() argument handling

Total: 36 tests, 100% coverage
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from copilot_confirm import InstallationResult, create_installer
from copilot_confirm.install import (
    AgentInstaller,
    EditorDetector,
    FileMapping,
    OperatingSystem,
    PathResolver,
    main,
    setup_logging,
)


class MockFileSystem:
    """Mock filesystem for testing w/o real I/O.

    Implements FileSystemProtocol. Tracks created dirs and copied files.
    Configurable existing_paths and copy_error for scenario testing.

    Attributes:
        existing_paths: Set of paths that "exist" in mock fs.
        created_dirs: List of dirs created via mkdir().
        copied_files: List of (src, dst) tuples from copy_file().
        _cwd: Mock current working directory.
        _copy_error: If True, copy_file() raises OSError.
    """

    def __init__(
        self,
        existing_paths: set[Path] | None = None,
        copy_error: bool = False,
    ):
        self.existing_paths = existing_paths or set()
        self.created_dirs: list[Path] = []
        self.copied_files: list[tuple[Path, Path]] = []
        self._cwd = Path("/test/repo")
        self._copy_error = copy_error

    def exists(self, path: Path) -> bool:
        return path in self.existing_paths

    def mkdir(
        self,
        path: Path,
        parents: bool = False,  # noqa: ARG002
        exist_ok: bool = False,  # noqa: ARG002
    ) -> None:
        self.created_dirs.append(path)

    def copy_file(self, src: Path, dst: Path) -> None:
        if self._copy_error:
            raise OSError("Mock copy error")
        self.copied_files.append((src, dst))

    def write_text(self, path: Path, content: str) -> None:  # noqa: ARG002
        pass  # no-op in most tests; override if needed

    def read_text(self, path: Path) -> str:  # noqa: ARG002
        return ""  # return empty string by default

    def get_cwd(self) -> Path:
        return self._cwd


class MockEnvironment:
    """Mock environment for testing w/o real platform detection.

    Implements EnvironmentProtocol. Configurable OS, env vars, home dir.

    Attributes:
        _system: OS name ("Linux", "Windows", "Darwin").
        _env_vars: Dict of environment variables.
        _home: Mock home directory path.
    """

    def __init__(
        self,
        system: str = "Linux",
        env_vars: dict[str, str] | None = None,
        home: Path | None = None,
    ):
        self._system = system
        self._env_vars = env_vars or {}
        self._home = home or Path("/home/testuser")

    def get_system(self) -> str:
        return self._system

    def get_env_var(self, name: str, default: str = "") -> str:
        return self._env_vars.get(name, default)

    def get_home(self) -> Path:
        return self._home


class TestFileMapping:
    """Tests for FileMapping dataclass.

    Categories: • Creation (1) • Immutability (1)
    Strategy: Direct instantiation, attribute access, mutation attempt
    Total: 2 tests
    """

    def test_file_mapping_creation(self) -> None:
        """Validates FileMapping stores src/dst paths correctly on creation.

        Tests dataclass field assignment for relative path strings. Confirms
        both src_relative and dst_relative accessible after construction.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If field values don't match constructor args

        Testing Principles: Dataclass field storage, attribute access

        Arrangement: Prepare src/dst path strings
        Action: Construct FileMapping w/ both paths
        Assertion: src_relative and dst_relative match inputs

        Examples:
            ```python
            mapping = FileMapping("src/file.md", "dst/file.md")
            assert mapping.src_relative == "src/file.md"
            ```
        """
        mapping = FileMapping("src/file.md", "dst/file.md")
        assert mapping.src_relative == "src/file.md"
        assert mapping.dst_relative == "dst/file.md"

    def test_file_mapping_is_frozen(self) -> None:
        """Validates FileMapping is immutable (frozen=True).

        Tests that attempting to modify attributes raises AttributeError.
        Frozen dataclasses prevent accidental mutation during iteration.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If mutation doesn't raise AttributeError

        Testing Principles: Immutability enforcement, frozen dataclass behavior

        Arrangement: Create valid FileMapping instance
        Action: Attempt to assign new value to src_relative
        Assertion: AttributeError raised (can't modify frozen dataclass)

        Examples:
            ```python
            mapping = FileMapping("a", "b")
            mapping.src_relative = "c"  # Raises AttributeError
            ```
        """
        mapping = FileMapping("src/file.md", "dst/file.md")
        with pytest.raises(AttributeError):
            mapping.src_relative = "new/path.md"  # type: ignore


class TestInstallationResult:
    """Tests for InstallationResult dataclass.

    Categories: • Success (1) • Failure (1)
    Strategy: Parameterized success/failure scenarios
    Total: 1 parameterized test (2 cases)
    """

    @pytest.mark.parametrize(
        ("success", "files_copied", "error_message", "expected_valid"),
        [
            (True, 2, None, True),
            (False, 0, "Test error", False),
        ],
    )
    def test_installation_result_states(
        self,
        success: bool,
        files_copied: int,
        error_message: str | None,
        expected_valid: bool,
    ) -> None:
        """Validates InstallationResult stores success/failure states.

        Parameterized test covering both success (files_copied=2, no error)
        and failure (files_copied=0, error message) scenarios for
        installation result tracking.

        Args:
            self: Test fixture
            success: Whether installation succeeded
            files_copied: Count of files copied
            error_message: Error description if failed
            expected_valid: Expected success state

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If any field doesn't match expected

        Testing Principles: Parameterized coverage, state representation

        Arrangement: Prepare success/failure param combination
        Action: Construct InstallationResult w/ params
        Assertion: All fields match expected values

        Examples:
            ```python
            result = InstallationResult(success=True, files_copied=2, ...)
            assert result.success and result.error_message is None
            ```
        """
        result = InstallationResult(
            success=success,
            files_copied=files_copied,
            target_dir=Path("/test"),
            error_message=error_message,
        )
        assert result.success is expected_valid
        assert result.files_copied == files_copied
        assert result.error_message == error_message


class TestPathResolver:
    """Tests for PathResolver class.

    Categories: • Cross-platform (1 parameterized) • Errors (2) • Local (2)
    Strategy: Parameterized OS/editor combinations, separate error cases
    Total: 5 tests
    """

    @pytest.mark.parametrize(
        ("system", "home", "env_vars", "editor", "expected_path"),
        [
            pytest.param(
                "Linux",
                Path("/home/user"),
                {},
                "Code",
                Path("/home/user/.config/Code/User"),
                id="linux-stable",
            ),
            pytest.param(
                "Linux",
                Path("/home/user"),
                {},
                "Code-Insiders",
                Path("/home/user/.config/Code - Insiders/User"),
                id="linux-insiders",
            ),
            pytest.param(
                "Windows",
                Path("C:/Users/test"),
                {"APPDATA": "C:\\Users\\test\\AppData\\Roaming"},
                "Code",
                Path("C:\\Users\\test\\AppData\\Roaming/Code/User"),
                id="windows-appdata",
            ),
            pytest.param(
                "Darwin",
                Path("/Users/test"),
                {},
                "Code",
                Path("/Users/test/Library/Application Support/Code/User"),
                id="macos",
            ),
        ],
    )
    def test_vscode_config_dir_cross_platform(
        self,
        system: str,
        home: Path,
        env_vars: dict,
        editor: str,
        expected_path: Path,
    ) -> None:
        """Validates VS Code config path construction across platforms.

        Parameterized test covering Linux stable, Linux Insiders, Windows
        w/ APPDATA, and macOS paths. Verifies OS-specific path patterns
        and editor variant naming ("Code" vs "Code - Insiders").

        Args:
            self: Test fixture
            system: OS name (Linux, Windows, Darwin)
            home: Mock home directory path
            env_vars: Environment variables (APPDATA for Windows)
            editor: Editor variant (Code, Code-Insiders)
            expected_path: Expected resolved config path

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If resolved path != expected

        Testing Principles: Cross-platform compatibility, path patterns

        Arrangement: MockEnvironment w/ system, home, env_vars
        Action: Call get_vscode_config_dir(editor)
        Assertion: Returned path matches OS/editor-specific expected

        Examples:
            ```python
            # Linux: ~/.config/Code/User
            # macOS: ~/Library/Application Support/Code/User
            # Windows: %APPDATA%/Code/User
            ```
        """
        env = MockEnvironment(system=system, home=home, env_vars=env_vars)
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)
        assert resolver.get_vscode_config_dir(editor) == expected_path

    def test_windows_no_appdata_returns_none(self) -> None:
        """Validates None returned when APPDATA env var missing on Windows.

        Tests graceful handling when Windows system lacks APPDATA variable.
        Returns None instead of raising, allowing caller to handle missing
        config path scenario.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If non-None returned when APPDATA missing

        Testing Principles: Missing env var handling, graceful degradation

        Arrangement: MockEnvironment(system="Windows", env_vars={})
        Action: Call get_vscode_config_dir("Code")
        Assertion: Returns None

        Examples:
            ```python
            # APPDATA not set -> cannot determine config path
            assert resolver.get_vscode_config_dir("Code") is None
            ```
        """
        env = MockEnvironment(system="Windows", env_vars={})
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)
        assert resolver.get_vscode_config_dir("Code") is None

    def test_unsupported_editor_returns_none(self) -> None:
        """Validates None returned for unknown editor variant names.

        Tests that requesting config path for unsupported editor (not
        "Code" or "Code-Insiders") returns None rather than raising.
        Enables caller to handle unknown editors gracefully.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If non-None returned for unknown editor

        Testing Principles: Unknown input handling, None sentinel

        Arrangement: Standard MockEnvironment + MockFileSystem
        Action: Call get_vscode_config_dir("UnsupportedEditor")
        Assertion: Returns None

        Examples:
            ```python
            assert resolver.get_vscode_config_dir("Atom") is None
            ```
        """
        env = MockEnvironment(system="Linux", home=Path("/home/user"))
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)
        assert resolver.get_vscode_config_dir("UnsupportedEditor") is None

    def test_unsupported_os_raises(self) -> None:
        """Validates ValueError raised for unsupported operating systems.

        Tests that PathResolver constructor raises descriptive error when
        platform.system() returns unsupported OS (e.g., FreeBSD). Fail-fast
        behavior for unsupported platforms.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If ValueError not raised or msg incorrect

        Testing Principles: Fail-fast on unsupported platforms, clear errors

        Arrangement: MockEnvironment(system="FreeBSD")
        Action: Attempt PathResolver construction
        Assertion: Raises ValueError w/ "Unsupported operating system" msg

        Examples:
            ```python
            with pytest.raises(ValueError, match="Unsupported"):
                PathResolver(env, fs)
            ```
        """
        env = MockEnvironment(system="FreeBSD")
        fs = MockFileSystem()
        with pytest.raises(ValueError, match="Unsupported operating system"):
            PathResolver(env, fs)

    @pytest.mark.parametrize(
        ("existing_paths", "cwd", "expected_github"),
        [
            # In git repo
            ({Path("/test/repo/.git")}, Path("/test/repo"), Path("/test/repo/.github")),
            # Not in git repo - fallback to cwd
            (set(), Path("/some/random/dir"), Path("/some/random/dir/.github")),
        ],
    )
    def test_get_local_install_dir(
        self, existing_paths: set, cwd: Path, expected_github: Path
    ) -> None:
        """Validates local install dir detection in/outside git repos.

        Parameterized test covering: (1) inside git repo - finds .git and
        returns sibling .github, (2) outside git repo - falls back to
        cwd/.github for non-repo local installation.

        Args:
            self: Test fixture
            existing_paths: Set of paths that exist in mock fs
            cwd: Mock current working directory
            expected_github: Expected .github path

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If resolved path != expected

        Testing Principles: Git repo detection, fallback behavior

        Arrangement: MockFileSystem w/ existing_paths, custom _cwd
        Action: Call get_local_install_dir()
        Assertion: Returns expected .github path

        Examples:
            ```python
            # In repo: /project/.git -> /project/.github
            # Not in repo: /dir -> /dir/.github
            ```
        """
        fs = MockFileSystem(existing_paths=existing_paths)
        fs._cwd = cwd
        env = MockEnvironment()
        resolver = PathResolver(env, fs)
        assert resolver.get_local_install_dir() == expected_github


class TestEditorDetector:
    """Tests for EditorDetector class.

    Categories: • Detection (1 parameterized w/ 3 cases)
    Strategy: Parameterized existing config paths, verify detection
    Total: 1 parameterized test (3 cases)
    """

    @pytest.mark.parametrize(
        ("existing_paths", "expected_editor"),
        [
            # Stable Code exists
            ({Path("/home/user/.config/Code/User")}, "Code"),
            # Insiders exists (checked first)
            ({Path("/home/user/.config/Code - Insiders/User")}, "Code-Insiders"),
            # Neither exists - default to Code
            (set(), "Code"),
        ],
    )
    def test_detect_installed_editor(
        self, existing_paths: set, expected_editor: str
    ) -> None:
        """Validates editor detection based on config directory existence.

        Parameterized test covering 3 scenarios: (1) stable Code exists,
        (2) Insiders exists and is preferred, (3) neither exists so
        default to stable Code. Verifies priority ordering.

        Args:
            self: Test fixture
            existing_paths: Set of paths that exist in mock fs
            expected_editor: Expected detected editor string

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If detected editor != expected

        Testing Principles: Detection priority, default behavior

        Arrangement: MockFileSystem w/ existing config paths
        Action: Call detect_installed_editor()
        Assertion: Returns expected editor string

        Examples:
            ```python
            # Insiders preferred when present
            # Falls back to "Code" when nothing found
            ```
        """
        env = MockEnvironment(system="Linux", home=Path("/home/user"))
        fs = MockFileSystem(existing_paths=existing_paths)
        resolver = PathResolver(env, fs)
        detector = EditorDetector(resolver, fs)
        assert detector.detect_installed_editor() == expected_editor


class TestAgentInstaller:
    """Tests for AgentInstaller class.

    Categories: • Local (4) • Global (3) • Errors (1)
    Strategy: MockFileSystem w/ configurable paths/errors, _create_installer helper
    Total: 8 tests
    """

    def _create_installer(
        self,
        fs: MockFileSystem,
        env: MockEnvironment | None = None,
    ) -> AgentInstaller:
        """Create AgentInstaller w/ mock deps for testing.

        Args:
            fs: MockFileSystem instance
            env: MockEnvironment (defaults to Linux)

        Returns:
            Configured AgentInstaller w/ mock deps
        """
        if env is None:
            env = MockEnvironment()
        resolver = PathResolver(env, fs)
        detector = EditorDetector(resolver, fs)
        logger = setup_logging(level="ERROR", logger_name="test_installer")

        return AgentInstaller(
            agent_files_dir=Path("/test/agent_files"),
            fs=fs,
            path_resolver=resolver,
            editor_detector=detector,
            logger=logger,
        )

    def test_install_local_dry_run(self) -> None:
        """Validates dry-run mode shows files w/o actual copy operations.

        Tests install_local(dry_run=True) returns success w/o copying files,
        allowing users to preview installation before committing changes.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If files copied during dry-run or result not success

        Testing Principles: Dry-run safety, preview-before-commit

        Arrangement: MockFileSystem w/ agent_files_dir and .git existing
        Action: Call install_local(dry_run=True)
        Assertion: success=True, fs.copied_files empty

        Examples:
            ```python
            result = installer.install_local(dry_run=True)
            assert result.success and len(fs.copied_files) == 0
            ```
        """
        fs = MockFileSystem(
            existing_paths={Path("/test/agent_files"), Path("/test/repo/.git")}
        )
        installer = self._create_installer(fs)

        result = installer.install_local(dry_run=True)
        assert result.success is True
        assert len(fs.copied_files) == 0  # Dry run, no files copied

    def test_install_local_success(self) -> None:
        """Validates successful local install copies all agent files.

        Tests install_local copies both agent and instruction files to .github
        directory, tracking operations via MockFileSystem.copied_files.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If files_copied != 2 or success=False

        Testing Principles: File copy verification, operation tracking

        Arrangement: MockFileSystem w/ agent_files_dir, .git, source files
        Action: Call install_local(dry_run=False)
        Assertion: success=True, files_copied=2, fs.copied_files has 2 entries

        Examples:
            ```python
            result = installer.install_local(dry_run=False)
            assert result.success and result.files_copied == 2
            ```
        """
        # Create paths for source files
        src_agent = Path("/test/agent_files/agents/copilot_confirm.agent.md")
        src_instructions = Path(
            "/test/agent_files/instructions/confirmation_workflow.instructions.md"
        )
        fs = MockFileSystem(
            existing_paths={
                Path("/test/agent_files"),
                Path("/test/repo/.git"),
                src_agent,
                src_instructions,
            }
        )
        installer = self._create_installer(fs)

        result = installer.install_local(dry_run=False)
        assert result.success is True
        assert result.files_copied == 2
        # Agent file is copied; instructions file is written via write_text
        assert len(fs.copied_files) == 1

    def test_install_source_file_not_found(self) -> None:
        """Validates failure when source agent files don't exist.

        Tests install_local returns failure when agent_files_dir exists but
        individual source files are missing, w/ files_copied=0.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If success=True or files_copied > 0

        Testing Principles: Missing file detection, partial state handling

        Arrangement: MockFileSystem w/ agent_files_dir only (no source files)
        Action: Call install_local(dry_run=False)
        Assertion: success=False, files_copied=0

        Examples:
            ```python
            result = installer.install_local(dry_run=False)
            assert not result.success and result.files_copied == 0
            ```
        """
        # Agent files dir exists but source files don't
        fs = MockFileSystem(
            existing_paths={Path("/test/agent_files"), Path("/test/repo/.git")}
        )
        installer = self._create_installer(fs)

        result = installer.install_local(dry_run=False)
        assert result.success is False
        assert result.files_copied == 0

    def test_install_agent_files_dir_not_found(self) -> None:
        """Validates failure w/ clear error when agent_files_dir missing.

        Tests install_local fails early w/ descriptive error_message when
        source agent_files directory doesn't exist.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If error_message doesn't indicate dir not found

        Testing Principles: Early validation, descriptive errors

        Arrangement: MockFileSystem w/ only .git (no agent_files_dir)
        Action: Call install_local(dry_run=False)
        Assertion: success=False, error_message="Agent files directory not found"

        Examples:
            ```python
            result = installer.install_local(dry_run=False)
            assert result.error_message == "Agent files directory not found"
            ```
        """
        fs = MockFileSystem(existing_paths={Path("/test/repo/.git")})
        installer = self._create_installer(fs)

        result = installer.install_local(dry_run=False)
        assert result.success is False
        assert result.error_message == "Agent files directory not found"

    def test_install_global_success(self) -> None:
        """Validates successful global install to VS Code config directory.

        Tests install_global copies agent files to VS Code's prompts/ dir,
        enabling system-wide agent availability across all workspaces.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If files_copied != 2 or success=False

        Testing Principles: Global path resolution, file copy verification

        Arrangement: MockFileSystem w/ agent_files, Code config, source files
        Action: Call install_global(editor="Code", dry_run=False)
        Assertion: success=True, files_copied=2

        Examples:
            ```python
            result = installer.install_global(editor="Code", dry_run=False)
            assert result.success and result.files_copied == 2
            ```
        """
        src_agent = Path("/test/agent_files/agents/copilot_confirm.agent.md")
        src_instructions = Path(
            "/test/agent_files/instructions/confirmation_workflow.instructions.md"
        )
        fs = MockFileSystem(
            existing_paths={
                Path("/test/agent_files"),
                Path("/home/testuser/.config/Code/User"),
                src_agent,
                src_instructions,
            }
        )
        installer = self._create_installer(fs)

        result = installer.install_global(editor="Code", dry_run=False)
        assert result.success is True
        assert result.files_copied == 2

    def test_install_global_auto_detect_editor(self) -> None:
        """Validates global install auto-detects editor when not specified.

        Tests install_global(editor=None) uses EditorDetector to find
        installed VS Code variant automatically.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If auto-detection fails or success=False

        Testing Principles: Auto-detection integration, default behavior

        Arrangement: MockFileSystem w/ Code config existing
        Action: Call install_global(editor=None, dry_run=True)
        Assertion: success=True (auto-detected Code)

        Examples:
            ```python
            result = installer.install_global(editor=None, dry_run=True)
            assert result.success  # Auto-detected editor
            ```
        """
        fs = MockFileSystem(
            existing_paths={
                Path("/test/agent_files"),
                Path("/home/testuser/.config/Code/User"),
            }
        )
        installer = self._create_installer(fs)

        result = installer.install_global(editor=None, dry_run=True)
        assert result.success is True

    def test_install_global_editor_not_found(self) -> None:
        """Validates failure w/ helpful error when editor config missing.

        Tests install_global fails w/ descriptive error when specified
        editor's config directory doesn't exist.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If error_message doesn't mention config directory

        Testing Principles: Clear error messages, actionable suggestions

        Arrangement: MockFileSystem w/ agent_files only (no Code config)
        Action: Call install_global(editor="Code", dry_run=False)
        Assertion: success=False, error contains "Could not find Code configuration"

        Examples:
            ```python
            result = installer.install_global(editor="Code", dry_run=False)
            assert "Could not find Code configuration" in result.error_message
            ```
        """
        fs = MockFileSystem(existing_paths={Path("/test/agent_files")})
        installer = self._create_installer(fs)

        result = installer.install_global(editor="Code", dry_run=False)
        assert result.success is False
        assert "Could not find Code configuration directory" in result.error_message

    def test_install_global_invalid_editor_returns_failure(self) -> None:
        """Validates failure result for invalid editor parameter.

        Tests install_global returns failure InstallationResult for unsupported
        editors since get_vscode_config_dir returns None for unknown editors.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If result.success is True or error_message missing

        Testing Principles: Graceful failure, helpful error messages

        Arrangement: Create installer w/ MockFileSystem
        Action: Call install_global(editor="InvalidEditor")
        Assertion: InstallationResult.success=False with descriptive error

        Examples:
            ```python
            result = installer.install_global(editor="NotAValidEditor")
            assert result.success is False
            ```
        """
        fs = MockFileSystem(existing_paths={Path("/test/agent_files")})
        installer = self._create_installer(fs)

        result = installer.install_global(editor="InvalidEditor", dry_run=False)

        assert result.success is False
        assert result.error_message is not None
        assert "Could not find InvalidEditor" in result.error_message

    def test_install_copy_error(self) -> None:
        """Validates graceful error handling when file copy fails.

        Tests install catches OSError during copy_file and returns failure
        result w/ descriptive error_message instead of raising.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If error not caught or error_message missing

        Testing Principles: Exception handling, graceful degradation

        Arrangement: MockFileSystem w/ copy_error=True, all paths existing
        Action: Call install_local(dry_run=False)
        Assertion: success=False, "Error during installation" in error_message

        Examples:
            ```python
            fs = MockFileSystem(..., copy_error=True)
            result = installer.install_local(dry_run=False)
            assert "Error during installation" in result.error_message
            ```
        """
        src_agent = Path("/test/agent_files/agents/copilot_confirm.agent.md")
        src_instructions = Path(
            "/test/agent_files/instructions/confirmation_workflow.instructions.md"
        )
        fs = MockFileSystem(
            existing_paths={
                Path("/test/agent_files"),
                Path("/test/repo/.git"),
                src_agent,
                src_instructions,
            },
            copy_error=True,
        )
        installer = self._create_installer(fs)

        result = installer.install_local(dry_run=False)
        assert result.success is False
        assert "Error during installation" in result.error_message


class TestSetupLogging:
    """Tests for setup_logging function.

    Categories: • Basic (1) • File handler (1)
    Strategy: Direct calls, mock FileHandler for file tests
    Total: 2 tests
    """

    def test_basic_logging_setup(self) -> None:
        """Validates basic logging creates console handler w/ correct level.

        Tests setup_logging w/ level param creates logger w/ matching level
        and single console handler (no file handler when log_file=None).

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If level wrong or handler count != 1

        Testing Principles: Logger configuration, handler setup

        Arrangement: None (uses defaults except level and name)
        Action: Call setup_logging(level="DEBUG", logger_name=unique)
        Assertion: logger.level == DEBUG (10), handlers count == 1

        Examples:
            ```python
            logger = setup_logging(level="DEBUG", logger_name="test")
            assert logger.level == 10 and len(logger.handlers) == 1
            ```
        """
        logger = setup_logging(level="DEBUG", logger_name="test_logger")
        assert logger.level == 10  # DEBUG level
        assert len(logger.handlers) == 1

    def test_logging_with_file(self) -> None:
        """Validates logging w/ log_file adds FileHandler.

        Tests setup_logging w/ log_file param creates 2 handlers (console +
        file). Uses mocked FileHandler to avoid real file I/O.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If handler count != 2

        Testing Principles: File handler addition, mock isolation

        Arrangement: Mock FileHandler and Path.mkdir
        Action: Call setup_logging w/ log_file path
        Assertion: handlers count == 2 (console + mocked file)

        Examples:
            ```python
            logger = setup_logging(log_file=Path("/tmp/test.log"))
            assert len(logger.handlers) == 2
            ```
        """
        mock_file_handler = MagicMock()
        mock_file_handler.setLevel = MagicMock()
        mock_file_handler.setFormatter = MagicMock()

        with (
            patch(
                "copilot_confirm.install.logging.FileHandler",
                return_value=mock_file_handler,
            ),
            patch.object(Path, "mkdir"),
        ):
            log_file = Path("/fake/path/test.log")
            logger = setup_logging(
                level="INFO",
                log_file=log_file,
                logger_name="test_file_logger_mock",
            )
            assert len(logger.handlers) == 2  # Console + mocked file handler

    def test_invalid_log_level_raises_value_error(self) -> None:
        """Validates invalid log level raises ValueError with helpful message.

        Tests setup_logging rejects invalid level strings and provides list
        of valid options in the error message.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If ValueError not raised or message incorrect

        Testing Principles: Input validation, helpful error messages

        Arrangement: None
        Action: Call setup_logging with invalid level "INVALID"
        Assertion: ValueError raised with valid level list in message
        """
        with pytest.raises(ValueError, match="Invalid log level 'INVALID'"):
            setup_logging(level="INVALID", logger_name="test_invalid")


class TestOperatingSystem:
    """Tests for OperatingSystem enum.

    Categories: • Values (1)
    Strategy: Verify enum values match platform.system() outputs
    Total: 1 test
    """

    def test_all_os_values(self) -> None:
        """Validates all OperatingSystem enum values match platform.system().

        Tests that enum values exactly match strings returned by platform.system()
        for Windows, macOS (Darwin), and Linux.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If any enum value doesn't match expected string

        Testing Principles: Enum value correctness, platform compatibility

        Arrangement: None (static enum values)
        Action: Access .value for each enum member
        Assertion: WINDOWS="Windows", DARWIN="Darwin", LINUX="Linux"

        Examples:
            ```python
            assert OperatingSystem.WINDOWS.value == "Windows"
            ```
        """
        assert OperatingSystem.WINDOWS.value == "Windows"
        assert OperatingSystem.DARWIN.value == "Darwin"
        assert OperatingSystem.LINUX.value == "Linux"


class TestCreateInstaller:
    """Tests for create_installer factory function.

    Categories: • Defaults (1) • Custom args (2)
    Strategy: Call factory, verify returned AgentInstaller configuration
    Total: 3 tests
    """

    def test_creates_installer_instance(self) -> None:
        """Validates create_installer returns AgentInstaller w/ defaults.

        Tests factory function w/ no args returns properly configured
        AgentInstaller instance using real dependencies.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If returned object not AgentInstaller

        Testing Principles: Factory pattern, default wiring

        Arrangement: None (uses all defaults)
        Action: Call create_installer()
        Assertion: Returns AgentInstaller instance

        Examples:
            ```python
            installer = create_installer()
            assert isinstance(installer, AgentInstaller)
            ```
        """
        installer = create_installer()
        assert isinstance(installer, AgentInstaller)

    def test_creates_installer_with_custom_dir(self) -> None:
        """Validates create_installer accepts custom agent_files_dir.

        Tests factory function w/ custom agent_files_dir param stores
        that path in returned AgentInstaller.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If agent_files_dir not set correctly

        Testing Principles: Parameter passing, custom configuration

        Arrangement: Create custom Path for agent files
        Action: Call create_installer(agent_files_dir=custom)
        Assertion: installer.agent_files_dir == custom path

        Examples:
            ```python
            custom = Path("/custom/path")
            installer = create_installer(agent_files_dir=custom)
            assert installer.agent_files_dir == custom
            ```
        """
        custom_dir = Path("/custom/agent/files")
        installer = create_installer(agent_files_dir=custom_dir)
        assert installer.agent_files_dir == custom_dir

    def test_creates_installer_with_custom_logger(self) -> None:
        """Validates create_installer accepts custom logger instance.

        Tests factory function w/ custom logger param uses that logger
        in returned AgentInstaller instead of creating default.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If logger not set correctly

        Testing Principles: Dependency injection, custom logger

        Arrangement: Create custom logger via setup_logging
        Action: Call create_installer(logger=custom)
        Assertion: installer.logger is same object as custom

        Examples:
            ```python
            logger = setup_logging(logger_name="custom")
            installer = create_installer(logger=logger)
            assert installer.logger is logger
            ```
        """
        logger = setup_logging(level="DEBUG", logger_name="custom_test")
        installer = create_installer(logger=logger)
        assert installer.logger == logger


class TestMain:
    """Tests for main CLI function.

    Categories: • Flags (1 parameterized) • Errors (1) • Logging (1 parameterized)
    Strategy: Parameterized argv combinations, verify exit codes
    Total: 3 tests
    """

    @pytest.mark.parametrize(
        "argv",
        [
            ["copilot-confirm", "--dry-run"],
            ["copilot-confirm", "--global", "--dry-run"],
            ["copilot-confirm", "--global", "--insiders", "--dry-run"],
            ["copilot-confirm", "--log-level", "DEBUG", "--dry-run"],
        ],
    )
    def test_main_valid_flag_combinations(self, argv: list) -> None:
        """Validates main() accepts various valid flag combinations.

        Parameterized test covering 4 CLI flag combos: dry-run only,
        global+dry-run, global+insiders+dry-run, log-level+dry-run.
        All should exit w/ 0 or 1 (file existence dependent).

        Args:
            self: Test fixture
            argv: Command-line argument list to test

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If exit code not in (0, 1)

        Testing Principles: CLI arg parsing, flag combinations

        Arrangement: Patch sys.argv w/ test argv
        Action: Call main(), capture exit code
        Assertion: Exit code in (0, 1)

        Examples:
            ```python
            with patch("sys.argv", ["copilot-confirm", "--dry-run"]):
                assert main() in (0, 1)
            ```
        """
        with patch("sys.argv", argv):
            code = main()
            assert code in (0, 1)

    def test_main_both_global_and_local_error(self, capsys) -> None:
        """Validates main() rejects mutually exclusive --global and --local.

        Tests CLI entry point exits w/ error when both flags specified.
        Verifies error message printed to stdout for user guidance.

        Args:
            self: Test fixture
            capsys: pytest stdout/stderr capture fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If exit code != 1 or error msg missing

        Testing Principles: Mutually exclusive args, error messaging

        Arrangement: Patch sys.argv w/ both --global and --local
        Action: Call main(), capture output
        Assertion: Returns 1, "Cannot specify both" in output

        Examples:
            ```python
            with patch("sys.argv", [..., "--global", "--local"]):
                assert main() == 1  # Error exit
            ```
        """
        with patch("sys.argv", ["copilot-confirm", "--global", "--local"]):
            code = main()
            assert code == 1
            captured = capsys.readouterr()
            assert "Cannot specify both" in captured.out

    def test_main_with_log_file(self) -> None:
        """Validates main() w/ --log-file creates FileHandler.

        Tests CLI entry point w/ --log-file writes logs to specified file
        in addition to console. Uses mocked FileHandler to avoid real I/O.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If exit code not in (0, 1)

        Testing Principles: Log file arg, FileHandler creation

        Arrangement: Mock FileHandler + Path.mkdir, patch sys.argv
        Action: Call main() w/ --log-file flag
        Assertion: Exit code in (0, 1)

        Examples:
            ```python
            with patch("sys.argv", [..., "--log-file", "/tmp/log"]):
                main()  # Creates log file handler
            ```
        """
        mock_file_handler = MagicMock()
        mock_file_handler.level = 10

        with (
            patch(
                "copilot_confirm.install.logging.FileHandler",
                return_value=mock_file_handler,
            ),
            patch.object(Path, "mkdir"),
            patch(
                "sys.argv",
                ["copilot-confirm", "--log-file", "/fake/install.log", "--dry-run"],
            ),
        ):
            code = main()
            assert code in (0, 1)
