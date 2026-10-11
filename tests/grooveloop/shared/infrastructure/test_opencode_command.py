from __future__ import annotations

from grooveloop.shared.infrastructure.opencode_command import OpencodeCommand


class TestOpencodeCommand:
    def test_argv_requests_json_events_and_skips_permissions_for_the_given_model(self) -> None:
        command = OpencodeCommand()

        assert command.argv("openrouter/inclusionai/ling-3.0-flash:free") == [
            "opencode",
            "run",
            "--format",
            "json",
            "-m",
            "openrouter/inclusionai/ling-3.0-flash:free",
            "--dangerously-skip-permissions",
        ]

    def test_engine_is_opencode(self) -> None:
        command = OpencodeCommand()

        assert command.engine == "opencode"

    def test_resume_argv_is_none_because_the_loop_does_not_resume_opencode_sessions(self) -> None:
        assert OpencodeCommand().resume_argv("model", '{"sessionID":"ses-1"}\n') is None
