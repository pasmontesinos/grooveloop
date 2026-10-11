from __future__ import annotations

import json

from grooveloop.shared.infrastructure.claude_command import ClaudeCommand


class TestClaudeCommand:
    def test_argv_requests_a_stream_of_json_events_with_the_concise_output_style_and_no_mcp_servers(self) -> None:
        command = ClaudeCommand()

        assert command.argv("opus") == [
            "claude",
            "--print",
            "--output-format",
            "stream-json",
            "--verbose",
            "--strict-mcp-config",
            "--model",
            "opus",
            "--settings",
            '{"outputStyle": "Concise", "permissions": '
            '{"allow": ["Bash(grooveloop note:*)", "Bash(grooveloop journal:*)"]}, '
            '"env": {"BASH_DEFAULT_TIMEOUT_MS": "600000", "BASH_MAX_TIMEOUT_MS": "3600000"}}',
        ]

    def test_settings_raise_the_bash_timeouts_so_long_commands_run_in_the_foreground(self) -> None:
        argv = ClaudeCommand().argv("opus")

        settings = json.loads(argv[argv.index("--settings") + 1])

        assert settings["env"] == {"BASH_DEFAULT_TIMEOUT_MS": "600000", "BASH_MAX_TIMEOUT_MS": "3600000"}

    def test_engine_is_claude(self) -> None:
        command = ClaudeCommand()

        assert command.engine == "claude"

    def test_resume_argv_resumes_the_session_the_log_of_the_previous_run_declares(self) -> None:
        log_head = (
            '{"type":"system","subtype":"hook_started","session_id":"session-1"}\n'
            '{"type":"system","subtype":"init","session_id":"session-1"}\n'
        )

        argv = ClaudeCommand().resume_argv("opus", log_head)

        assert argv == [*ClaudeCommand().argv("opus"), "--resume", "session-1"]

    def test_resume_argv_is_none_when_the_log_declares_no_session(self) -> None:
        assert ClaudeCommand().resume_argv("opus", '{"type":"system"}\nnot json\n') is None
