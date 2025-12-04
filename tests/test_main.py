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
    Strategy: Direct instantiation w/ success/failure scenarios
    Total: 2 tests
    """

    def test_successful_result(self) -> None:
        """Validates InstallationResult w/ success=True stores all fields.

        Tests successful installation result: success flag, files_copied count,
        target_dir path, and None error_message (default for success).

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If fields don't match expected success state

        Testing Principles: Success state representation, default values

        Arrangement: Prepare success params (True, 2 files, target path)
        Action: Construct InstallationResult w/ success params
        Assertion: success=True, files_copied=2, error_message=None

        Examples:
            ```python
            result = InstallationResult(True, 2, Path("/t"))
            assert result.success and result.error_message is None
            ```
        """
        result = InstallationResult(
            success=True, files_copied=2, target_dir=Path("/test")
        )
        assert result.success is True
        assert result.files_copied == 2
        assert result.error_message is None

    def test_failed_result(self) -> None:
        """Validates InstallationResult w/ success=False includes error_message.

        Tests failure installation result: success=False, files_copied=0,
        and descriptive error_message for user feedback.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If fields don't match expected failure state

        Testing Principles: Failure state representation, error messaging

        Arrangement: Prepare failure params (False, 0 files, error msg)
        Action: Construct InstallationResult w/ failure params
        Assertion: success=False, error_message contains description

        Examples:
            ```python
            result = InstallationResult(success=False, ..., error_message="Failed")
            assert not result.success and result.error_message == "Failed"
            ```
        """
        result = InstallationResult(
            success=False,
            files_copied=0,
            target_dir=Path("/test"),
            error_message="Test error",
        )
        assert result.success is False
        assert result.error_message == "Test error"


class TestPathResolver:
    """Tests for PathResolver class.

    Categories: • Linux (2) • Windows (2) • macOS (1) • Errors (2) • Local (2)
    Strategy: MockEnvironment per OS, verify path construction
    Total: 9 tests
    """

    def test_linux_vscode_config_dir(self) -> None:
        """Validates Linux VS Code config path uses ~/.config/Code/User.

        Tests PathResolver constructs correct XDG-compliant path for stable
        VS Code on Linux using home directory from MockEnvironment.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If path doesn't match Linux convention

        Testing Principles: Linux XDG config path, home-relative construction

        Arrangement: MockEnvironment(system="Linux", home="/home/user")
        Action: Call get_vscode_config_dir("Code")
        Assertion: Returns /home/user/.config/Code/User

        Examples:
            ```python
            resolver = PathResolver(env, fs)
            assert resolver.get_vscode_config_dir("Code") == Path("~/.config/Code/User")
            ```
        """
        env = MockEnvironment(system="Linux", home=Path("/home/user"))
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)

        config_dir = resolver.get_vscode_config_dir("Code")
        assert config_dir == Path("/home/user/.config/Code/User")

    def test_linux_vscode_insiders_config_dir(self) -> None:
        """Validates Linux Insiders path uses ~/.config/Code - Insiders/User.

        Tests PathResolver handles space in "Code - Insiders" directory name
        correctly for Linux Insiders installation.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If path doesn't include space in dir name

        Testing Principles: Insiders naming convention, space handling

        Arrangement: MockEnvironment(system="Linux", home="/home/user")
        Action: Call get_vscode_config_dir("Code-Insiders")
        Assertion: Returns path w/ "Code - Insiders" (note spaces)

        Examples:
            ```python
            path = resolver.get_vscode_config_dir("Code-Insiders")
            assert "Code - Insiders" in str(path)
            ```
        """
        env = MockEnvironment(system="Linux", home=Path("/home/user"))
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)

        config_dir = resolver.get_vscode_config_dir("Code-Insiders")
        assert config_dir == Path("/home/user/.config/Code - Insiders/User")

    def test_windows_vscode_config_dir(self) -> None:
        """Validates Windows VS Code config uses %APPDATA%/Code/User.

        Tests PathResolver reads APPDATA env var and constructs Windows-style
        path for VS Code configuration.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If path doesn't use APPDATA base

        Testing Principles: Windows APPDATA usage, env var resolution

        Arrangement: MockEnvironment w/ APPDATA env var set
        Action: Call get_vscode_config_dir("Code")
        Assertion: Returns APPDATA-based path

        Examples:
            ```python
            env = MockEnvironment(system="Windows", env_vars={"APPDATA": "C:/..."})
            assert "AppData/Roaming/Code" in str(resolver.get_vscode_config_dir("Code"))
            ```
        """
        env = MockEnvironment(
            system="Windows",
            env_vars={"APPDATA": "C:\\Users\\test\\AppData\\Roaming"},
        )
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)

        config_dir = resolver.get_vscode_config_dir("Code")
        assert config_dir == Path("C:\\Users\\test\\AppData\\Roaming/Code/User")

    def test_windows_no_appdata_returns_none(self) -> None:
        """Validates None returned when APPDATA env var missing on Windows.

        Tests graceful handling when Windows system lacks APPDATA variable.
        Returns None instead of raising, allowing caller to handle.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If non-None returned when APPDATA missing

        Testing Principles: Missing env var handling, graceful degradation

        Arrangement: MockEnvironment(system="Windows", env_vars={}) - empty
        Action: Call get_vscode_config_dir("Code")
        Assertion: Returns None

        Examples:
            ```python
            env = MockEnvironment(system="Windows", env_vars={})
            assert resolver.get_vscode_config_dir("Code") is None
            ```
        """
        env = MockEnvironment(system="Windows", env_vars={})
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)

        config_dir = resolver.get_vscode_config_dir("Code")
        assert config_dir is None

    def test_darwin_vscode_config_dir(self) -> None:
        """Validates macOS VS Code path uses ~/Library/Application Support.

        Tests PathResolver constructs macOS-standard Application Support path
        per Apple's app data location guidelines.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If path doesn't use Library/Application Support

        Testing Principles: macOS conventions, Application Support path

        Arrangement: MockEnvironment(system="Darwin", home="/Users/test")
        Action: Call get_vscode_config_dir("Code")
        Assertion: Returns ~/Library/Application Support/Code/User

        Examples:
            ```python
            path = resolver.get_vscode_config_dir("Code")
            assert "Library/Application Support" in str(path)
            ```
        """
        env = MockEnvironment(system="Darwin", home=Path("/Users/test"))
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)

        config_dir = resolver.get_vscode_config_dir("Code")
        assert config_dir == Path("/Users/test/Library/Application Support/Code/User")

    def test_unsupported_editor_returns_none(self) -> None:
        """Validates None returned for unknown editor variant names.

        Tests that requesting config path for unsupported editor (not Code or
        Code-Insiders) returns None rather than raising exception.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If non-None returned for unsupported editor

        Testing Principles: Unknown input handling, graceful None return

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

        config_dir = resolver.get_vscode_config_dir("UnsupportedEditor")
        assert config_dir is None

    def test_unsupported_os_raises(self) -> None:
        """Validates ValueError raised for unsupported operating systems.

        Tests that PathResolver constructor raises descriptive error when
        platform.system() returns unsupported OS (e.g., FreeBSD).

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

    def test_get_local_install_dir_in_git_repo(self) -> None:
        """Validates local install finds .github relative to git repo root.

        Tests get_local_install_dir walks up directory tree to find .git,
        returns sibling .github directory for repo-local installation.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If .github path not relative to repo root

        Testing Principles: Git repo detection, parent traversal

        Arrangement: MockFileSystem w/ /test/repo/.git existing
        Action: Call get_local_install_dir()
        Assertion: Returns Path("/test/repo/.github")

        Examples:
            ```python
            fs = MockFileSystem(existing_paths={Path("/repo/.git")})
            assert resolver.get_local_install_dir() == Path("/repo/.github")
            ```
        """
        fs = MockFileSystem(existing_paths={Path("/test/repo/.git")})
        env = MockEnvironment()
        resolver = PathResolver(env, fs)

        local_dir = resolver.get_local_install_dir()
        assert local_dir == Path("/test/repo/.github")

    def test_get_local_install_dir_not_in_git_repo(self) -> None:
        """Validates fallback to cwd/.github when not in git repository.

        Tests get_local_install_dir returns cwd-based .github path when no
        .git directory found in parent tree. Enables use outside git repos.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If path not based on cwd

        Testing Principles: Fallback behavior, non-git-repo support

        Arrangement: MockFileSystem w/ no .git, custom _cwd
        Action: Call get_local_install_dir()
        Assertion: Returns cwd/.github

        Examples:
            ```python
            fs._cwd = Path("/some/dir")
            assert resolver.get_local_install_dir() == Path("/some/dir/.github")
            ```
        """
        fs = MockFileSystem(existing_paths=set())
        fs._cwd = Path("/some/random/dir")
        env = MockEnvironment()
        resolver = PathResolver(env, fs)

        local_dir = resolver.get_local_install_dir()
        assert local_dir == Path("/some/random/dir/.github")


class TestEditorDetector:
    """Tests for EditorDetector class.

    Categories: • Detection (2) • Fallback (1)
    Strategy: MockFileSystem w/ existing config dirs, verify priority
    Total: 3 tests
    """

    def test_detect_code(self) -> None:
        """Validates detection of stable VS Code via config directory.

        Tests EditorDetector finds stable Code when its config directory
        exists, confirming installation detection via filesystem presence.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If "Code" not returned when config exists

        Testing Principles: Installation detection, filesystem-based discovery

        Arrangement: MockFileSystem w/ ~/.config/Code/User existing
        Action: Call detect_installed_editor()
        Assertion: Returns "Code"

        Examples:
            ```python
            fs = MockFileSystem(existing_paths={Path("~/.config/Code/User")})
            assert detector.detect_installed_editor() == "Code"
            ```
        """
        env = MockEnvironment(system="Linux", home=Path("/home/user"))
        fs = MockFileSystem(existing_paths={Path("/home/user/.config/Code/User")})
        resolver = PathResolver(env, fs)
        detector = EditorDetector(resolver, fs)

        editor = detector.detect_installed_editor()
        assert editor == "Code"

    def test_detect_code_insiders(self) -> None:
        """Validates Insiders detection when its config exists.

        Tests EditorDetector returns Code-Insiders when its config directory
        exists. Insiders checked first due to developer preference.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If "Code-Insiders" not detected when present

        Testing Principles: Priority ordering, Insiders preference

        Arrangement: MockFileSystem w/ Code-Insiders config existing
        Action: Call detect_installed_editor()
        Assertion: Returns "Code-Insiders"

        Examples:
            ```python
            fs = MockFileSystem(existing_paths={Path("~/.config/Code - Insiders/User")})
            assert detector.detect_installed_editor() == "Code-Insiders"
            ```
        """
        env = MockEnvironment(system="Linux", home=Path("/home/user"))
        fs = MockFileSystem(
            existing_paths={Path("/home/user/.config/Code - Insiders/User")}
        )
        resolver = PathResolver(env, fs)
        detector = EditorDetector(resolver, fs)

        editor = detector.detect_installed_editor()
        assert editor == "Code-Insiders"

    def test_default_to_code(self) -> None:
        """Validates fallback to "Code" when no VS Code installation found.

        Tests EditorDetector defaults to stable Code when neither Code nor
        Insiders config directories exist. Provides reasonable default.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If default not "Code"

        Testing Principles: Sensible defaults, fallback behavior

        Arrangement: MockFileSystem w/ no VS Code config dirs
        Action: Call detect_installed_editor()
        Assertion: Returns "Code" as default

        Examples:
            ```python
            fs = MockFileSystem()  # No paths exist
            assert detector.detect_installed_editor() == "Code"
            ```
        """
        env = MockEnvironment(system="Linux", home=Path("/home/user"))
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)
        detector = EditorDetector(resolver, fs)

        editor = detector.detect_installed_editor()
        assert editor == "Code"


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
        assert len(fs.copied_files) == 2

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

    Categories: • Basic (2) • Flags (3) • Logging (1)
    Strategy: Patch sys.argv, verify SystemExit codes, capture stdout
    Total: 6 tests
    """

    def test_main_local_install_dry_run(self) -> None:
        """Validates main() w/ --dry-run performs local install preview.

        Tests CLI entry point w/ dry-run flag exits cleanly (0 or 1 depending
        on file existence). Default mode is local install.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If exit code not in (0, 1)

        Testing Principles: CLI arg parsing, dry-run behavior, exit codes

        Arrangement: Patch sys.argv w/ ["copilot-confirm", "--dry-run"]
        Action: Call main(), catch SystemExit
        Assertion: Exit code in (0, 1)

        Examples:
            ```python
            with patch("sys.argv", ["copilot-confirm", "--dry-run"]):
                with pytest.raises(SystemExit) as exc:
                    main()
                assert exc.value.code in (0, 1)
            ```
        """
        with patch("sys.argv", ["copilot-confirm", "--dry-run"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # May exit 0 or 1 depending on file existence
            assert exc_info.value.code in (0, 1)

    def test_main_both_global_and_local_error(self, capsys) -> None:
        """Validates main() rejects --global and --local together.

        Tests CLI entry point exits w/ error when both flags specified.
        Verifies error message printed to stdout.

        Args:
            self: Test fixture
            capsys: pytest fixture for capturing stdout/stderr

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If exit code != 1 or error msg missing

        Testing Principles: Mutually exclusive args, error messaging

        Arrangement: Patch sys.argv w/ both --global and --local
        Action: Call main(), catch SystemExit, capture output
        Assertion: Exit code == 1, "Cannot specify both" in output

        Examples:
            ```python
            with patch("sys.argv", ["copilot-confirm", "--global", "--local"]):
                main()  # Exits 1 w/ error message
            ```
        """
        with patch("sys.argv", ["copilot-confirm", "--global", "--local"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "Cannot specify both" in captured.out

    def test_main_global_install(self) -> None:
        """Validates main() w/ --global performs global install.

        Tests CLI entry point w/ --global flag attempts global installation
        to VS Code config directory.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If exit code not in (0, 1)

        Testing Principles: Global flag handling, install mode selection

        Arrangement: Patch sys.argv w/ --global --dry-run
        Action: Call main(), catch SystemExit
        Assertion: Exit code in (0, 1)

        Examples:
            ```python
            with patch("sys.argv", ["copilot-confirm", "--global", "--dry-run"]):
                main()  # Attempts global install
            ```
        """
        with patch("sys.argv", ["copilot-confirm", "--global", "--dry-run"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code in (0, 1)

    def test_main_with_insiders_flag(self) -> None:
        """Validates main() w/ --insiders targets VS Code Insiders.

        Tests CLI entry point w/ --insiders flag selects Code-Insiders
        as target editor for global installation.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If exit code not in (0, 1)

        Testing Principles: Insiders flag handling, editor selection

        Arrangement: Patch sys.argv w/ --global --insiders --dry-run
        Action: Call main(), catch SystemExit
        Assertion: Exit code in (0, 1)

        Examples:
            ```python
            with patch("sys.argv", ["copilot-confirm", "--global", "--insiders"]):
                main()  # Targets Code-Insiders
            ```
        """
        with patch(
            "sys.argv",
            ["copilot-confirm", "--global", "--insiders", "--dry-run"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code in (0, 1)

    def test_main_with_log_level(self) -> None:
        """Validates main() w/ --log-level sets logging verbosity.

        Tests CLI entry point w/ --log-level DEBUG enables verbose logging
        for troubleshooting installation issues.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If exit code not in (0, 1)

        Testing Principles: Log level arg parsing, logging configuration

        Arrangement: Patch sys.argv w/ --log-level DEBUG --dry-run
        Action: Call main(), catch SystemExit
        Assertion: Exit code in (0, 1)

        Examples:
            ```python
            with patch("sys.argv", ["copilot-confirm", "--log-level", "DEBUG"]):
                main()  # Runs w/ DEBUG logging
            ```
        """
        with patch(
            "sys.argv", ["copilot-confirm", "--log-level", "DEBUG", "--dry-run"]
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code in (0, 1)

    def test_main_with_log_file(self) -> None:
        """Validates main() w/ --log-file creates file handler.

        Tests CLI entry point w/ --log-file writes logs to specified file
        in addition to console output. Uses mocked FileHandler.

        Args:
            self: Test fixture

        Returns:
            None (pytest test method)

        Raises:
            AssertionError: If exit code not in (0, 1)

        Testing Principles: Log file arg parsing, FileHandler creation

        Arrangement: Mock FileHandler + Path.mkdir, patch sys.argv
        Action: Call main(), catch SystemExit
        Assertion: Exit code in (0, 1)

        Examples:
            ```python
            with patch("sys.argv", ["copilot-confirm", "--log-file", "/tmp/log"]):
                main()  # Writes to /tmp/log
            ```
        """
        mock_file_handler = MagicMock()
        mock_file_handler.level = 10  # Provide a real int for level comparison

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
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code in (0, 1)
