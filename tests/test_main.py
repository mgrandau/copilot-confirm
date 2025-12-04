"""Tests for the install module."""

from pathlib import Path

import pytest

from copilot_confirm import InstallationResult, create_installer
from copilot_confirm.install import (
    AgentInstaller,
    EditorDetector,
    FileMapping,
    PathResolver,
    setup_logging,
)


class MockFileSystem:
    """Mock file system for testing."""

    def __init__(self, existing_paths: set[Path] | None = None):
        self.existing_paths = existing_paths or set()
        self.created_dirs: list[Path] = []
        self.copied_files: list[tuple[Path, Path]] = []
        self._cwd = Path("/test/repo")

    def exists(self, path: Path) -> bool:
        return path in self.existing_paths

    def mkdir(
        self, path: Path, parents: bool = False, exist_ok: bool = False  # noqa: ARG002
    ) -> None:
        self.created_dirs.append(path)

    def copy_file(self, src: Path, dst: Path) -> None:
        self.copied_files.append((src, dst))

    def get_cwd(self) -> Path:
        return self._cwd


class MockEnvironment:
    """Mock environment for testing."""

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
    """Tests for FileMapping dataclass."""

    def test_file_mapping_creation(self) -> None:
        mapping = FileMapping("src/file.md", "dst/file.md")
        assert mapping.src_relative == "src/file.md"
        assert mapping.dst_relative == "dst/file.md"

    def test_file_mapping_is_frozen(self) -> None:
        mapping = FileMapping("src/file.md", "dst/file.md")
        with pytest.raises(AttributeError):
            mapping.src_relative = "new/path.md"  # type: ignore


class TestInstallationResult:
    """Tests for InstallationResult dataclass."""

    def test_successful_result(self) -> None:
        result = InstallationResult(
            success=True, files_copied=2, target_dir=Path("/test")
        )
        assert result.success is True
        assert result.files_copied == 2
        assert result.error_message is None

    def test_failed_result(self) -> None:
        result = InstallationResult(
            success=False,
            files_copied=0,
            target_dir=Path("/test"),
            error_message="Test error",
        )
        assert result.success is False
        assert result.error_message == "Test error"


class TestPathResolver:
    """Tests for PathResolver class."""

    def test_linux_vscode_config_dir(self) -> None:
        env = MockEnvironment(system="Linux", home=Path("/home/user"))
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)

        config_dir = resolver.get_vscode_config_dir("Code")
        assert config_dir == Path("/home/user/.config/Code/User")

    def test_unsupported_os_raises(self) -> None:
        env = MockEnvironment(system="FreeBSD")
        fs = MockFileSystem()

        with pytest.raises(ValueError, match="Unsupported operating system"):
            PathResolver(env, fs)

    def test_get_local_install_dir_in_git_repo(self) -> None:
        fs = MockFileSystem(existing_paths={Path("/test/repo/.git")})
        env = MockEnvironment()
        resolver = PathResolver(env, fs)

        local_dir = resolver.get_local_install_dir()
        assert local_dir == Path("/test/repo/.github")


class TestEditorDetector:
    """Tests for EditorDetector class."""

    def test_detect_code_insiders(self) -> None:
        env = MockEnvironment(system="Linux", home=Path("/home/user"))
        fs = MockFileSystem(
            existing_paths={Path("/home/user/.config/Code - Insiders/User")}
        )
        resolver = PathResolver(env, fs)
        detector = EditorDetector(resolver, fs)

        editor = detector.detect_installed_editor()
        assert editor == "Code-Insiders"

    def test_default_to_code(self) -> None:
        env = MockEnvironment(system="Linux", home=Path("/home/user"))
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)
        detector = EditorDetector(resolver, fs)

        editor = detector.detect_installed_editor()
        assert editor == "Code"


class TestAgentInstaller:
    """Tests for AgentInstaller class."""

    def test_install_local_dry_run(self) -> None:
        agent_files_dir = Path("/test/agent_files")
        fs = MockFileSystem(
            existing_paths={agent_files_dir, Path("/test/repo/.git")}
        )
        env = MockEnvironment()
        resolver = PathResolver(env, fs)
        detector = EditorDetector(resolver, fs)
        logger = setup_logging(level="WARNING")

        installer = AgentInstaller(
            agent_files_dir=agent_files_dir,
            fs=fs,
            path_resolver=resolver,
            editor_detector=detector,
            logger=logger,
        )

        result = installer.install_local(dry_run=True)
        assert result.success is True
        assert len(fs.copied_files) == 0  # Dry run, no files copied


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_basic_logging_setup(self) -> None:
        logger = setup_logging(level="DEBUG", logger_name="test_logger")
        assert logger.level == 10  # DEBUG level
        assert len(logger.handlers) == 1


class TestCreateInstaller:
    """Tests for create_installer factory function."""

    def test_creates_installer_instance(self) -> None:
        installer = create_installer()
        assert isinstance(installer, AgentInstaller)

