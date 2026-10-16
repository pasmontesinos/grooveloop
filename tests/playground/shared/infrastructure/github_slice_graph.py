from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

_THREAD_COMMENTS_MARKER = "PullRequestReviewThread"
_PULL_THREADS_MARKER = "reviewThreads(first: $page"
_PULL_COMMENTS_MARKER = "comments(first: $page"
_STORY_MARKER = "$storyLabel"
_LAST_CLOSED_MARKER = "states: [CLOSED]"
_ISSUES_MARKER = "issues("
_PULL_REQUEST_MARKER = "pullRequest(number: $number)"
_LABELED_PULLS_MARKER = "pullRequests("
_STORY_PULLS_MARKER = "$labels"
_ADD_REACTION_MARKER = "addReaction"
_REMOVE_REACTION_MARKER = "removeReaction"
_REACTED_AT = "2026-07-01T00:00:00Z"
_REACTIONS_MARKER = "... on Reactable"


def slice_node(
    number: int,
    *label_names: str,
    title: str = "",
    body: str = "",
    state: str = "OPEN",
    pull_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "labels": {"nodes": [{"name": name} for name in label_names]},
        "closedByPullRequestsReferences": {"nodes": [pull_request] if pull_request is not None else []},
    }


def pr_node(
    number: int,
    *,
    state: str = "OPEN",
    merged: bool = False,
    inline: list[dict[str, Any]] | None = None,
    conversation: list[dict[str, Any]] | None = None,
    commit_dates: list[str] | None = None,
    conversation_cursor: str | None = None,
    threads_cursor: str | None = None,
    thread_comments_cursor: str | None = None,
    thread_id: str = "thread-1",
    title: str = "",
    additions: int = 0,
    deletions: int = 0,
    changed_files: int = 0,
    updated_at: str = "2026-06-01T00:00:00Z",
    head_ref_oid: str = "0000000",
    mergeable: str = "UNKNOWN",
    checks: str | None = None,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    rollup = None if checks is None else {"state": checks}

    return {
        "number": number,
        "title": title,
        "state": state,
        "merged": merged,
        "additions": additions,
        "deletions": deletions,
        "changedFiles": changed_files,
        "updatedAt": updated_at,
        "headRefOid": head_ref_oid,
        "mergeable": mergeable,
        "commits": {
            "nodes": [{"commit": {"committedDate": date, "statusCheckRollup": rollup}} for date in commit_dates or []]
        },
        "comments": connection(conversation or [], next_cursor=conversation_cursor),
        "reviewThreads": connection(
            [thread_node(inline, thread_id=thread_id, next_cursor=thread_comments_cursor)] if inline else [],
            next_cursor=threads_cursor,
        ),
        "labels": {"nodes": [{"name": name} for name in labels or []]},
    }


def thread_node(
    comments: list[dict[str, Any]], *, thread_id: str = "thread-1", next_cursor: str | None = None
) -> dict[str, Any]:
    return {"id": thread_id, "comments": connection(comments, next_cursor=next_cursor)}


def connection(nodes: list[dict[str, Any]], *, next_cursor: str | None = None) -> dict[str, Any]:
    return {
        "pageInfo": {"hasNextPage": next_cursor is not None, "endCursor": next_cursor},
        "nodes": nodes,
    }


def inline_comment(
    body: str,
    path: str = "src/x.py",
    line: int = 10,
    database_id: int = 555,
    day: int = 2,
    reply_to: int | None = None,
    diff_hunk: str = "@@ @@",
    author: str | None = "octocat",
    node_id: str | None = None,
    reactions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id if node_id is not None else f"inline-{database_id}",
        "reactionGroups": reactions or [],
        "databaseId": database_id,
        "author": _author(author),
        "body": body,
        "path": path,
        "line": line,
        "diffHunk": diff_hunk,
        "createdAt": f"2026-06-0{day}T00:00:00Z",
        "replyTo": {"databaseId": reply_to} if reply_to is not None else None,
    }


def conversation_comment(
    body: str,
    day: int = 2,
    author: str | None = "octocat",
    node_id: str | None = None,
    reactions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id if node_id is not None else f"conversation-{day}",
        "reactionGroups": reactions or [],
        "body": body,
        "author": _author(author),
        "createdAt": f"2026-06-0{day}T00:00:00Z",
    }


def reaction_group(
    content: str,
    *,
    viewer_has_reacted: bool = True,
    reacted_at: str | None = None,
    others_reacted_at: list[str] | None = None,
) -> dict[str, Any]:
    viewer = [{"createdAt": reacted_at, "user": {"isViewer": True}}] if reacted_at is not None else []
    others = [{"createdAt": at, "user": {"isViewer": False}} for at in others_reacted_at or []]

    return {"content": content, "viewerHasReacted": viewer_has_reacted, "reactions": [*viewer, *others]}


def _author(login: str | None) -> dict[str, Any] | None:
    return None if login is None else {"login": login}


def pull_comments_page(nodes: list[dict[str, Any]], *, next_cursor: str | None = None) -> dict[str, Any]:
    return {"repository": {"pullRequest": {"comments": connection(nodes, next_cursor=next_cursor)}}}


def pull_threads_page(nodes: list[dict[str, Any]], *, next_cursor: str | None = None) -> dict[str, Any]:
    return {"repository": {"pullRequest": {"reviewThreads": connection(nodes, next_cursor=next_cursor)}}}


def thread_comments_page(nodes: list[dict[str, Any]], *, next_cursor: str | None = None) -> dict[str, Any]:
    return {"node": {"comments": connection(nodes, next_cursor=next_cursor)}}


def wire_story_graph(
    repo: Any,
    *nodes: dict[str, Any],
    comments: list[dict[str, Any]] | None = None,
    threads: list[dict[str, Any]] | None = None,
    thread_comments: list[dict[str, Any]] | None = None,
    pull_requests: list[dict[str, Any]] | None = None,
    page_size: int = 100,
    full_name: str = "owner/repo",
) -> None:
    repo.full_name = full_name
    universe = list(nodes)
    pulls = list(pull_requests or [])
    routes = [
        (_THREAD_COMMENTS_MARKER, iter(thread_comments or [])),
        (_PULL_THREADS_MARKER, iter(threads or [])),
        (_PULL_COMMENTS_MARKER, iter(comments or [])),
    ]

    def respond(document: str, variables: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        for marker, source in routes:
            if marker in document:
                return {}, {"data": next(source)}

        if _STORY_PULLS_MARKER in document:
            window = _page(_labeled_any(pulls, variables["labels"]), variables["after"], variables["page"])

            return {}, {"data": {"repository": {"pullRequests": window}}}

        if _LABELED_PULLS_MARKER in document:
            return {}, {"data": {"repository": {"pullRequests": {"nodes": _labeled(pulls, variables["label"])[:1]}}}}

        if _PULL_REQUEST_MARKER in document:
            return {}, {"data": {"repository": {"pullRequest": _node_of(pulls, variables["number"])}}}

        if _STORY_MARKER in document:
            return {}, {"data": _story_data(universe, variables, page_size)}

        if _LAST_CLOSED_MARKER in document:
            return {}, {"data": _last_closed_data(universe)}

        if _ISSUES_MARKER in document:
            return {}, {"data": _discovery_data(universe, variables, page_size)}

        return {}, {"data": {"repository": {"issue": _node_of(universe, variables["number"])}}}

    repo.requester.graphql_query.side_effect = _answering_reactions(respond, [*universe, *pulls])


def wire_slice_graph(
    repo: Any,
    *nodes: dict[str, Any],
    pull_requests: list[dict[str, Any]] | None = None,
    full_name: str = "acme/sample",
) -> None:
    wire_story_graph(repo, *nodes, pull_requests=pull_requests, full_name=full_name)


def _answering_reactions(
    respond: Callable[[str, dict[str, Any]], tuple[dict[str, Any], dict[str, Any]]],
    nodes: list[dict[str, Any]],
) -> Callable[[str, dict[str, Any]], tuple[dict[str, Any], dict[str, Any]]]:
    def answer(document: str, variables: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        if _ADD_REACTION_MARKER in document:
            _react(nodes, variables["subject"], variables["content"])
            return {}, {"data": {"addReaction": {"reaction": {"content": variables["content"]}}}}

        if _REMOVE_REACTION_MARKER in document:
            _unreact(nodes, variables["subject"], variables["content"])
            return {}, {"data": {"removeReaction": {"reaction": {"content": variables["content"]}}}}

        if _REACTIONS_MARKER in document:
            return {}, {"data": {"node": {"reactions": {"nodes": _eyes_of(nodes, variables["id"])}}}}

        return respond(document, variables)

    return answer


def _react(nodes: list[dict[str, Any]], comment_id: str, content: str) -> None:
    groups = _comment(nodes, comment_id)["reactionGroups"]
    group = next((group for group in groups if group["content"] == content), None)
    if group is None:
        groups.append(reaction_group(content, reacted_at=_REACTED_AT))
        return

    if group["viewerHasReacted"]:
        return

    group["viewerHasReacted"] = True
    group["reactions"].append({"createdAt": _REACTED_AT, "user": {"isViewer": True}})


def _unreact(nodes: list[dict[str, Any]], comment_id: str, content: str) -> None:
    for group in _comment(nodes, comment_id)["reactionGroups"]:
        if group["content"] == content:
            group["viewerHasReacted"] = False
            group["reactions"] = [reaction for reaction in group["reactions"] if not reaction["user"]["isViewer"]]


def _comment(nodes: list[dict[str, Any]], comment_id: str) -> dict[str, Any]:
    return next(comment for comment in _comments_of(nodes) if comment["id"] == comment_id)


def _eyes_of(nodes: list[dict[str, Any]], comment_id: str) -> list[dict[str, Any]]:
    return [
        reaction
        for group in _comment(nodes, comment_id)["reactionGroups"]
        if group["content"] == "EYES"
        for reaction in group["reactions"]
    ]


def _comments_of(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pulls = [pull for node in nodes for pull in node.get("closedByPullRequestsReferences", {"nodes": [node]})["nodes"]]
    conversation = [comment for pull in pulls for comment in pull.get("comments", {"nodes": []})["nodes"]]
    threads = [thread for pull in pulls for thread in pull.get("reviewThreads", {"nodes": []})["nodes"]]
    inline = [comment for thread in threads for comment in thread["comments"]["nodes"]]

    return conversation + inline


def reactions_added(repo: Any) -> list[tuple[str, str]]:
    calls = repo.requester.graphql_query.call_args_list

    return [
        (call.args[1]["subject"], call.args[1]["content"]) for call in calls if _ADD_REACTION_MARKER in call.args[0]
    ]


def story_pages(repo: Any) -> list[int]:
    calls = repo.requester.graphql_query.call_args_list

    return [call.args[1]["page"] for call in calls if _STORY_MARKER in call.args[0]]


def graph_reads(repo: Any) -> int:
    documents = [call.args[0] for call in repo.requester.graphql_query.call_args_list]

    return len(
        [
            document
            for document in documents
            if _ISSUES_MARKER in document and _STORY_MARKER not in document and _LAST_CLOSED_MARKER not in document
        ]
    )


def labeled_pull_reads(repo: Any) -> list[list[str]]:
    calls = repo.requester.graphql_query.call_args_list

    return [call.args[1]["labels"] for call in calls if _STORY_PULLS_MARKER in call.args[0]]


def labeled_pull_pages(repo: Any) -> list[int]:
    calls = repo.requester.graphql_query.call_args_list

    return [call.args[1]["page"] for call in calls if _STORY_PULLS_MARKER in call.args[0]]


def closed_story_reads(repo: Any) -> int:
    documents = [call.args[0] for call in repo.requester.graphql_query.call_args_list]

    return len([document for document in documents if _LAST_CLOSED_MARKER in document])


def _last_closed_data(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [{"number": node["number"], "labels": node["labels"]} for node in nodes if node["state"] == "CLOSED"]

    return {"repository": {"issues": {"nodes": closed[:1]}}}


def _discovery_data(nodes: list[dict[str, Any]], variables: dict[str, Any], page_size: int) -> dict[str, Any]:
    discovered = [{"number": node["number"], "labels": node["labels"]} for node in nodes if node["state"] == "OPEN"]

    return {"repository": {"issues": _page(discovered, variables["after"], page_size)}}


def _story_data(nodes: list[dict[str, Any]], variables: dict[str, Any], page_size: int) -> dict[str, Any]:
    slices = [node for node in nodes if variables["storyLabel"] in _labels_of(node)]

    return {
        "repository": {
            "issue": _node_of(nodes, variables["number"]),
            "issues": _page(slices, variables["after"], page_size),
        }
    }


def _page(nodes: list[dict[str, Any]], after: str | None, page_size: int) -> dict[str, Any]:
    start = int(after.removeprefix("cursor-")) if after is not None else 0
    window = nodes[start : start + page_size]
    end = start + len(window)
    has_next_page = end < len(nodes)

    return {
        "pageInfo": {"hasNextPage": has_next_page, "endCursor": f"cursor-{end}" if has_next_page else None},
        "nodes": window,
    }


def _node_of(nodes: list[dict[str, Any]], number: int) -> dict[str, Any] | None:
    return next((node for node in nodes if node["number"] == number), None)


def _labeled(pulls: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    return [pull for pull in pulls if label in _labels_of(pull)]


def _labeled_any(pulls: list[dict[str, Any]], labels: list[str]) -> list[dict[str, Any]]:
    return [pull for pull in pulls if set(labels) & set(_labels_of(pull))]


def _labels_of(node: dict[str, Any]) -> list[str]:
    return [label["name"] for label in node["labels"]["nodes"]]
