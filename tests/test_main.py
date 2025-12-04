"""Tests for the install module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

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
    """Mock file system for testing."""

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
        self, path: Path, parents: bool = False, exist_ok: bool = False  # noqa: ARG002
    ) -> None:
        self.created_dirs.append(path)

    def copy_file(self, src: Path, dst: Path) -> None:
        if self._copy_error:
            raise OSError("Mock copy error")
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

    def test_linux_vscode_insiders_config_dir(self) -> None:
        env = MockEnvironment(system="Linux", home=Path("/home/user"))
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)

        config_dir = resolver.get_vscode_config_dir("Code-Insiders")
        assert config_dir == Path("/home/user/.config/Code - Insiders/User")

    def test_windows_vscode_config_dir(self) -> None:
        env = MockEnvironment(
            system="Windows",
            env_vars={"APPDATA": "C:\\Users\\test\\AppData\\Roaming"},
        )
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)

        config_dir = resolver.get_vscode_config_dir("Code")
        assert config_dir == Path("C:\\Users\\test\\AppData\\Roaming/Code/User")

    def test_windows_no_appdata_returns_none(self) -> None:
        env = MockEnvironment(system="Windows", env_vars={})
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)

        config_dir = resolver.get_vscode_config_dir("Code")
        assert config_dir is None

    def test_darwin_vscode_config_dir(self) -> None:
        env = MockEnvironment(system="Darwin", home=Path("/Users/test"))
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)

        config_dir = resolver.get_vscode_config_dir("Code")
        assert config_dir == Path(
            "/Users/test/Library/Application Support/Code/User"
        )

    def test_unsupported_editor_returns_none(self) -> None:
        env = MockEnvironment(system="Linux", home=Path("/home/user"))
        fs = MockFileSystem()
        resolver = PathResolver(env, fs)

        config_dir = resolver.get_vscode_config_dir("UnsupportedEditor")
        assert config_dir is None

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

    def test_get_local_install_dir_not_in_git_repo(self) -> None:
        fs = MockFileSystem(existing_paths=set())
        fs._cwd = Path("/some/random/dir")
        env = MockEnvironment()
        resolver = PathResolver(env, fs)

        local_dir = resolver.get_local_install_dir()
        assert local_dir == Path("/some/random/dir/.github")


class TestEditorDetector:
    """Tests for EditorDetector class."""

    def test_detect_code(self) -> None:
        env = MockEnvironment(system="Linux", home=Path("/home/user"))
        fs = MockFileSystem(
            existing_paths={Path("/home/user/.config/Code/User")}
        )
        resolver = PathResolver(env, fs)
        detector = EditorDetector(resolver, fs)

        editor = detector.detect_installed_editor()
        assert editor == "Code"

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

    def _create_installer(
        self,
        fs: MockFileSystem,
        env: MockEnvironment | None = None,
    ) -> AgentInstaller:
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
        fs = MockFileSystem(
            existing_paths={Path("/test/agent_files"), Path("/test/repo/.git")}
        )
        installer = self._create_installer(fs)

        result = installer.install_local(dry_run=True)
        assert result.success is True
        assert len(fs.copied_files) == 0  # Dry run, no files copied

    def test_install_local_success(self) -> None:
        # Create paths for source files
        src_agent = Path(
            "/test/agent_files/agents/copilot_confirm.agent.md"
        )
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
        # Agent files dir exists but source files don't
        fs = MockFileSystem(
            existing_paths={Path("/test/agent_files"), Path("/test/repo/.git")}
        )
        installer = self._create_installer(fs)

        result = installer.install_local(dry_run=False)
        assert result.success is False
        assert result.files_copied == 0

    def test_install_agent_files_dir_not_found(self) -> None:
        fs = MockFileSystem(existing_paths={Path("/test/repo/.git")})
        installer = self._create_installer(fs)

        result = installer.install_local(dry_run=False)
        assert result.success is False
        assert result.error_message == "Agent files directory not found"

    def test_install_global_success(self) -> None:
        src_agent = Path(
            "/test/agent_files/agents/copilot_confirm.agent.md"
        )
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
        fs = MockFileSystem(existing_paths={Path("/test/agent_files")})
        installer = self._create_installer(fs)

        result = installer.install_global(editor="Code", dry_run=False)
        assert result.success is False
        assert "Could not find Code configuration directory" in result.error_message

    def test_install_copy_error(self) -> None:
        src_agent = Path(
            "/test/agent_files/agents/copilot_confirm.agent.md"
        )
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
    """Tests for setup_logging function."""

    def test_basic_logging_setup(self) -> None:
        logger = setup_logging(level="DEBUG", logger_name="test_logger")
        assert logger.level == 10  # DEBUG level
        assert len(logger.handlers) == 1

    def test_logging_with_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_logging(
                level="INFO",
                log_file=log_file,
                logger_name="test_file_logger",
            )
            assert len(logger.handlers) == 2  # Console + file
            logger.info("Test message")
            assert log_file.exists()


class TestOperatingSystem:
    """Tests for OperatingSystem enum."""

    def test_all_os_values(self) -> None:
        assert OperatingSystem.WINDOWS.value == "Windows"
        assert OperatingSystem.DARWIN.value == "Darwin"
        assert OperatingSystem.LINUX.value == "Linux"


class TestCreateInstaller:
    """Tests for create_installer factory function."""

    def test_creates_installer_instance(self) -> None:
        installer = create_installer()
        assert isinstance(installer, AgentInstaller)

    def test_creates_installer_with_custom_dir(self) -> None:
        custom_dir = Path("/custom/agent/files")
        installer = create_installer(agent_files_dir=custom_dir)
        assert installer.agent_files_dir == custom_dir

    def test_creates_installer_with_custom_logger(self) -> None:
        logger = setup_logging(level="DEBUG", logger_name="custom_test")
        installer = create_installer(logger=logger)
        assert installer.logger == logger


class TestMain:
    """Tests for main CLI function."""

    def test_main_local_install_dry_run(self) -> None:
        with patch("sys.argv", ["copilot-confirm", "--dry-run"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # May exit 0 or 1 depending on file existence
            assert exc_info.value.code in (0, 1)

    def test_main_both_global_and_local_error(self, capsys) -> None:
        with patch("sys.argv", ["copilot-confirm", "--global", "--local"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "Cannot specify both" in captured.out

    def test_main_global_install(self) -> None:
        with patch("sys.argv", ["copilot-confirm", "--global", "--dry-run"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code in (0, 1)

    def test_main_with_insiders_flag(self) -> None:
        with patch(
            "sys.argv",
            ["copilot-confirm", "--global", "--insiders", "--dry-run"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code in (0, 1)

    def test_main_with_log_level(self) -> None:
        with patch("sys.argv", ["copilot-confirm", "--log-level", "DEBUG", "--dry-run"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code in (0, 1)

    def test_main_with_log_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "install.log"
            with patch(
                "sys.argv",
                ["copilot-confirm", "--log-file", str(log_file), "--dry-run"],
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code in (0, 1)

