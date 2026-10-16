from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, create_autospec

import pytest
from github.Issue import Issue
from github.Label import Label
from github.Repository import Repository

from grooveloop.delivery.domain.directive_mark import DirectiveMark
from grooveloop.delivery.domain.pull_request_number import PullRequestNumber
from grooveloop.delivery.domain.review_comment import ReviewComment
from grooveloop.delivery.domain.review_verdict import ReviewVerdict
from grooveloop.delivery.domain.slice_id import SliceId
from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId
from grooveloop.delivery.infrastructure.github_slice_repository import GithubSliceRepository
from grooveloop.shared.domain.agent_run import AgentRun
from grooveloop.shared.domain.agent_run_cause import AgentRunCause
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.domain.comment_directive import CommentDirective
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.slicing.domain.story_id import StoryId as SlicingStoryId
from grooveloop.slicing.infrastructure.github_story_repository import GithubStoryRepository
from tests.playground.shared.infrastructure.github_slice_graph import (
    conversation_comment,
    graph_reads,
    inline_comment,
    pr_node,
    reaction_group,
    slice_node,
    wire_slice_graph,
)


def _cache() -> GithubReadCache:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)

    return GithubReadCache(clock)


def _issue(number: int, *label_names: str) -> Any:
    issue = create_autospec(Issue, spec_set=True, instance=True)
    issue.number = number
    issue.labels = [_label(name) for name in label_names]

    return issue


def _label(name: str) -> Any:
    label = create_autospec(Label, spec_set=True, instance=True)
    label.name = name

    return label


@pytest.fixture
def repo() -> Any:
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.full_name = "owner/repo"

    return repo


@pytest.mark.integration
class TestGithubSliceRepository:
    def test_find_should_map_the_status_from_labels(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "dispatched"))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("11"))

        assert a_slice is not None
        assert a_slice.status == SliceStatus.DISPATCHED

    def test_find_reads_a_sub_issue_whose_state_label_a_human_removed_as_pending(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "order:1"))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("11"))

        assert a_slice is not None
        assert a_slice.status == SliceStatus.PENDING

    def test_find_returns_none_when_the_issue_does_not_exist(self, repo: Mock) -> None:
        wire_slice_graph(repo)
        adapter = GithubSliceRepository(repo, _cache())

        assert adapter.find(SliceId("11")) is None

    def test_search_should_filter_by_story_and_status_labels(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(11, "story:10", "pending"),
            slice_node(12, "story:10", "merged"),
        )
        adapter = GithubSliceRepository(repo, _cache())

        slices = adapter.search(story_id=StoryId("10"), status=SliceStatus.PENDING)

        assert [s.id.value for s in slices] == ["11"]

    def test_search_should_read_the_whole_graph_once(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "pending"), slice_node(12, "story:20", "pending"))
        adapter = GithubSliceRepository(repo, _cache())

        adapter.search(story_id=StoryId("10"))
        adapter.search(story_id=StoryId("20"))

        assert graph_reads(repo) == 1

    def test_search_should_ignore_story_issues(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(10, "grooveloop"), slice_node(11, "story:10", "pending"))
        adapter = GithubSliceRepository(repo, _cache())

        assert [s.id.value for s in adapter.search()] == ["11"]

    def test_search_should_only_return_the_open_slices_when_asked_for_them(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(11, "story:10", "pending"),
            slice_node(12, "story:10", "merged", state="CLOSED"),
        )
        adapter = GithubSliceRepository(repo, _cache())

        assert [s.id.value for s in adapter.search(story_id=StoryId("10"), open=True)] == ["11"]

    def test_search_should_only_return_the_closed_slices_when_asked_for_them(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(11, "story:10", "pending"),
            slice_node(12, "story:10", "merged", state="CLOSED"),
        )
        adapter = GithubSliceRepository(repo, _cache())

        assert [s.id.value for s in adapter.search(story_id=StoryId("10"), open=False)] == ["12"]

    def test_search_should_return_open_and_closed_slices_without_the_open_criterion(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(11, "story:10", "pending", "order:1"),
            slice_node(12, "story:10", "merged", "order:2", state="CLOSED"),
        )
        adapter = GithubSliceRepository(repo, _cache())

        slices = adapter.search(story_id=StoryId("10"))

        assert [s.id.value for s in slices] == ["11", "12"]

    def test_search_should_order_slices_by_their_order_label(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(12, "story:10", "pending", "order:2"),
            slice_node(11, "story:10", "pending", "order:1"),
        )
        adapter = GithubSliceRepository(repo, _cache())

        slices = adapter.search(story_id=StoryId("10"))

        assert [s.id.value for s in slices] == ["11", "12"]

    def test_search_should_resolve_the_pull_request_of_a_slice(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(12, "story:10", "pr_open", "pr:42", pull_request=pr_node(42, state="MERGED", merged=True)),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.search(story_id=StoryId("10"))[0]

        assert a_slice.pull_request is not None
        assert a_slice.pull_request.is_merged() is True

    def test_find_should_resolve_the_pull_request_of_a_blocked_slice(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "blocked", pull_request=pr_node(42)))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("11"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.number == PullRequestNumber(42)

    def test_find_should_read_the_story_id_from_its_label(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "dispatched"))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("11"))

        assert a_slice is not None
        assert a_slice.story_id == StoryId("10")

    def test_find_should_read_the_agent_run_id_from_its_label(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "changes_requested", "run:abc-123"))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("11"))

        assert a_slice is not None
        assert a_slice.agent_run_id == "abc-123"

    def test_find_should_read_the_declared_dependencies_from_the_marker(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                13,
                "story:10",
                "pending",
                body="<!-- grooveloop:depends-on -->\n**Depends on:** #11, #12",
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("13"))

        assert a_slice is not None
        assert a_slice.depends_on == [SliceId("11"), SliceId("12")]

    def test_find_should_leave_dependencies_undeclared_without_the_marker(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "pending", body="any description"))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("11"))

        assert a_slice is not None
        assert a_slice.depends_on is None

    def test_find_should_report_declared_independence_when_the_marker_says_none(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                11,
                "story:10",
                "pending",
                body="<!-- grooveloop:depends-on -->\n**Depends on:** none",
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("11"))

        assert a_slice is not None
        assert a_slice.depends_on == []

    def test_save_should_set_the_status_label_keeping_the_story_label(self, repo: Mock) -> None:
        issue = _issue(11, "story:10", "pending")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "pending"))
        adapter = GithubSliceRepository(repo, _cache())
        a_slice = adapter.find(SliceId("11"))
        assert a_slice is not None
        a_slice.dispatch()

        adapter.save(a_slice)

        issue.set_labels.assert_called_once_with("story:10", "dispatched")

    def test_save_should_write_the_agent_run_label(self, repo: Mock) -> None:
        issue = _issue(11, "story:10", "pr_open")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "pr_open"))
        adapter = GithubSliceRepository(repo, _cache())
        a_slice = adapter.find(SliceId("11"))
        assert a_slice is not None
        a_slice.record_agent_run(AgentRun(run_id="abc-123", pid=0))
        a_slice.request_changes()

        adapter.save(a_slice)

        issue.set_labels.assert_called_once_with("story:10", "changes_requested", "run:abc-123")

    def test_save_should_write_the_pull_request_label_when_the_slice_has_a_pull_request(self, repo: Mock) -> None:
        issue = _issue(11, "story:10", "dispatched")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "dispatched"))
        adapter = GithubSliceRepository(repo, _cache())
        a_slice = adapter.find(SliceId("11"))
        assert a_slice is not None
        a_slice.anchor_pull_request(PullRequestNumber(99))
        a_slice.start_review()

        adapter.save(a_slice)

        labels_set = issue.set_labels.call_args.args
        assert "under_review" in labels_set
        assert "pr:99" in labels_set

    def test_find_should_read_the_review_verdict_from_its_label(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "under_review", "review:blocking"))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("11"))

        assert a_slice is not None
        assert a_slice.review_verdict == ReviewVerdict.BLOCKING

    def test_save_should_rewrite_the_review_verdict_label_from_the_aggregate(self, repo: Mock) -> None:
        issue = _issue(11, "story:10", "under_review", "review:blocked")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "under_review", "review:blocked"))
        adapter = GithubSliceRepository(repo, _cache())
        a_slice = adapter.find(SliceId("11"))
        assert a_slice is not None
        a_slice.complete_review()

        adapter.save(a_slice)

        issue.set_labels.assert_called_once_with("story:10", "pr_open", "review:blocked")

    def test_save_should_drop_the_review_label_when_a_new_review_starts(self, repo: Mock) -> None:
        issue = _issue(11, "story:10", "changes_requested", "review:blocking", "review-round:1")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "changes_requested", "review:blocking", "review-round:1"))
        adapter = GithubSliceRepository(repo, _cache())
        a_slice = adapter.find(SliceId("11"))
        assert a_slice is not None
        a_slice.start_review()

        adapter.save(a_slice)

        issue.set_labels.assert_called_once_with("story:10", "under_review", "review-round:1")

    def test_find_should_read_the_consumed_review_rounds_from_its_label(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "under_review", "review-round:2"))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("11"))

        assert a_slice is not None
        assert a_slice.review_rounds == 2

    def test_find_should_report_no_consumed_rounds_without_the_label(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "under_review"))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("11"))

        assert a_slice is not None
        assert a_slice.review_rounds == 0

    def test_save_should_write_the_consumed_review_rounds(self, repo: Mock) -> None:
        issue = _issue(11, "story:10", "under_review", "review:blocking")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "under_review", "review:blocking"))
        adapter = GithubSliceRepository(repo, _cache())
        a_slice = adapter.find(SliceId("11"))
        assert a_slice is not None
        a_slice.consume_review_round()
        a_slice.request_changes()

        adapter.save(a_slice)

        assert issue.set_labels.call_args.args == (
            "story:10",
            "changes_requested",
            "review-round:1",
            "review:blocking",
        )

    def test_save_should_leave_no_round_label_when_none_was_consumed(self, repo: Mock) -> None:
        issue = _issue(11, "story:10", "pr_open")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "pr_open"))
        adapter = GithubSliceRepository(repo, _cache())
        a_slice = adapter.find(SliceId("11"))
        assert a_slice is not None
        a_slice.request_changes()

        adapter.save(a_slice)

        assert issue.set_labels.call_args.args == ("story:10", "changes_requested")

    def test_find_should_read_the_spent_retries_and_the_failure_cause_from_their_labels(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "failed", "retry:2", "failure:network"))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("11"))

        assert a_slice is not None
        assert a_slice.retries == 2
        assert a_slice.failure_cause.value == "network"

    def test_find_should_report_no_retries_nor_failure_cause_without_their_labels(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "dispatched"))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("11"))

        assert a_slice is not None
        assert a_slice.retries == 0
        assert a_slice.failure_cause.value is None

    def test_save_should_replace_the_run_and_count_the_retry(self, repo: Mock) -> None:
        issue = _issue(11, "story:10", "dispatched", "run:run-1", "retry:1")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "dispatched", "run:run-1", "retry:1"))
        adapter = GithubSliceRepository(repo, _cache())
        a_slice = adapter.find(SliceId("11"))
        assert a_slice is not None
        a_slice.retry_agent_run(AgentRun(run_id="run-2", pid=1))

        adapter.save(a_slice)

        assert issue.set_labels.call_args.args == ("story:10", "dispatched", "run:run-2", "retry:2")

    def test_save_should_write_the_failure_cause(self, repo: Mock) -> None:
        issue = _issue(11, "story:10", "dispatched", "run:run-1", "retry:2")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "dispatched", "run:run-1", "retry:2"))
        adapter = GithubSliceRepository(repo, _cache())
        a_slice = adapter.find(SliceId("11"))
        assert a_slice is not None
        a_slice.fail(AgentRunCause.OVERLOADED)

        adapter.save(a_slice)

        assert issue.set_labels.call_args.args == (
            "story:10",
            "failed",
            "run:run-1",
            "retry:2",
            "failure:overloaded",
        )

    def test_global_search_scopes_closed_reads_to_active_stories(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "story:10", "pending"),
            slice_node(12, "story:10", "merged", state="CLOSED"),
        )
        adapter = GithubSliceRepository(repo, _cache())

        slices = adapter.search()

        assert sorted(s.id.value for s in slices) == ["11", "12"]

    def test_global_search_does_not_read_slices_of_done_stories(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "story:10", "pending"),
            slice_node(20, "grooveloop", "done", state="CLOSED"),
            slice_node(21, "story:20", "merged", state="CLOSED"),
        )
        adapter = GithubSliceRepository(repo, _cache())

        slices = adapter.search()

        assert [s.id.value for s in slices] == ["11"]

    def test_global_search_keeps_a_story_active_while_one_of_its_slices_is_open(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(20, "grooveloop", "done", state="CLOSED"),
            slice_node(21, "story:20", "pending"),
            slice_node(22, "story:20", "merged", state="CLOSED"),
        )
        adapter = GithubSliceRepository(repo, _cache())

        slices = adapter.search()

        assert sorted(s.id.value for s in slices) == ["21", "22"]


@pytest.mark.integration
class TestGithubSliceRepositoryPullRequest:
    def test_find_resolves_the_pull_request_labeled_with_the_slice_when_no_pull_request_closes_it(
        self, repo: Mock
    ) -> None:
        wire_slice_graph(
            repo,
            slice_node(12, "story:10", "dispatched"),
            pull_requests=[pr_node(42, labels=["grooveloop", "slice:12"])],
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.number == PullRequestNumber(42)

    def test_find_resolves_the_pull_request_with_unaddressed_comments(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "story:10",
                "pr_open",
                "pr:42",
                pull_request=pr_node(
                    42, inline=[inline_comment("/grooveloop-implement: use the port", "src/x.py", 10, 555)]
                ),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.has_unaddressed_comments()

    def test_find_does_not_request_implementation_for_a_plain_comment(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "pr_open",
                "pr:42",
                pull_request=pr_node(42, inline=[inline_comment("a reply from the agent", "src/x.py", 10, 555)]),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.comments[0].directives == frozenset()
        assert a_slice.pull_request.has_unaddressed_comments() is False

    def test_find_reads_the_implement_directive_from_the_comment_body(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "pr_open",
                "pr:42",
                pull_request=pr_node(
                    42, inline=[inline_comment("/grooveloop-implement: rename the variable", "src/x.py", 10, 555)]
                ),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.comments[0].directives == {CommentDirective.IMPLEMENT}
        assert a_slice.pull_request.has_unaddressed_comments() is True

    def test_find_reads_every_directive_of_a_mixed_comment_body(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "pr_open",
                "pr:42",
                pull_request=pr_node(
                    42,
                    inline=[
                        inline_comment(
                            "/grooveloop-implement: rename the variable\n\n"
                            "/grooveloop-learn: inject through the constructor",
                            "src/x.py",
                            10,
                            555,
                        )
                    ],
                ),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.comments[0].directives == {
            CommentDirective.IMPLEMENT,
            CommentDirective.LEARN,
        }
        assert a_slice.pull_request.has_unaddressed_comments() is True

    def test_find_reads_the_review_comments_of_the_pull_request(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "pr_open",
                "pr:42",
                pull_request=pr_node(
                    42, inline=[inline_comment("use the SliceRepository port", "src/x.py", 10, 555, day=2)]
                ),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.comments == [
            ReviewComment(
                body="use the SliceRepository port",
                path="src/x.py",
                line=10,
                thread_id="555",
                created_at=datetime(2026, 6, 2, tzinfo=UTC),
                id="inline-555",
            )
        ]

    def test_find_reads_the_reactions_of_the_viewer_as_the_marks_of_each_comment(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "pr_open",
                "pr:42",
                pull_request=pr_node(
                    42,
                    inline=[
                        inline_comment(
                            "/grooveloop-implement: use the port",
                            node_id="PRRC_1",
                            reactions=[reaction_group("EYES"), reaction_group("ROCKET")],
                        )
                    ],
                    conversation=[
                        conversation_comment(
                            "/grooveloop-implement: rename the variable",
                            day=3,
                            node_id="IC_1",
                            reactions=[
                                reaction_group("EYES"),
                                reaction_group("ROCKET", viewer_has_reacted=False),
                                reaction_group("HEART"),
                            ],
                        )
                    ],
                ),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        inline, conversation = a_slice.pull_request.comments
        assert inline.id == "PRRC_1"
        assert inline.marks == {DirectiveMark.TAKEN, DirectiveMark.ADDRESSED}
        assert conversation.id == "IC_1"
        assert conversation.marks == {DirectiveMark.TAKEN}

    def test_find_reads_when_the_viewer_took_each_directive_still_without_the_addressed_mark(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "changes_requested",
                "pr:42",
                pull_request=pr_node(
                    42,
                    conversation=[
                        conversation_comment(
                            "/grooveloop-implement: rename the variable",
                            day=3,
                            node_id="IC_1",
                            reactions=[
                                reaction_group(
                                    "EYES",
                                    reacted_at="2026-06-05T00:00:00Z",
                                    others_reacted_at=["2026-06-07T00:00:00Z"],
                                )
                            ],
                        ),
                        conversation_comment(
                            "/grooveloop-implement: and test it",
                            day=4,
                            node_id="IC_2",
                            reactions=[
                                reaction_group("EYES", reacted_at="2026-06-06T00:00:00Z"),
                                reaction_group("ROCKET"),
                            ],
                        ),
                    ],
                ),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        taken, addressed = a_slice.pull_request.comments
        assert taken.taken_at == datetime(2026, 6, 5, tzinfo=UTC)
        assert addressed.taken_at is None

    def test_find_reads_conversation_comments_as_context_with_their_directive(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "pr_open",
                "pr:42",
                pull_request=pr_node(
                    42,
                    conversation=[conversation_comment("/grooveloop-implement: rename the variable", day=3)],
                    commit_dates=["2026-06-01T00:00:00Z"],
                ),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        conversation = a_slice.pull_request.comments[0]
        assert conversation.body == "/grooveloop-implement: rename the variable"
        assert conversation.path is None
        assert conversation.line is None
        assert conversation.thread_id is None
        assert conversation.directives == {CommentDirective.IMPLEMENT}
        assert a_slice.pull_request.has_unaddressed_comments() is True

    def test_find_does_not_request_implementation_for_a_plain_conversation_comment(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "pr_open",
                "pr:42",
                pull_request=pr_node(
                    42, conversation=[conversation_comment("Verdict: OK\n\n<!-- grooveloop:review -->", day=3)]
                ),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.comments[0].directives == frozenset()
        assert a_slice.pull_request.has_unaddressed_comments() is False

    def test_find_groups_inline_replies_under_the_root_comment_thread(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "pr_open",
                "pr:42",
                pull_request=pr_node(
                    42,
                    inline=[
                        inline_comment("use the SliceRepository port", "src/x.py", 10, 555, day=2),
                        inline_comment(
                            "/grooveloop-implement: and rename it", "src/x.py", 10, 556, day=3, reply_to=555
                        ),
                    ],
                ),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        thread_ids = [comment.thread_id for comment in a_slice.pull_request.comments]
        assert thread_ids == ["555", "555"]
        assert a_slice.pull_request.has_unaddressed_comments() is True

    def test_resolves_commits_after_review_when_the_branch_has_a_newer_commit(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "pr_open",
                "pr:42",
                pull_request=pr_node(
                    42,
                    inline=[
                        inline_comment(
                            "/grooveloop-implement: use the SliceRepository port", "src/x.py", 10, 555, day=2
                        )
                    ],
                    commit_dates=["2026-06-03T00:00:00Z"],
                ),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.has_commits_after_review() is True

    def test_resolves_the_merged_state_of_the_pull_request(self, repo: Mock) -> None:
        wire_slice_graph(
            repo, slice_node(12, "pr_open", "pr:42", pull_request=pr_node(42, state="MERGED", merged=True))
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.is_merged() is True

    def test_resolves_the_closed_state_of_the_pull_request(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(12, "pr_open", "pr:42", pull_request=pr_node(42, state="CLOSED")))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.is_closed_without_merge() is True

    def test_a_merged_pull_request_is_not_closed_without_merge(self, repo: Mock) -> None:
        wire_slice_graph(
            repo, slice_node(12, "pr_open", "pr:42", pull_request=pr_node(42, state="CLOSED", merged=True))
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.is_closed_without_merge() is False

    def test_pull_request_is_absent_when_no_pull_request_links_the_slice(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(12, "pr_open", pull_request=None))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is None

    def test_hydrates_the_review_summary_when_a_conversation_comment_has_the_marker(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "under_review",
                "pr:42",
                pull_request=pr_node(
                    42, conversation=[conversation_comment("Verdict: OK\n\n<!-- grooveloop:review -->")]
                ),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.has_a_fresh_review_summary() is True

    def test_hydrates_the_instant_of_the_review_summary_as_the_review_baseline(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "under_review",
                "pr:42",
                pull_request=pr_node(
                    42,
                    conversation=[
                        conversation_comment("Verdict: would request changes\n\n<!-- grooveloop:review -->", day=4)
                    ],
                    commit_dates=["2026-06-03T00:00:00Z"],
                ),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.has_a_fresh_review_summary() is True
        assert a_slice.pull_request.has_commits_after_review() is False

    def test_does_not_hydrate_the_review_summary_without_the_marker(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(
                12,
                "under_review",
                "pr:42",
                pull_request=pr_node(42, conversation=[conversation_comment("any comment")]),
            ),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.has_a_fresh_review_summary() is False

    @pytest.mark.parametrize("terminal_status", ["merged", "failed"])
    def test_does_not_hydrate_the_pull_request_of_terminal_slices(self, repo: Mock, terminal_status: str) -> None:
        wire_slice_graph(
            repo,
            slice_node(12, "story:10", terminal_status, "pr:42", pull_request=pr_node(42, state="MERGED", merged=True)),
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is None
        assert a_slice.pull_request_number == PullRequestNumber(42)


@pytest.mark.integration
class TestGithubSliceRepositoryLinkedPullRequest:
    def test_find_resolves_the_open_linked_pull_request_without_the_pr_label(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(12, "story:10", "dispatched", pull_request=pr_node(99, state="OPEN")))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.number == PullRequestNumber(99)
        assert a_slice.pull_request.is_open() is True

    def test_find_resolves_the_merged_linked_pull_request_across_all_states(self, repo: Mock) -> None:
        wire_slice_graph(
            repo, slice_node(12, "story:10", "dispatched", pull_request=pr_node(99, state="MERGED", merged=True))
        )
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is not None
        assert a_slice.pull_request.number == PullRequestNumber(99)
        assert a_slice.pull_request.is_merged() is True

    def test_find_resolves_no_pull_request_when_none_references_the_sub_issue(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(12, "story:10", "dispatched", pull_request=None))
        adapter = GithubSliceRepository(repo, _cache())

        a_slice = adapter.find(SliceId("12"))

        assert a_slice is not None
        assert a_slice.pull_request is None


@pytest.mark.integration
class TestGithubSliceRepositoryCache:
    def test_repeated_reads_within_the_ttl_hit_the_edge_once(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(11, "story:10", "pending"))
        adapter = GithubSliceRepository(repo, _cache())

        adapter.search(story_id=StoryId("10"))
        adapter.search(story_id=StoryId("10"))

        assert graph_reads(repo) == 1

    def test_save_invalidates_so_the_next_read_requeries_the_edge(self, repo: Mock) -> None:
        issue = _issue(11, "story:10", "pending")
        repo.get_issue.return_value = issue
        wire_slice_graph(repo, slice_node(11, "story:10", "pending"))
        adapter = GithubSliceRepository(repo, _cache())

        slices = adapter.search(story_id=StoryId("10"))
        assert slices
        a_slice = slices[0]
        a_slice.dispatch()
        adapter.save(a_slice)
        adapter.search(story_id=StoryId("10"))

        assert graph_reads(repo) == 2

    def test_a_shared_cache_invalidated_by_a_story_save_requeries_slice_reads(self, repo: Mock) -> None:
        cache = _cache()
        slice_repository = GithubSliceRepository(repo, cache)
        story_repository = GithubStoryRepository(repo, cache)
        parent = create_autospec(Issue, spec_set=True, instance=True)
        parent.body = "## Slices\n### First\n"
        parent.labels = [_label("grooveloop"), _label("ready_for_implementation")]
        repo.get_issue.return_value = parent
        wire_slice_graph(repo, slice_node(11, "story:10", "pending"))
        story = story_repository.find(SlicingStoryId("7"))
        assert story is not None
        story.materialize_slices(verify_deploy=False)

        slice_repository.search(story_id=StoryId("10"))
        story_repository.save(story)
        slice_repository.search(story_id=StoryId("10"))

        assert graph_reads(repo) == 2
