from __future__ import annotations

from typing import TYPE_CHECKING

from grooveloop.cli.session_line import session_line
from grooveloop.cli.watch_render import LearningLine, PullRequestLine, SliceLine, StoryLine

if TYPE_CHECKING:
    from datetime import datetime

    from grooveloop.shared.application.queries.list_repo_sessions import AgentSessionDTO
    from grooveloop.shared.domain.snapshot_lesson import SnapshotLesson
    from grooveloop.shared.domain.snapshot_pull_request import SnapshotPullRequest
    from grooveloop.shared.domain.snapshot_slice import SnapshotSlice
    from grooveloop.shared.domain.snapshot_story import SnapshotStory


def story_lines(stories: list[SnapshotStory], sessions: list[AgentSessionDTO], now: datetime) -> list[StoryLine]:
    by_slice = _by_slice(sessions)

    return [_story_line(story, by_slice, now) for story in stories]


def _by_slice(sessions: list[AgentSessionDTO]) -> dict[str, list[AgentSessionDTO]]:
    grouped: dict[str, list[AgentSessionDTO]] = {}
    for session in sessions:
        grouped.setdefault(session.slice_number, []).append(session)

    return grouped


def _story_line(story: SnapshotStory, sessions: dict[str, list[AgentSessionDTO]], now: datetime) -> StoryLine:
    by_source = {lesson.source_pull_request_number: lesson for lesson in story.lessons}
    sourced = {int(a_slice.pr_number) for a_slice in story.slices if a_slice.pr_number is not None}

    return StoryLine(
        number=story.number,
        title=story.title,
        status=story.status,
        slices=[
            _slice_line(a_slice, order, sessions, by_source, now) for order, a_slice in enumerate(story.slices, start=1)
        ],
        lessons=[
            _learning_line(lesson) for lesson in story.lessons if lesson.source_pull_request_number not in sourced
        ],
    )


def _slice_line(
    a_slice: SnapshotSlice,
    order: int,
    sessions: dict[str, list[AgentSessionDTO]],
    lessons: dict[int, SnapshotLesson],
    now: datetime,
) -> SliceLine:
    return SliceLine(
        status=a_slice.status,
        title=a_slice.title,
        order=order,
        pr_number=a_slice.pr_number,
        number=a_slice.number,
        sessions=[session_line(session, now) for session in sessions.get(a_slice.number, [])],
        learning=_lesson_of(a_slice, lessons),
        depends_on=a_slice.depends_on,
        pull_request=_pull_request_line(a_slice.pull_request, now),
    )


def _pull_request_line(pull_request: SnapshotPullRequest | None, now: datetime) -> PullRequestLine | None:
    if pull_request is None:
        return None

    return PullRequestLine(
        title=pull_request.title,
        additions=pull_request.additions,
        deletions=pull_request.deletions,
        changed_files=pull_request.changed_files,
        mergeable=pull_request.mergeable,
        checks=pull_request.checks,
        age_seconds=int((now - pull_request.updated_at).total_seconds()),
    )


def _lesson_of(a_slice: SnapshotSlice, lessons: dict[int, SnapshotLesson]) -> LearningLine | None:
    if a_slice.pr_number is None:
        return None

    lesson = lessons.get(int(a_slice.pr_number))
    if lesson is None:
        return None

    return _learning_line(lesson)


def _learning_line(lesson: SnapshotLesson) -> LearningLine:
    return LearningLine(
        number=lesson.number,
        status=lesson.status,
        conventions_pr_number=_number_or_none(lesson.conventions_pull_request_number),
        resolved=lesson.resolved,
    )


def _number_or_none(number: int | None) -> str | None:
    if number is None:
        return None

    return str(number)
