from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, create_autospec

import pytest
from github.Repository import Repository

from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.shared.infrastructure.github_story_graph import GithubStoryGraph
from tests.playground.shared.infrastructure.github_slice_graph import (
    closed_story_reads,
    conversation_comment,
    graph_reads,
    inline_comment,
    labeled_pull_pages,
    labeled_pull_reads,
    pr_node,
    pull_comments_page,
    pull_threads_page,
    slice_node,
    story_pages,
    thread_comments_page,
    thread_node,
    wire_story_graph,
)


def _cache() -> GithubReadCache:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = datetime(2026, 8, 25, tzinfo=UTC)

    return GithubReadCache(clock)


@pytest.fixture
def repo() -> Any:
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.full_name = "owner/repo"

    return repo


@pytest.mark.integration
class TestGithubStoryGraph:
    def test_should_group_each_story_with_its_slices(self, repo: Mock) -> None:
        wire_story_graph(repo, slice_node(10, "grooveloop"), slice_node(11, "grooveloop", "story:10", "order:1"))
        graph = GithubStoryGraph(repo, _cache())

        stories = graph.stories()

        assert [entry.story.number for entry in stories] == [10]
        assert [a_slice.number for a_slice in stories[0].slices] == [11]

    def test_should_leave_a_lesson_issue_out_of_the_slices_of_its_story(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", "order:1"),
            slice_node(500, "grooveloop", "lesson", "story:10", "source_pr:42"),
        )
        graph = GithubStoryGraph(repo, _cache())

        stories = graph.stories()

        assert [a_slice.number for a_slice in stories[0].slices] == [11]

    def test_should_order_the_slices_of_a_story_by_their_order_label(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(13, "grooveloop", "story:10", "order:2"),
            slice_node(11, "grooveloop", "story:10", "order:1"),
        )
        graph = GithubStoryGraph(repo, _cache())

        stories = graph.stories()

        assert [a_slice.number for a_slice in stories[0].slices] == [11, 13]

    def test_should_keep_the_order_of_the_stories_returned_by_the_repository(self, repo: Mock) -> None:
        wire_story_graph(repo, slice_node(20, "grooveloop"), slice_node(10, "grooveloop"))
        graph = GithubStoryGraph(repo, _cache())

        stories = graph.stories()

        assert [entry.story.number for entry in stories] == [20, 10]

    def test_should_bring_the_last_closed_story_when_no_story_is_open(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop", "done", state="CLOSED"),
            slice_node(11, "grooveloop", "story:10", "order:1", state="CLOSED"),
        )
        graph = GithubStoryGraph(repo, _cache())

        stories = graph.stories()

        assert [entry.story.number for entry in stories] == [10]
        assert [a_slice.number for a_slice in stories[0].slices] == [11]

    def test_should_leave_the_closed_story_out_while_another_story_is_open(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(20, "grooveloop"),
            slice_node(10, "grooveloop", "done", state="CLOSED"),
        )
        graph = GithubStoryGraph(repo, _cache())

        stories = graph.stories()

        assert [entry.story.number for entry in stories] == [20]

    def test_should_not_ask_for_the_closed_story_while_another_story_is_open(self, repo: Mock) -> None:
        wire_story_graph(repo, slice_node(20, "grooveloop"))
        graph = GithubStoryGraph(repo, _cache())

        graph.stories()

        assert closed_story_reads(repo) == 0

    def test_should_ask_for_the_closed_story_once_when_no_story_is_open(self, repo: Mock) -> None:
        wire_story_graph(repo, slice_node(10, "grooveloop", "done", state="CLOSED"))
        graph = GithubStoryGraph(repo, _cache())

        graph.stories()

        assert closed_story_reads(repo) == 1

    def test_should_follow_the_pagination_of_the_live_stories(self, repo: Mock) -> None:
        wire_story_graph(repo, slice_node(20, "grooveloop"), slice_node(10, "grooveloop"), page_size=1)
        graph = GithubStoryGraph(repo, _cache())

        stories = graph.stories()

        assert [entry.story.number for entry in stories] == [20, 10]

    def test_should_follow_the_pagination_of_the_slices_of_a_story(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", "order:1"),
            slice_node(12, "grooveloop", "story:10", "order:2"),
            page_size=1,
        )
        graph = GithubStoryGraph(repo, _cache())

        stories = graph.stories()

        assert [a_slice.number for a_slice in stories[0].slices] == [11, 12]

    def test_should_ignore_slices_whose_story_is_not_in_the_graph(self, repo: Mock) -> None:
        wire_story_graph(repo, slice_node(10, "grooveloop"), slice_node(11, "grooveloop", "story:99", "order:1"))
        graph = GithubStoryGraph(repo, _cache())

        stories = graph.stories()

        assert [entry.story.number for entry in stories] == [10]
        assert stories[0].slices == []

    def test_should_read_the_title_the_body_and_the_labels_of_a_story(self, repo: Mock) -> None:
        wire_story_graph(repo, slice_node(10, "grooveloop", "sliced", title="one query", body="## Slices"))
        graph = GithubStoryGraph(repo, _cache())

        story = graph.stories()[0].story

        assert story.title == "one query"
        assert story.body == "## Slices"
        assert story.labels == ["grooveloop", "sliced"]

    def test_should_reuse_the_cached_graph_within_the_ttl(self, repo: Mock) -> None:
        wire_story_graph(repo, slice_node(10, "grooveloop"))
        graph = GithubStoryGraph(repo, _cache())

        graph.stories()
        graph.stories()

        assert graph_reads(repo) == 1


@pytest.mark.integration
class TestGithubStoryGraphLiveStories:
    def test_should_not_read_a_closed_story_without_open_issues(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop", "sliced"),
            slice_node(11, "grooveloop", "story:10", "pending"),
            slice_node(20, "grooveloop", "done", state="CLOSED"),
            slice_node(21, "grooveloop", "story:20", "merged", state="CLOSED"),
        )
        graph = GithubStoryGraph(repo, _cache())

        assert [node.number for node in graph.nodes()] == [10, 11]

    def test_should_keep_a_closed_story_alive_while_one_of_its_issues_is_open(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(20, "grooveloop", "done", state="CLOSED"),
            slice_node(21, "grooveloop", "story:20", "pending"),
            slice_node(22, "grooveloop", "story:20", "merged", state="CLOSED"),
        )
        graph = GithubStoryGraph(repo, _cache())

        assert sorted(node.number for node in graph.nodes()) == [20, 21, 22]

    def test_should_read_the_closed_slices_of_a_live_story(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop", "sliced"),
            slice_node(11, "grooveloop", "story:10", "merged", state="CLOSED"),
        )
        graph = GithubStoryGraph(repo, _cache())

        assert [node.number for node in graph.nodes()] == [10, 11]

    def test_should_not_take_an_issue_without_the_loop_label_as_a_story(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(30, "enhancement"),
            slice_node(31, "grooveloop", "story:30", "pending"),
        )
        graph = GithubStoryGraph(repo, _cache())

        assert [node.number for node in graph.nodes()] == [31]

    def test_should_ask_for_a_bounded_page_of_slices(self, repo: Mock) -> None:
        wire_story_graph(repo, slice_node(10, "grooveloop"), slice_node(11, "grooveloop", "story:10"))
        graph = GithubStoryGraph(repo, _cache())

        graph.nodes()

        assert story_pages(repo) == [20]

    def test_should_not_query_more_when_the_history_grows(self, repo: Mock) -> None:
        history = [slice_node(number, "grooveloop", "done", state="CLOSED") for number in range(100, 120)]
        wire_story_graph(repo, slice_node(10, "grooveloop"), *history)
        graph = GithubStoryGraph(repo, _cache())

        graph.nodes()

        assert repo.requester.graphql_query.call_count == 2


@pytest.mark.integration
class TestGithubStoryGraphNodes:
    def test_should_expose_every_issue_of_the_graph_as_a_flat_node(self, repo: Mock) -> None:
        wire_story_graph(repo, slice_node(10, "grooveloop"), slice_node(11, "grooveloop", "story:10"))
        graph = GithubStoryGraph(repo, _cache())

        assert [node.number for node in graph.nodes()] == [10, 11]

    def test_should_read_the_closed_state_of_an_issue(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", state="CLOSED"),
        )
        graph = GithubStoryGraph(repo, _cache())

        assert graph.nodes()[1].closed is True

    def test_should_share_the_cache_between_the_flat_and_the_grouped_view(self, repo: Mock) -> None:
        wire_story_graph(repo, slice_node(10, "grooveloop"))
        graph = GithubStoryGraph(repo, _cache())

        graph.nodes()
        graph.stories()

        assert graph_reads(repo) == 1

    def test_should_read_the_pull_request_that_closes_an_issue(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", pull_request=pr_node(42, state="MERGED", merged=True)),
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert pull_request.number == 42
        assert pull_request.merged is True
        assert pull_request.closed is False

    def test_should_read_the_review_summary_of_the_pull_request(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(
                11,
                "grooveloop",
                "story:10",
                pull_request=pr_node(
                    42,
                    title="Member roles",
                    additions=180,
                    deletions=22,
                    changed_files=7,
                    updated_at="2026-06-03T10:00:00Z",
                    head_ref_oid="abc123",
                    mergeable="MERGEABLE",
                    commit_dates=["2026-06-03T00:00:00Z"],
                    checks="SUCCESS",
                ),
            ),
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert pull_request.title == "Member roles"
        assert pull_request.additions == 180
        assert pull_request.deletions == 22
        assert pull_request.changed_files == 7
        assert pull_request.updated_at == datetime(2026, 6, 3, 10, tzinfo=UTC)
        assert pull_request.head_ref_oid == "abc123"
        assert pull_request.mergeable == "MERGEABLE"
        assert pull_request.checks == "SUCCESS"

    def test_should_leave_the_checks_empty_when_the_last_commit_has_no_checks(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", pull_request=pr_node(42, commit_dates=["2026-06-03T00:00:00Z"])),
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert pull_request.checks is None

    def test_should_read_the_last_commit_date_of_the_pull_request(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", pull_request=pr_node(42, commit_dates=["2026-06-03T00:00:00Z"])),
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert pull_request.last_commit_at == datetime(2026, 6, 3, tzinfo=UTC)

    def test_should_read_the_conversation_and_the_review_comments(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(
                11,
                "grooveloop",
                "story:10",
                pull_request=pr_node(
                    42,
                    conversation=[conversation_comment("summary")],
                    inline=[inline_comment("use the port")],
                ),
            ),
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert [comment.body for comment in pull_request.conversation] == ["summary"]
        assert pull_request.review[0].database_id == 555
        assert pull_request.review[0].path == "src/x.py"
        assert pull_request.review[0].line == 10
        assert pull_request.review[0].reply_to_id is None

    def test_should_read_the_root_of_an_inline_reply(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(
                11,
                "grooveloop",
                "story:10",
                pull_request=pr_node(42, inline=[inline_comment("use the port", database_id=556, reply_to=555)]),
            ),
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert pull_request.review[0].reply_to_id == 555

    def test_should_leave_the_pull_request_empty_when_no_pull_request_closes_the_issue(self, repo: Mock) -> None:
        wire_story_graph(repo, slice_node(10, "grooveloop"), slice_node(11, "grooveloop", "story:10"))
        graph = GithubStoryGraph(repo, _cache())

        assert graph.nodes()[1].pull_request is None

    def test_should_expose_the_diff_hunk_of_an_inline_review_comment(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(
                11,
                "grooveloop",
                "story:10",
                pull_request=pr_node(90, inline=[inline_comment("x", diff_hunk="@@ -1 +1 @@")]),
            ),
        )
        graph = GithubStoryGraph(repo, _cache())

        node = graph.nodes()[1]

        assert node.pull_request is not None
        assert node.pull_request.review[0].diff_hunk == "@@ -1 +1 @@"

    def test_should_read_the_author_of_every_comment(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(
                11,
                "grooveloop",
                "story:10",
                pull_request=pr_node(
                    42,
                    conversation=[conversation_comment("summary", author="reviewer-bot")],
                    inline=[inline_comment("use the port", author=None)],
                ),
            ),
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert pull_request.conversation[0].author == "reviewer-bot"
        assert pull_request.review[0].author is None


@pytest.mark.integration
class TestGithubStoryGraphCommentPagination:
    def test_should_read_every_conversation_comment_of_a_truncated_pull_request(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(
                11,
                "grooveloop",
                "story:10",
                pull_request=pr_node(42, conversation=[conversation_comment("uno")], conversation_cursor="cursor-1"),
            ),
            comments=[pull_comments_page([conversation_comment("dos", day=3)])],
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert [comment.body for comment in pull_request.conversation] == ["uno", "dos"]

    def test_should_follow_the_conversation_pagination_until_the_last_page(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(
                11,
                "grooveloop",
                "story:10",
                pull_request=pr_node(42, conversation=[conversation_comment("uno")], conversation_cursor="cursor-1"),
            ),
            comments=[
                pull_comments_page([conversation_comment("dos", day=3)], next_cursor="cursor-2"),
                pull_comments_page([conversation_comment("tres", day=4)]),
            ],
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert [comment.body for comment in pull_request.conversation] == ["uno", "dos", "tres"]

    def test_should_read_every_review_thread_of_a_truncated_pull_request(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(
                11,
                "grooveloop",
                "story:10",
                pull_request=pr_node(42, inline=[inline_comment("uno")], threads_cursor="cursor-1"),
            ),
            threads=[pull_threads_page([thread_node([inline_comment("dos")], thread_id="thread-2")])],
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert [comment.body for comment in pull_request.review] == ["uno", "dos"]

    def test_should_read_every_comment_of_a_truncated_review_thread(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(
                11,
                "grooveloop",
                "story:10",
                pull_request=pr_node(42, inline=[inline_comment("uno")], thread_comments_cursor="cursor-1"),
            ),
            thread_comments=[thread_comments_page([inline_comment("dos", database_id=556, reply_to=555)])],
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert [comment.body for comment in pull_request.review] == ["uno", "dos"]

    def test_should_read_every_comment_of_a_thread_that_arrives_by_pagination(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(
                11,
                "grooveloop",
                "story:10",
                pull_request=pr_node(42, inline=[inline_comment("uno")], threads_cursor="cursor-1"),
            ),
            threads=[
                pull_threads_page([thread_node([inline_comment("dos")], thread_id="thread-2", next_cursor="cursor-2")])
            ],
            thread_comments=[thread_comments_page([inline_comment("tres")])],
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert [comment.body for comment in pull_request.review] == ["uno", "dos", "tres"]

    def test_should_not_query_again_when_no_comment_connection_is_truncated(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(
                11,
                "grooveloop",
                "story:10",
                pull_request=pr_node(42, conversation=[conversation_comment("uno")], inline=[inline_comment("dos")]),
            ),
        )
        graph = GithubStoryGraph(repo, _cache())

        graph.nodes()

        assert repo.requester.graphql_query.call_count == 2


@pytest.mark.integration
class TestGithubStoryGraphPullRequest:
    def test_should_read_a_pull_request_by_its_number(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            pull_requests=[
                pr_node(
                    77,
                    state="CLOSED",
                    updated_at="2026-09-25T10:00:00Z",
                    head_ref_oid="abc123",
                    conversation=[conversation_comment("uno")],
                    inline=[inline_comment("dos")],
                )
            ],
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.pull_request(77)

        assert pull_request is not None
        assert pull_request.number == 77
        assert pull_request.closed is True
        assert pull_request.updated_at == datetime(2026, 9, 25, 10, tzinfo=UTC)
        assert pull_request.head_ref_oid == "abc123"
        assert [comment.body for comment in pull_request.conversation + pull_request.review] == ["uno", "dos"]

    def test_should_read_every_conversation_comment_of_a_truncated_pull_request(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            pull_requests=[pr_node(77, conversation=[conversation_comment("uno")], conversation_cursor="cursor-1")],
            comments=[pull_comments_page([conversation_comment("dos", day=3)])],
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.pull_request(77)

        assert pull_request is not None
        assert [comment.body for comment in pull_request.conversation] == ["uno", "dos"]

    def test_should_find_no_pull_request_for_a_number_that_does_not_exist(self, repo: Mock) -> None:
        wire_story_graph(repo)
        graph = GithubStoryGraph(repo, _cache())

        assert graph.pull_request(77) is None


@pytest.mark.integration
class TestGithubStoryGraphLabeledPullRequest:
    def test_should_read_the_pull_request_labeled_with_the_slice_when_no_pull_request_closes_it(
        self, repo: Mock
    ) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", "dispatched"),
            pull_requests=[pr_node(42, labels=["grooveloop", "slice:11"])],
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert pull_request.number == 42
        assert labeled_pull_reads(repo) == [["slice:11"]]

    def test_should_read_the_merged_state_of_the_labeled_pull_request(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", "pr_open"),
            pull_requests=[pr_node(42, state="MERGED", merged=True, labels=["slice:11"])],
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert pull_request.merged is True

    def test_should_read_every_comment_of_a_truncated_labeled_pull_request(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", "pr_open"),
            pull_requests=[
                pr_node(
                    42, conversation=[conversation_comment("uno")], conversation_cursor="cursor-1", labels=["slice:11"]
                )
            ],
            comments=[pull_comments_page([conversation_comment("dos", day=3)])],
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert [comment.body for comment in pull_request.conversation] == ["uno", "dos"]

    def test_should_keep_the_pull_request_that_closes_the_slice_over_a_labeled_one(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", "dispatched", pull_request=pr_node(42)),
            pull_requests=[pr_node(43, labels=["slice:11"])],
        )
        graph = GithubStoryGraph(repo, _cache())

        pull_request = graph.nodes()[1].pull_request

        assert pull_request is not None
        assert pull_request.number == 42
        assert labeled_pull_reads(repo) == []

    def test_should_leave_the_pull_request_empty_when_no_pull_request_carries_the_slice_label(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", "dispatched"),
            pull_requests=[pr_node(43, labels=["slice:12"])],
        )
        graph = GithubStoryGraph(repo, _cache())

        assert graph.nodes()[1].pull_request is None

    def test_should_not_look_for_a_labeled_pull_request_of_a_closed_slice_or_of_the_story(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", "merged", state="CLOSED"),
            slice_node(12, "grooveloop", "story:10", "pending"),
        )
        graph = GithubStoryGraph(repo, _cache())

        graph.nodes()

        assert labeled_pull_reads(repo) == [["slice:12"]]

    def test_should_ask_once_for_the_pull_requests_of_every_open_slice_without_a_closing_pull_request(
        self, repo: Mock
    ) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", "dispatched"),
            slice_node(12, "grooveloop", "story:10", "pending"),
            slice_node(13, "grooveloop", "story:10", "pr_open"),
        )
        graph = GithubStoryGraph(repo, _cache())

        graph.nodes()

        assert labeled_pull_reads(repo) == [["slice:11", "slice:12", "slice:13"]]

    def test_should_give_each_slice_the_most_recent_pull_request_with_its_label(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", "pr_open"),
            slice_node(12, "grooveloop", "story:10", "dispatched"),
            slice_node(13, "grooveloop", "story:10", "pending"),
            pull_requests=[
                pr_node(45, labels=["slice:12"]),
                pr_node(44, labels=["slice:11"]),
                pr_node(42, state="CLOSED", labels=["slice:11"]),
            ],
        )
        graph = GithubStoryGraph(repo, _cache())

        pulls = {node.number: node.pull_request for node in graph.nodes()}

        assert {number: pull.number if pull else None for number, pull in pulls.items()} == {
            10: None,
            11: 44,
            12: 45,
            13: None,
        }

    def test_should_leave_the_label_of_a_slice_with_a_closing_pull_request_out_of_the_query(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", "pr_open", pull_request=pr_node(42)),
            slice_node(12, "grooveloop", "story:10", "dispatched"),
            pull_requests=[pr_node(43, labels=["slice:11"]), pr_node(44, labels=["slice:12"])],
        )
        graph = GithubStoryGraph(repo, _cache())

        pulls = [node.pull_request.number if node.pull_request else None for node in graph.nodes()]

        assert pulls == [None, 42, 44]
        assert labeled_pull_reads(repo) == [["slice:12"]]

    def test_should_follow_the_pagination_of_the_labeled_pull_requests(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            slice_node(11, "grooveloop", "story:10", "pr_open"),
            slice_node(12, "grooveloop", "story:10", "pr_open"),
            pull_requests=[
                pr_node(46, labels=["slice:11"]),
                pr_node(45, state="CLOSED", labels=["slice:11"]),
                pr_node(44, state="CLOSED", labels=["slice:11"]),
                pr_node(43, labels=["slice:12"]),
            ],
        )
        graph = GithubStoryGraph(repo, _cache())

        pulls = [node.pull_request.number if node.pull_request else None for node in graph.nodes()]

        assert pulls == [None, 46, 43]
        assert labeled_pull_pages(repo) == [2, 2]

    def test_should_ask_for_at_most_a_hundred_labeled_pull_requests_per_page(self, repo: Mock) -> None:
        wire_story_graph(
            repo,
            slice_node(10, "grooveloop"),
            *[slice_node(number, "grooveloop", "story:10", "pending") for number in range(11, 112)],
        )
        graph = GithubStoryGraph(repo, _cache())

        graph.nodes()

        assert labeled_pull_pages(repo) == [100]
