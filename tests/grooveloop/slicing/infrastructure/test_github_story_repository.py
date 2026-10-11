from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock, create_autospec

import pytest
from github.Issue import Issue
from github.Label import Label
from github.Repository import Repository

from grooveloop.delivery.domain.slice_status import SliceStatus
from grooveloop.delivery.domain.story_id import StoryId as DeliveryStoryId
from grooveloop.delivery.infrastructure.github_slice_repository import GithubSliceRepository
from grooveloop.shared.domain.clock import Clock
from grooveloop.shared.infrastructure.github_read_cache import GithubReadCache
from grooveloop.slicing.domain.story_id import StoryId
from grooveloop.slicing.domain.story_status import StoryStatus
from grooveloop.slicing.infrastructure.github_story_repository import GithubStoryRepository
from tests.grooveloop.delivery.mothers.slice_mother import SliceMother
from tests.playground.shared.infrastructure.github_slice_graph import graph_reads, slice_node, wire_slice_graph


def _label(name: str) -> Any:
    label = create_autospec(Label, spec_set=True, instance=True)
    label.name = name

    return label


def _cache() -> GithubReadCache:
    clock = create_autospec(Clock, spec_set=True, instance=True)
    clock.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)

    return GithubReadCache(clock)


@pytest.fixture
def repo() -> Any:
    repo = create_autospec(Repository, spec_set=True, instance=True)
    repo.full_name = "owner/repo"

    return repo


@pytest.mark.integration
class TestGithubStoryRepository:
    def test_find_should_return_story_with_parsed_spec(self, repo: Mock) -> None:
        issue = create_autospec(Issue, spec_set=True, instance=True)
        issue.body = "## Slices\n### First\n### Second\n"
        issue.labels = [_label("grooveloop"), _label("ready_for_implementation")]
        repo.get_issue.return_value = issue
        adapter = GithubStoryRepository(repo, _cache())

        story = adapter.find(StoryId("7"))

        repo.get_issue.assert_called_once_with(7)
        assert story is not None
        assert len(story.spec.items) == 2
        assert story.status == StoryStatus.READY_FOR_IMPLEMENTATION

    def test_find_should_mark_sliced_when_label_present(self, repo: Mock) -> None:
        issue = create_autospec(Issue, spec_set=True, instance=True)
        issue.body = "## Slices\n### Only\n"
        issue.labels = [_label("grooveloop"), _label("sliced")]
        repo.get_issue.return_value = issue
        adapter = GithubStoryRepository(repo, _cache())

        story = adapter.find(StoryId("7"))

        assert story is not None
        assert story.status == StoryStatus.SLICED

    def test_find_should_mark_draft_when_no_lifecycle_label_is_present(self, repo: Mock) -> None:
        issue = create_autospec(Issue, spec_set=True, instance=True)
        issue.body = "## Slices\n### Only\n"
        issue.labels = [_label("grooveloop")]
        repo.get_issue.return_value = issue
        adapter = GithubStoryRepository(repo, _cache())

        story = adapter.find(StoryId("7"))

        assert story is not None
        assert story.status == StoryStatus.DRAFT

    def test_search_should_read_the_whole_graph_once(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(7, "grooveloop", "ready_for_implementation", body="## Slices\n### First\n"))
        adapter = GithubStoryRepository(repo, _cache())

        adapter.search()

        assert graph_reads(repo) == 1
        repo.get_issues.assert_not_called()

    def test_search_should_only_return_the_open_stories_when_asked_for_them(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(7, "grooveloop", "done", body="## Slices\n### First\n", state="CLOSED"))
        adapter = GithubStoryRepository(repo, _cache())

        assert adapter.search(open=True) == []

    def test_search_should_only_return_the_closed_stories_when_asked_for_them(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(80, "grooveloop", "done", body="## Slices\n### First\n", state="CLOSED"),
            slice_node(81, "grooveloop", "story:80", "pending"),
        )
        adapter = GithubStoryRepository(repo, _cache())

        assert [story.id.value for story in adapter.search(open=False)] == ["80"]

    def test_search_should_return_open_and_closed_stories_without_the_open_criterion(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(80, "grooveloop", "done", title="feature", body="## Slices\n### First\n", state="CLOSED"),
            slice_node(81, "grooveloop", "story:80", "pending"),
        )
        adapter = GithubStoryRepository(repo, _cache())

        stories = adapter.search()

        assert [story.id.value for story in stories] == ["80"]
        assert stories[0].status == StoryStatus.DONE

    def test_search_should_ignore_sub_issues_that_belong_to_a_story(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(7, "grooveloop", "ready_for_implementation", body="## Slices\n### First\n"),
            slice_node(12, "grooveloop", "story:7", "pending"),
        )
        adapter = GithubStoryRepository(repo, _cache())

        stories = adapter.search()

        assert [story.id.value for story in stories] == ["7"]

    def test_search_should_exclude_issues_without_a_parseable_spec(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(5, "grooveloop", "ready_for_implementation", body="A planning note"))
        adapter = GithubStoryRepository(repo, _cache())

        assert adapter.search() == []

    def test_search_should_expose_the_issue_title_as_the_story_title(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(7, "grooveloop", "ready_for_implementation", title="watch panel", body="## Slices\n### First\n"),
        )
        adapter = GithubStoryRepository(repo, _cache())

        assert [story.title for story in adapter.search()] == ["watch panel"]

    def test_search_should_include_stories_marked_ready_for_implementation(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(80, "grooveloop", "ready_for_implementation", title="feature", body="## Slices\n### First\n"),
        )
        adapter = GithubStoryRepository(repo, _cache())

        stories = adapter.search()

        assert [story.id.value for story in stories] == ["80"]
        assert stories[0].status == StoryStatus.READY_FOR_IMPLEMENTATION

    def test_search_should_exclude_drafts_when_filtering_by_ready_for_implementation(self, repo: Mock) -> None:
        wire_slice_graph(repo, slice_node(80, "grooveloop", title="feature", body="## Slices\n### First\n"))
        adapter = GithubStoryRepository(repo, _cache())

        assert adapter.search(status=StoryStatus.READY_FOR_IMPLEMENTATION) == []

    def test_search_should_filter_by_status(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(7, "grooveloop", "ready_for_implementation", body="## Slices\n### First\n"),
            slice_node(8, "grooveloop", "sliced", body="## Slices\n### First\n"),
        )
        adapter = GithubStoryRepository(repo, _cache())

        stories = adapter.search(status=StoryStatus.SLICED)

        assert [story.id.value for story in stories] == ["8"]

    def test_find_should_return_none_when_issue_lacks_the_marker_label(self, repo: Mock) -> None:
        issue = create_autospec(Issue, spec_set=True, instance=True)
        issue.body = "## Slices\n### Only\n"
        issue.labels = [_label("ready_for_implementation")]
        repo.get_issue.return_value = issue
        adapter = GithubStoryRepository(repo, _cache())

        assert adapter.find(StoryId("10")) is None

    def test_find_should_mark_done_when_label_present(self, repo: Mock) -> None:
        issue = create_autospec(Issue, spec_set=True, instance=True)
        issue.body = "## Slices\n### Only\n"
        issue.labels = [_label("grooveloop"), _label("done")]
        repo.get_issue.return_value = issue
        adapter = GithubStoryRepository(repo, _cache())

        story = adapter.find(StoryId("7"))

        assert story is not None
        assert story.status == StoryStatus.DONE

    def test_save_should_close_the_parent_and_swap_sliced_for_done_when_story_is_done(self, repo: Mock) -> None:
        parent = create_autospec(Issue, spec_set=True, instance=True)
        parent.body = "## Slices\n### First\n"
        parent.labels = [_label("grooveloop"), _label("ready_for_implementation"), _label("sliced")]
        repo.get_issue.return_value = parent
        adapter = GithubStoryRepository(repo, _cache())
        story = adapter.find(StoryId("7"))
        assert story is not None
        story.complete()

        adapter.save(story)

        labels_set = parent.set_labels.call_args.args
        assert "done" in labels_set
        assert "sliced" not in labels_set
        assert "ready_for_implementation" not in labels_set
        parent.edit.assert_called_once_with(state="closed")

    def test_save_should_create_a_child_issue_per_slice_and_mark_parent_sliced(self, repo: Mock) -> None:
        parent = create_autospec(Issue, spec_set=True, instance=True)
        parent.body = "## Slices\n### First\n- **Type:** infra\n### Second\n- **Type:** vertical\n"
        parent.labels = [_label("grooveloop"), _label("ready_for_implementation")]
        repo.get_issue.return_value = parent
        adapter = GithubStoryRepository(repo, _cache())
        story = adapter.find(StoryId("7"))
        assert story is not None
        story.materialize_slices(verify_deploy=False)

        adapter.save(story)

        assert repo.create_issue.call_count == 2
        repo.create_issue.assert_any_call(
            title="First", body="- **Type:** infra", labels=["grooveloop", "story:7", "pending", "order:1"]
        )
        parent.add_to_labels.assert_called_once_with("sliced")

    def test_save_should_write_the_depends_on_marker_with_resolved_issue_numbers(self, repo: Mock) -> None:
        parent = create_autospec(Issue, spec_set=True, instance=True)
        parent.body = (
            "## Slices\n### First\n- **Type:** infra\n### Second\n- **Type:** vertical\n- **Depends on:** slice 1\n"
        )
        parent.labels = [_label("grooveloop"), _label("ready_for_implementation")]
        repo.get_issue.return_value = parent
        first_issue = create_autospec(Issue, spec_set=True, instance=True)
        first_issue.number = 101
        second_issue = create_autospec(Issue, spec_set=True, instance=True)
        second_issue.number = 102
        repo.create_issue.side_effect = [first_issue, second_issue]
        adapter = GithubStoryRepository(repo, _cache())
        story = adapter.find(StoryId("7"))
        assert story is not None
        story.materialize_slices(verify_deploy=False)

        adapter.save(story)

        repo.create_issue.assert_any_call(
            title="Second",
            body=(
                "- **Type:** vertical\n- **Depends on:** slice 1\n\n"
                "<!-- grooveloop:depends-on -->\n**Depends on:** #101"
            ),
            labels=["grooveloop", "story:7", "pending", "order:2"],
        )

    def test_save_should_write_the_marker_saying_none_when_independence_is_declared(self, repo: Mock) -> None:
        parent = create_autospec(Issue, spec_set=True, instance=True)
        parent.body = "## Slices\n### First\n- **Type:** infra\n- **Depends on:** none\n"
        parent.labels = [_label("grooveloop"), _label("ready_for_implementation")]
        repo.get_issue.return_value = parent
        adapter = GithubStoryRepository(repo, _cache())
        story = adapter.find(StoryId("7"))
        assert story is not None
        story.materialize_slices(verify_deploy=False)

        adapter.save(story)

        repo.create_issue.assert_called_once_with(
            title="First",
            body=("- **Type:** infra\n- **Depends on:** none\n\n<!-- grooveloop:depends-on -->\n**Depends on:** none"),
            labels=["grooveloop", "story:7", "pending", "order:1"],
        )

    def test_save_should_leave_the_body_untouched_without_the_depends_on_bullet(self, repo: Mock) -> None:
        parent = create_autospec(Issue, spec_set=True, instance=True)
        parent.body = "## Slices\n### First\n- **Type:** infra\n"
        parent.labels = [_label("grooveloop"), _label("ready_for_implementation")]
        repo.get_issue.return_value = parent
        adapter = GithubStoryRepository(repo, _cache())
        story = adapter.find(StoryId("7"))
        assert story is not None
        story.materialize_slices(verify_deploy=False)

        adapter.save(story)

        repo.create_issue.assert_called_once_with(
            title="First",
            body="- **Type:** infra",
            labels=["grooveloop", "story:7", "pending", "order:1"],
        )

    def test_repeated_reads_within_the_ttl_hit_the_edge_once(self, repo: Mock) -> None:
        wire_slice_graph(
            repo,
            slice_node(80, "grooveloop", "ready_for_implementation", title="feature", body="## Slices\n### First\n"),
        )
        adapter = GithubStoryRepository(repo, _cache())

        adapter.search()
        adapter.search()

        assert graph_reads(repo) == 1

    def test_save_invalidates_so_the_next_read_requeries_the_edge(self, repo: Mock) -> None:
        parent = create_autospec(Issue, spec_set=True, instance=True)
        parent.body = "## Slices\n### First\n- **Type:** infra\n"
        parent.labels = [_label("grooveloop"), _label("ready_for_implementation")]
        repo.get_issue.return_value = parent
        wire_slice_graph(repo)
        adapter = GithubStoryRepository(repo, _cache())
        story = adapter.find(StoryId("7"))
        assert story is not None
        story.materialize_slices(verify_deploy=False)

        adapter.search()
        adapter.save(story)
        adapter.search()

        assert graph_reads(repo) == 2

    def test_a_shared_cache_invalidated_by_a_slice_save_requeries_story_reads(self, repo: Mock) -> None:
        cache = _cache()
        story_repository = GithubStoryRepository(repo, cache)
        slice_repository = GithubSliceRepository(repo, cache)
        sub_issue = create_autospec(Issue, spec_set=True, instance=True)
        sub_issue.number = 11
        sub_issue.labels = [_label("story:7"), _label("pending")]
        repo.get_issue.return_value = sub_issue
        wire_slice_graph(repo)
        a_slice = SliceMother.create(slice_id="11", status=SliceStatus.PENDING, story_id=DeliveryStoryId("7").value)
        a_slice.dispatch()

        story_repository.search()
        slice_repository.save(a_slice)
        story_repository.search()

        assert graph_reads(repo) == 2

    def test_save_should_label_new_sub_issues_for_deploy_verification(self, repo: Mock) -> None:
        parent = create_autospec(Issue, spec_set=True, instance=True)
        parent.body = "## Slices\n### First\n- **Type:** infra\n"
        parent.labels = [_label("grooveloop"), _label("ready_for_implementation")]
        repo.get_issue.return_value = parent
        adapter = GithubStoryRepository(repo, _cache())
        story = adapter.find(StoryId("7"))
        assert story is not None
        story.materialize_slices(verify_deploy=True)

        adapter.save(story)

        repo.create_issue.assert_called_once_with(
            title="First",
            body="- **Type:** infra",
            labels=["grooveloop", "story:7", "pending", "order:1", "verify-deploy"],
        )

    def test_save_should_not_label_sub_issues_when_verification_is_off(self, repo: Mock) -> None:
        parent = create_autospec(Issue, spec_set=True, instance=True)
        parent.body = "## Slices\n### First\n- **Type:** infra\n"
        parent.labels = [_label("grooveloop"), _label("ready_for_implementation")]
        repo.get_issue.return_value = parent
        adapter = GithubStoryRepository(repo, _cache())
        story = adapter.find(StoryId("7"))
        assert story is not None
        story.materialize_slices(verify_deploy=False)

        adapter.save(story)

        assert "verify-deploy" not in repo.create_issue.call_args.kwargs["labels"]
