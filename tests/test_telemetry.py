"""Tests for copilot_confirm.telemetry module.

Tests all telemetry functionality:
- TelemetryEntry serialization
- Config parsing (off/local/remote modes, defaults, missing file)
- TelemetryLogger.log() (append, mode=off, mode=remote, turn auto-increment)
- TelemetryLogger.show() (empty/missing file)
- TelemetryLogger.send() (success, failure, no endpoint, mode=off)
- CLI subcommands: log, telemetry show, telemetry send
- Installer bakes correct CLI path into instructions
- Append-only behavior (multiple log calls)
"""

from datetime import date
from pathlib import Path
from unittest.mock import patch

from copilot_confirm.install import (
    AgentInstaller,
    EditorDetector,
    FileMapping,
    PathResolver,
    main,
    setup_logging,
)
from copilot_confirm.telemetry import (
    TelemetryConfig,
    TelemetryEntry,
    TelemetryLogger,
    _parse_toml_telemetry,
    load_config,
)

# ============================================================================
# Mock Implementations
# ============================================================================


class MockTelemetryFS:
    """Mock filesystem for telemetry tests."""

    def __init__(self, existing_content: str = "") -> None:
        self.lines: list[str] = []
        self.existing_content = existing_content
        self._date_counts: dict[str, int] = {}

    def read_text(self, path: Path) -> str:  # noqa: ARG002
        if self.lines:
            return "\n".join(self.lines) + "\n"
        return self.existing_content

    def append_line(self, path: Path, line: str) -> None:  # noqa: ARG002
        self.lines.append(line)

    def exists(self, path: Path) -> bool:  # noqa: ARG002
        return bool(self.lines or self.existing_content)

    def count_lines_for_date(self, path: Path, date_str: str) -> int:  # noqa: ARG002
        return self._date_counts.get(date_str, 0)

    def set_date_count(self, date_str: str, count: int) -> None:
        self._date_counts[date_str] = count


class MockNetwork:
    """Mock network for telemetry tests."""

    def __init__(self, status: int = 200, body: str = "ok") -> None:
        self.status = status
        self.body = body
        self.posted: list[tuple[str, str]] = []

    def post(self, url: str, data: str) -> tuple[int, str]:
        self.posted.append((url, data))
        return self.status, self.body


# ============================================================================
# TelemetryEntry
# ============================================================================


class TestTelemetryEntry:
    def test_to_line_basic(self) -> None:
        entry = TelemetryEntry(
            model="claude-sonnet-4.6",
            selected=70,
            spread=[70, 25, 5],
            correction=False,
            waited=True,
            options=True,
            pct=True,
        )
        line = entry.to_line(date(2026, 4, 17), 1)
        assert "2026-04-17" in line
        assert "turn=1" in line
        assert "model=claude-sonnet-4.6" in line
        assert "selected=70" in line
        assert "spread=[70,25,5]" in line
        assert "correction=no" in line
        assert "waited=yes" in line
        assert "options=yes" in line
        assert "pct=yes" in line

    def test_to_line_pipe_delimited(self) -> None:
        entry = TelemetryEntry(
            model="gpt-5-mini",
            selected=0,
            spread=[60, 30, 10],
            correction=True,
            waited=False,
            options=True,
            pct=True,
        )
        line = entry.to_line(date(2026, 4, 17), 3)
        parts = [p.strip() for p in line.split("|")]
        assert len(parts) == 13
        assert parts[0] == "2026-04-17"
        assert parts[1] == "turn=3"
        assert parts[2] == "model=gpt-5-mini"
        assert parts[3] == "selected=0"
        assert parts[4] == "spread=[60,30,10]"
        assert parts[5] == "correction=yes"
        assert parts[6] == "waited=no"
        assert parts[7] == "options=yes"
        assert parts[8] == "pct=yes"
        # v2 fields default when not set
        assert parts[9] == "assumed=no"
        assert parts[10] == "framing_correction=no"
        assert parts[11] == "option_modification=no"
        assert parts[12] == "task_id=-"

    def test_to_line_correction_and_waited_bool(self) -> None:
        entry = TelemetryEntry(
            model="m",
            selected=55,
            spread=[55, 35, 10],
            correction=True,
            waited=True,
            options=False,
            pct=False,
        )
        line = entry.to_line(date(2026, 1, 1), 1)
        assert "correction=yes" in line
        assert "waited=yes" in line
        assert "options=no" in line
        assert "pct=no" in line

    def test_selected_zero_rejection(self) -> None:
        """selected=0 means user rejected all options."""
        entry = TelemetryEntry(
            model="m",
            selected=0,
            spread=[60, 30, 10],
            correction=True,
            waited=True,
            options=True,
            pct=True,
        )
        line = entry.to_line(date(2026, 1, 1), 1)
        assert "selected=0" in line
        assert "correction=yes" in line

    def test_v2_assumption_and_task_id(self) -> None:
        """v2 fields render correctly when set."""
        entry = TelemetryEntry(
            model="m",
            selected=70,
            spread=[70, 25, 5],
            correction=False,
            waited=True,
            options=True,
            pct=True,
            assumed=True,
            framing_correction=False,
            option_modification=True,
            task_id="abc12345",
        )
        line = entry.to_line(date(2026, 4, 22), 1)
        assert "assumed=yes" in line
        assert "framing_correction=no" in line
        assert "option_modification=yes" in line
        assert "task_id=abc12345" in line

    def test_v2_defaults_when_unset(self) -> None:
        """v2 fields default to no/'-' when omitted (backward compat)."""
        entry = TelemetryEntry(
            model="m",
            selected=70,
            spread=[70, 25, 5],
            correction=False,
            waited=True,
            options=True,
            pct=True,
        )
        line = entry.to_line(date(2026, 4, 22), 1)
        assert "assumed=no" in line
        assert "framing_correction=no" in line
        assert "option_modification=no" in line
        assert "task_id=-" in line


# ============================================================================
# Config Parsing
# ============================================================================


class TestLoadConfig:
    def test_defaults_when_no_file(self, tmp_path: Path) -> None:
        config = load_config(tmp_path / "nonexistent.toml")
        assert config.mode == "off"
        assert "telemetry.log" in str(config.path)
        assert config.endpoint == ""

    def test_parse_local_mode(self) -> None:
        toml = '[telemetry]\nmode = "local"\n'
        defaults = TelemetryConfig(mode="off", path=Path("/default"), endpoint="")
        config = _parse_toml_telemetry(toml, defaults)
        assert config.mode == "local"

    def test_parse_remote_mode_with_endpoint(self) -> None:
        toml = '[telemetry]\nmode = "remote"\nendpoint = "https://example.com/telem"\n'
        defaults = TelemetryConfig(mode="off", path=Path("/default"), endpoint="")
        config = _parse_toml_telemetry(toml, defaults)
        assert config.mode == "remote"
        assert config.endpoint == "https://example.com/telem"

    def test_parse_off_mode(self) -> None:
        toml = '[telemetry]\nmode = "off"\n'
        defaults = TelemetryConfig(mode="local", path=Path("/default"), endpoint="")
        config = _parse_toml_telemetry(toml, defaults)
        assert config.mode == "off"

    def test_invalid_mode_uses_default(self) -> None:
        toml = '[telemetry]\nmode = "invalid"\n'
        defaults = TelemetryConfig(mode="off", path=Path("/default"), endpoint="")
        config = _parse_toml_telemetry(toml, defaults)
        assert config.mode == "off"

    def test_parse_custom_path(self) -> None:
        toml = '[telemetry]\npath = "/tmp/mylog.txt"\n'
        defaults = TelemetryConfig(mode="off", path=Path("/default"), endpoint="")
        config = _parse_toml_telemetry(toml, defaults)
        assert config.path == Path("/tmp/mylog.txt")

    def test_ignores_other_sections(self) -> None:
        toml = '[other]\nmode = "remote"\n[telemetry]\nmode = "local"\n'
        defaults = TelemetryConfig(mode="off", path=Path("/default"), endpoint="")
        config = _parse_toml_telemetry(toml, defaults)
        assert config.mode == "local"

    def test_load_from_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text('[telemetry]\nmode = "local"\n', encoding="utf-8")
        config = load_config(config_file)
        assert config.mode == "local"


# ============================================================================
# TelemetryLogger.log
# ============================================================================


class TestTelemetryLoggerLog:
    def _make_entry(self) -> TelemetryEntry:
        return TelemetryEntry(
            model="claude-sonnet-4.6",
            selected=70,
            spread=[70, 25, 5],
            correction=False,
            waited=True,
            options=True,
            pct=True,
        )

    def test_log_off_returns_none(self) -> None:
        config = TelemetryConfig(mode="off", path=Path("/tmp/t.log"), endpoint="")
        logger = TelemetryLogger(config, MockTelemetryFS(), MockNetwork())
        result = logger.log(self._make_entry())
        assert result is None

    def test_log_local_appends_line(self) -> None:
        config = TelemetryConfig(mode="local", path=Path("/tmp/t.log"), endpoint="")
        fs = MockTelemetryFS()
        logger = TelemetryLogger(config, fs, MockNetwork())
        result = logger.log(self._make_entry())
        assert result is not None
        assert len(fs.lines) == 1
        assert "selected=70" in fs.lines[0]

    def test_log_turn_autoincrements(self) -> None:
        config = TelemetryConfig(mode="local", path=Path("/tmp/t.log"), endpoint="")
        fs = MockTelemetryFS()
        logger = TelemetryLogger(config, fs, MockNetwork())
        # First call — turn=1
        logger.log(self._make_entry())
        # Simulate one existing line for today
        today = date.today().isoformat()
        fs.set_date_count(today, 1)
        # Second call — turn=2
        logger.log(self._make_entry())
        assert "turn=1" in fs.lines[0]
        assert "turn=2" in fs.lines[1]

    def test_log_append_only_multiple_calls(self) -> None:
        config = TelemetryConfig(mode="local", path=Path("/tmp/t.log"), endpoint="")
        fs = MockTelemetryFS()
        today = date.today().isoformat()
        logger = TelemetryLogger(config, fs, MockNetwork())
        for i in range(3):
            fs.set_date_count(today, i)
            logger.log(self._make_entry())
        assert len(fs.lines) == 3

    def test_log_remote_posts_line(self) -> None:
        config = TelemetryConfig(
            mode="remote", path=Path("/tmp/t.log"), endpoint="https://example.com/t"
        )
        fs = MockTelemetryFS()
        net = MockNetwork()
        logger = TelemetryLogger(config, fs, net)
        logger.log(self._make_entry())
        assert len(net.posted) == 1
        assert "selected=70" in net.posted[0][1]

    def test_log_remote_no_endpoint_does_not_post(self) -> None:
        config = TelemetryConfig(mode="remote", path=Path("/tmp/t.log"), endpoint="")
        fs = MockTelemetryFS()
        net = MockNetwork()
        logger = TelemetryLogger(config, fs, net)
        logger.log(self._make_entry())
        assert len(net.posted) == 0
        assert len(fs.lines) == 1  # still writes locally


# ============================================================================
# TelemetryLogger.show
# ============================================================================


class TestTelemetryLoggerShow:
    def test_show_empty_when_no_file(self) -> None:
        config = TelemetryConfig(mode="local", path=Path("/tmp/t.log"), endpoint="")
        fs = MockTelemetryFS()
        logger = TelemetryLogger(config, fs, MockNetwork())
        assert logger.show() == ""

    def test_show_returns_content(self) -> None:
        content = "2026-04-17 | turn=1 | model=m | selected=70 | ...\n"
        config = TelemetryConfig(mode="local", path=Path("/tmp/t.log"), endpoint="")
        fs = MockTelemetryFS(existing_content=content)
        logger = TelemetryLogger(config, fs, MockNetwork())
        assert logger.show() == content


# ============================================================================
# TelemetryLogger.send
# ============================================================================


class TestTelemetryLoggerSend:
    def test_send_off_returns_error(self) -> None:
        config = TelemetryConfig(mode="off", path=Path("/tmp/t.log"), endpoint="")
        logger = TelemetryLogger(config, MockTelemetryFS(), MockNetwork())
        ok, msg = logger.send()
        assert not ok
        assert "disabled" in msg.lower()

    def test_send_no_endpoint_returns_error(self) -> None:
        config = TelemetryConfig(mode="local", path=Path("/tmp/t.log"), endpoint="")
        logger = TelemetryLogger(config, MockTelemetryFS(), MockNetwork())
        ok, msg = logger.send()
        assert not ok
        assert "endpoint" in msg.lower()

    def test_send_empty_file_returns_error(self) -> None:
        config = TelemetryConfig(
            mode="local", path=Path("/tmp/t.log"), endpoint="https://example.com"
        )
        logger = TelemetryLogger(config, MockTelemetryFS(), MockNetwork())
        ok, msg = logger.send()
        assert not ok
        assert "no telemetry" in msg.lower()

    def test_send_success(self) -> None:
        content = "2026-04-17 | turn=1 | model=m | selected=70\n"
        config = TelemetryConfig(
            mode="local", path=Path("/tmp/t.log"), endpoint="https://example.com"
        )
        net = MockNetwork(status=200, body="ok")
        logger = TelemetryLogger(config, MockTelemetryFS(existing_content=content), net)
        ok, msg = logger.send()
        assert ok
        assert "200" in msg

    def test_send_failure_non_200(self) -> None:
        content = "2026-04-17 | turn=1 | model=m | selected=70\n"
        config = TelemetryConfig(
            mode="local", path=Path("/tmp/t.log"), endpoint="https://example.com"
        )
        net = MockNetwork(status=500, body="error")
        logger = TelemetryLogger(config, MockTelemetryFS(existing_content=content), net)
        ok, msg = logger.send()
        assert not ok
        assert "500" in msg

    def test_send_posts_content(self) -> None:
        content = "line1\nline2\n"
        config = TelemetryConfig(
            mode="local", path=Path("/tmp/t.log"), endpoint="https://example.com/t"
        )
        net = MockNetwork()
        logger = TelemetryLogger(config, MockTelemetryFS(existing_content=content), net)
        logger.send()
        assert len(net.posted) == 1
        assert net.posted[0][1] == content


# ============================================================================
# CLI subcommands
# ============================================================================


class TestCLILog:
    def test_log_command_mode_off_returns_0(self) -> None:
        """When mode=off, log command exits 0 silently."""
        with (
            patch(
                "sys.argv",
                [
                    "copilot-confirm",
                    "log",
                    "--model",
                    "claude-sonnet-4.6",
                    "--selected",
                    "70",
                    "--spread",
                    "70,25,5",
                    "--correction",
                    "no",
                    "--waited",
                    "yes",
                    "--options",
                    "yes",
                    "--pct",
                    "yes",
                ],
            ),
            patch("copilot_confirm.telemetry.create_telemetry_logger") as mock_factory,
        ):
            mock_telem = mock_factory.return_value
            mock_telem.log.return_value = None
            result = main()
        assert result == 0

    def test_log_command_local_returns_0(self) -> None:
        with (
            patch(
                "sys.argv",
                [
                    "copilot-confirm",
                    "log",
                    "--model",
                    "test-model",
                    "--selected",
                    "55",
                    "--spread",
                    "55,35,10",
                    "--correction",
                    "yes",
                    "--waited",
                    "yes",
                    "--options",
                    "yes",
                    "--pct",
                    "yes",
                ],
            ),
            patch("copilot_confirm.telemetry.create_telemetry_logger") as mock_factory,
        ):
            mock_telem = mock_factory.return_value
            mock_telem.log.return_value = "2026-04-17 | turn=1 | ..."
            result = main()
        assert result == 0

    def test_log_command_bad_spread(self) -> None:
        with patch(
            "sys.argv",
            [
                "copilot-confirm",
                "log",
                "--model",
                "m",
                "--selected",
                "70",
                "--spread",
                "bad,data",
                "--correction",
                "no",
                "--waited",
                "yes",
                "--options",
                "yes",
                "--pct",
                "yes",
            ],
        ):
            result = main()
        assert result == 1


class TestCLITelemetryShow:
    def test_show_no_data(self) -> None:
        with (
            patch("sys.argv", ["copilot-confirm", "telemetry", "show"]),
            patch("copilot_confirm.telemetry.create_telemetry_logger") as mock_factory,
        ):
            mock_telem = mock_factory.return_value
            mock_telem.show.return_value = ""
            result = main()
        assert result == 0

    def test_show_with_data(self) -> None:
        with (
            patch("sys.argv", ["copilot-confirm", "telemetry", "show"]),
            patch("copilot_confirm.telemetry.create_telemetry_logger") as mock_factory,
        ):
            mock_telem = mock_factory.return_value
            mock_telem.show.return_value = "some data\n"
            result = main()
        assert result == 0


class TestCLITelemetrySend:
    def test_send_success(self) -> None:
        with (
            patch("sys.argv", ["copilot-confirm", "telemetry", "send"]),
            patch("copilot_confirm.telemetry.create_telemetry_logger") as mock_factory,
        ):
            mock_telem = mock_factory.return_value
            mock_telem.send.return_value = (True, "Sent successfully (HTTP 200)")
            result = main()
        assert result == 0

    def test_send_failure(self) -> None:
        with (
            patch("sys.argv", ["copilot-confirm", "telemetry", "send"]),
            patch("copilot_confirm.telemetry.create_telemetry_logger") as mock_factory,
        ):
            mock_telem = mock_factory.return_value
            mock_telem.send.return_value = (False, "Telemetry is disabled (mode=off)")
            result = main()
        assert result == 1


# ============================================================================
# Installer bakes CLI path
# ============================================================================


class TestInstallerBakesCliPath:
    """Verify that the installer substitutes CLI_PATH in instructions file."""

    class MockInstallerFS:
        """Minimal FS mock for installer that supports read_text/write_text."""

        def __init__(self, instructions_content: str) -> None:
            self.instructions_content = instructions_content
            self.written: dict[str, str] = {}
            self.created_dirs: list[Path] = []
            self.copied_files: list[tuple[Path, Path]] = []

        def exists(self, path: Path) -> bool:
            return True  # everything "exists"

        def mkdir(
            self, path: Path, parents: bool = False, exist_ok: bool = False
        ) -> None:
            self.created_dirs.append(path)

        def copy_file(self, src: Path, dst: Path) -> None:
            self.copied_files.append((src, dst))

        def write_text(self, path: Path, content: str) -> None:
            self.written[str(path)] = content

        def read_text(self, path: Path) -> str:
            return self.instructions_content

        def get_cwd(self) -> Path:
            return Path("/test/repo")

    def test_cli_path_substituted_in_instructions(self) -> None:

        class MockEnv:
            def get_system(self) -> str:
                return "Linux"

            def get_env_var(self, name: str, default: str = "") -> str:
                return default

            def get_home(self) -> Path:
                return Path("/home/user")

        instructions_with_placeholder = "Run: CLI_PATH log --model MODEL\n"
        fs = self.MockInstallerFS(instructions_content=instructions_with_placeholder)
        env = MockEnv()
        resolver = PathResolver(env, fs)
        detector = EditorDetector(resolver, fs)
        logger = setup_logging(level="ERROR")  # quiet
        installer = AgentInstaller(
            agent_files_dir=Path("/fake/agent_files"),
            fs=fs,
            path_resolver=resolver,
            editor_detector=detector,
            logger=logger,
            cli_path="/usr/local/bin/copilot-confirm",
        )

        instructions_src = "instructions/confirmation_workflow.instructions.md"
        mappings = [FileMapping(instructions_src, instructions_src)]
        installer.install_files(Path("/fake/target"), mappings)

        # Find the written file
        written = next(iter(fs.written.values()))
        assert "/usr/local/bin/copilot-confirm" in written
        assert "CLI_PATH" not in written
