from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from grooveloop.cli import main as main_module
from grooveloop.cli.main import main

if TYPE_CHECKING:
    from collections.abc import Iterator

_HANDLER_LOGGER = "grooveloop.shared.application.commands.command_handler"


@pytest.fixture(autouse=True)
def _restore_the_grooveloop_logger() -> Iterator[None]:
    logger = logging.getLogger("grooveloop")
    handlers, level = list(logger.handlers), logger.level
    yield
    logger.handlers = handlers
    logger.setLevel(level)


def _log_through_main(level: int, message: str) -> None:
    def run_doctor(**_: object) -> int:
        logging.getLogger(_HANDLER_LOGGER).log(level, message)

        return 0

    with patch.object(main_module, "doctor_command") as doctor_command:
        doctor_command.run.side_effect = run_doctor
        main(["doctor"])


@pytest.mark.entrypoint
class TestMainLogging:
    def test_should_drop_the_handler_info_lines_by_default(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("GROOVELOOP_LOG_LEVEL", raising=False)

        _log_through_main(logging.INFO, "Executing MarkMergedCommand")

        assert "Executing MarkMergedCommand" not in capsys.readouterr().err

    def test_should_write_the_warnings_to_stderr_by_default(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("GROOVELOOP_LOG_LEVEL", raising=False)

        _log_through_main(logging.WARNING, "the tick took long")

        assert "WARNING the tick took long" in capsys.readouterr().err

    def test_should_write_the_handler_info_lines_to_stderr_at_the_level_of_the_environment(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("GROOVELOOP_LOG_LEVEL", "info")

        _log_through_main(logging.INFO, "Executing MarkMergedCommand")

        captured = capsys.readouterr()
        assert "INFO Executing MarkMergedCommand" in captured.err
        assert "Executing MarkMergedCommand" not in captured.out

    def test_should_write_each_line_once_when_main_runs_twice(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("GROOVELOOP_LOG_LEVEL", "INFO")

        _log_through_main(logging.INFO, "first")
        _log_through_main(logging.INFO, "second")

        assert capsys.readouterr().err.count("INFO second") == 1


@pytest.mark.entrypoint
class TestMain:
    def test_doctor_subcommand_returns_its_exit_code(self) -> None:
        with patch.object(main_module, "doctor_command") as doctor_command:
            doctor_command.run.return_value = 3
            exit_code = main(["doctor"])

        assert exit_code == 3

    def test_doctor_subcommand_parses_the_workdir_flag(self) -> None:
        with patch.object(main_module, "doctor_command") as doctor_command:
            doctor_command.run.return_value = 0
            exit_code = main(["doctor", "--workdir", "/wd"])

        assert exit_code == 0
        doctor_command.run.assert_called_once_with(workdir="/wd", repo=None)

    def test_doctor_subcommand_parses_the_repo_flag(self) -> None:
        with patch.object(main_module, "doctor_command") as doctor_command:
            doctor_command.run.return_value = 0
            main(["doctor", "--repo", "acme/sample"])

        doctor_command.run.assert_called_once_with(workdir=".", repo="acme/sample")

    def test_unknown_subcommand_exits_with_argparse_error(self) -> None:
        with pytest.raises(SystemExit):
            main(["nope"])

    def test_run_subcommand_no_longer_exists(self) -> None:
        with pytest.raises(SystemExit):
            main(["run", "--repo", "owner/repo"])

    def test_watch_subcommand_returns_its_exit_code(self) -> None:
        with patch.object(main_module, "watch_command") as watch_command:
            watch_command.run.return_value = 0
            exit_code = main(["watch"])

        assert exit_code == 0
        watch_command.run.assert_called_once_with(interval=1, stall_after=300, screenshot=None)

    def test_watch_subcommand_parses_its_flags(self) -> None:
        with patch.object(main_module, "watch_command") as watch_command:
            watch_command.run.return_value = 0
            main(["watch", "--interval", "3", "--stall-after", "42", "--screenshot", "/tmp/watch.svg"])

        watch_command.run.assert_called_once_with(interval=3, stall_after=42, screenshot="/tmp/watch.svg")

    @pytest.mark.parametrize("flag", ["--once", "--tui"])
    def test_watch_subcommand_rejects_the_retired_flags_with_exit_two(self, flag: str) -> None:
        with patch.object(main_module, "watch_command") as watch_command, pytest.raises(SystemExit) as exit_info:
            main(["watch", flag])

        assert exit_info.value.code == 2
        watch_command.run.assert_not_called()

    def test_watch_subcommand_rejects_the_repo_flag(self) -> None:
        with pytest.raises(SystemExit):
            main(["watch", "--repo", "owner/repo"])

    def test_dispatch_subcommand_no_longer_exists(self) -> None:
        with pytest.raises(SystemExit):
            main(["dispatch", "--repo", "owner/repo", "--story", "10"])

    def test_loop_subcommand_requires_repo(self) -> None:
        with pytest.raises(SystemExit):
            main(["loop"])

    def test_loop_subcommand_parses_intervals_and_workdir(self) -> None:
        with patch.object(main_module, "loop_command") as loop_command:
            loop_command.run.return_value = 0
            exit_code = main(
                ["loop", "--repo", "owner/repo", "--interval", "2", "--tick-interval", "3", "--workdir", "/wd"]
            )

        assert exit_code == 0
        loop_command.run.assert_called_once_with(
            "owner/repo",
            interval=2,
            tick_interval=3,
            workdir="/wd",
            once=False,
            story=None,
            verify_deploy=False,
            max_review_rounds=3,
            max_parallel_slices=3,
            journal_enabled=True,
            max_retries=2,
            auto_merge=False,
        )

    def test_loop_subcommand_parses_the_story_flag(self) -> None:
        with patch.object(main_module, "loop_command") as loop_command:
            loop_command.run.return_value = 0
            exit_code = main(["loop", "--repo", "owner/repo", "--story", "42"])

        assert exit_code == 0
        loop_command.run.assert_called_once_with(
            "owner/repo",
            interval=5,
            tick_interval=120,
            workdir=".",
            once=False,
            story=42,
            verify_deploy=False,
            max_review_rounds=3,
            max_parallel_slices=3,
            journal_enabled=True,
            max_retries=2,
            auto_merge=False,
        )

    def test_loop_subcommand_parses_the_once_flag(self) -> None:
        with patch.object(main_module, "loop_command") as loop_command:
            loop_command.run.return_value = 0
            exit_code = main(["loop", "--repo", "owner/repo", "--once"])

        assert exit_code == 0
        loop_command.run.assert_called_once_with(
            "owner/repo",
            interval=5,
            tick_interval=120,
            workdir=".",
            once=True,
            story=None,
            verify_deploy=False,
            max_review_rounds=3,
            max_parallel_slices=3,
            journal_enabled=True,
            max_retries=2,
            auto_merge=False,
        )

    def test_watch_help_documents_the_keys(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main(["watch", "--help"])

        output = capsys.readouterr().out
        assert "Keys" in output
        assert "[1-9]" not in output
        assert "[enter]/click" not in output
        for key in ["[tab]", "[ / ]", "[enter]", "[esc]", "[o]", "[f]", "[q]"]:
            assert key in output

    def test_watch_help_documents_the_screenshot_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main(["watch", "--help"])

        output = capsys.readouterr().out
        assert "--screenshot" in output
        assert "screenshot saved" in output

    def test_loop_help_documents_the_exit_codes(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main(["loop", "--help"])

        output = capsys.readouterr().out
        assert "Exit codes" in output
        assert "  1  the single tick of --once failed" in output
        assert "  2  usage error" in output
        assert "  3  preflight failed" in output
        assert "panel" not in output
        assert "invalid flag combination" not in output

    @pytest.mark.parametrize(
        ("command", "documented"),
        [
            ("doctor", ["  0  ", "  1  a required probe failed", "  2  usage error"]),
            ("usage", ["  0  ", "  1  no sessions for the slice", "  2  usage error"]),
            ("note", ["  0  ", "  2  usage error", "  4  missing context"]),
            ("journal", ["  0  ", "  2  usage error", "  4  missing context"]),
            ("watch", ["  0  ", "  2  usage error"]),
        ],
    )
    def test_help_of_every_command_documents_its_exit_codes(
        self, command: str, documented: list[str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            main([command, "--help"])

        output = capsys.readouterr().out
        assert "Exit codes:" in output
        for line in documented:
            assert line in output

    def test_loop_help_documents_the_clocks(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main(["loop", "--help"])

        output = capsys.readouterr().out
        assert "Clocks" in output
        assert "--tick-interval" in output

    @pytest.mark.parametrize("flag", ["--render", "--no-render", "--no-tick", "--stall-after=0"])
    def test_loop_subcommand_rejects_the_panel_flags_with_exit_two(self, flag: str) -> None:
        with patch.object(main_module, "loop_command") as loop_command, pytest.raises(SystemExit) as exit_info:
            main(["loop", "--repo", "owner/repo", flag])

        assert exit_info.value.code == 2
        loop_command.run.assert_not_called()

    def test_loop_subcommand_no_longer_accepts_the_github_interval_flag(self) -> None:
        with pytest.raises(SystemExit):
            main(["loop", "--repo", "owner/repo", "--github-interval", "300"])

    def test_loop_subcommand_parses_the_verify_deploy_flag(self) -> None:
        with patch.object(main_module, "loop_command") as loop_command:
            loop_command.run.return_value = 0
            exit_code = main(["loop", "--repo", "owner/repo", "--verify-deploy"])

        assert exit_code == 0
        assert loop_command.run.call_args.kwargs["verify_deploy"] is True

    def test_loop_subcommand_leaves_deploy_verification_off_by_default(self) -> None:
        with patch.object(main_module, "loop_command") as loop_command:
            loop_command.run.return_value = 0
            exit_code = main(["loop", "--repo", "owner/repo"])

        assert exit_code == 0
        assert loop_command.run.call_args.kwargs["verify_deploy"] is False

    def test_loop_subcommand_parses_the_no_journal_flag(self) -> None:
        with patch.object(main_module, "loop_command") as loop_command:
            loop_command.run.return_value = 0
            exit_code = main(["loop", "--repo", "owner/repo", "--no-journal"])

        assert exit_code == 0
        assert loop_command.run.call_args.kwargs["journal_enabled"] is False

    def test_loop_subcommand_turns_the_journal_on_by_default(self) -> None:
        with patch.object(main_module, "loop_command") as loop_command:
            loop_command.run.return_value = 0
            exit_code = main(["loop", "--repo", "owner/repo"])

        assert exit_code == 0
        assert loop_command.run.call_args.kwargs["journal_enabled"] is True

    def test_loop_subcommand_parses_the_max_review_rounds_flag(self) -> None:
        with patch.object(main_module, "loop_command") as loop_command:
            loop_command.run.return_value = 0
            exit_code = main(["loop", "--repo", "owner/repo", "--max-review-rounds", "1"])

        assert exit_code == 0
        assert loop_command.run.call_args.kwargs["max_review_rounds"] == 1

    def test_loop_subcommand_rejects_a_negative_max_review_rounds(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(main_module, "loop_command") as loop_command, pytest.raises(SystemExit) as error:
            main(["loop", "--repo", "owner/repo", "--max-review-rounds", "-1"])

        assert error.value.code == 2
        assert "--max-review-rounds" in capsys.readouterr().err
        loop_command.run.assert_not_called()

    def test_usage_subcommand_returns_its_exit_code(self) -> None:
        with patch.object(main_module, "usage_command") as usage_command:
            usage_command.run.return_value = 0
            exit_code = main(["usage", "--repo", "owner/repo", "--slice", "363"])

        assert exit_code == 0
        usage_command.run.assert_called_once_with(repo="owner/repo", slice_number=363)

    def test_usage_subcommand_requires_repo_and_slice(self) -> None:
        with pytest.raises(SystemExit):
            main(["usage"])

    def test_note_subcommand_returns_its_exit_code(self) -> None:
        with patch.object(main_module, "note_command") as note_command:
            note_command.run.return_value = 0
            exit_code = main(["note", "--repo", "owner/repo", "--story", "999", "--kind", "finding", "body text"])

        assert exit_code == 0
        note_command.run.assert_called_once_with(repo="owner/repo", story=999, kind="finding", body="body text")

    def test_note_subcommand_requires_repo_story_and_kind(self) -> None:
        with pytest.raises(SystemExit):
            main(["note", "body text"])

    def test_journal_subcommand_returns_its_exit_code(self) -> None:
        with patch.object(main_module, "journal_command") as journal_command:
            journal_command.run.return_value = 0
            exit_code = main(["journal", "--repo", "owner/repo", "--story", "999"])

        assert exit_code == 0
        journal_command.run.assert_called_once_with(repo="owner/repo", story=999, kinds=None)

    def test_journal_subcommand_forwards_repeated_kind_flags(self) -> None:
        with patch.object(main_module, "journal_command") as journal_command:
            journal_command.run.return_value = 0
            exit_code = main(
                ["journal", "--repo", "owner/repo", "--story", "999", "--kind", "constraint", "--kind", "finding"]
            )

        assert exit_code == 0
        journal_command.run.assert_called_once_with(repo="owner/repo", story=999, kinds=["constraint", "finding"])

    def test_journal_subcommand_can_omit_repo_and_story(self) -> None:
        with patch.object(main_module, "journal_command") as journal_command:
            journal_command.run.return_value = 0
            exit_code = main(["journal"])

        assert exit_code == 0
        journal_command.run.assert_called_once_with(repo=None, story=None, kinds=None)

    def test_loop_subcommand_asks_for_three_automatic_review_rounds_by_default(self) -> None:
        with patch.object(main_module, "loop_command") as loop_command:
            loop_command.run.return_value = 0
            exit_code = main(["loop", "--repo", "owner/repo"])

        assert exit_code == 0
        assert loop_command.run.call_args.kwargs["max_review_rounds"] == 3

    def test_loop_subcommand_parses_the_max_parallel_slices_flag(self) -> None:
        with patch.object(main_module, "loop_command") as loop_command:
            loop_command.run.return_value = 0
            exit_code = main(["loop", "--repo", "owner/repo", "--max-parallel-slices", "5"])

        assert exit_code == 0
        assert loop_command.run.call_args.kwargs["max_parallel_slices"] == 5

    def test_loop_subcommand_rejects_a_non_positive_max_parallel_slices(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.object(main_module, "loop_command") as loop_command, pytest.raises(SystemExit) as error:
            main(["loop", "--repo", "owner/repo", "--max-parallel-slices", "0"])

        assert error.value.code == 2
        assert "--max-parallel-slices" in capsys.readouterr().err
        loop_command.run.assert_not_called()

    def test_loop_subcommand_parses_the_max_retries_flag(self) -> None:
        with patch.object(main_module, "loop_command") as loop_command:
            loop_command.run.return_value = 0
            exit_code = main(["loop", "--repo", "owner/repo", "--max-retries", "0"])

        assert exit_code == 0
        assert loop_command.run.call_args.kwargs["max_retries"] == 0

    def test_loop_subcommand_parses_the_auto_merge_flag(self) -> None:
        with patch.object(main_module, "loop_command") as loop_command:
            loop_command.run.return_value = 0
            exit_code = main(["loop", "--repo", "owner/repo", "--auto-merge"])

        assert exit_code == 0
        assert loop_command.run.call_args.kwargs["auto_merge"] is True

    def test_loop_subcommand_rejects_a_negative_max_retries(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(main_module, "loop_command") as loop_command, pytest.raises(SystemExit) as error:
            main(["loop", "--repo", "owner/repo", "--max-retries", "-1"])

        assert error.value.code == 2
        assert "--max-retries" in capsys.readouterr().err
        loop_command.run.assert_not_called()

    def test_loop_subcommand_defaults_to_three_parallel_slices(self) -> None:
        with patch.object(main_module, "loop_command") as loop_command:
            loop_command.run.return_value = 0
            exit_code = main(["loop", "--repo", "owner/repo"])

        assert exit_code == 0
        assert loop_command.run.call_args.kwargs["max_parallel_slices"] == 3
