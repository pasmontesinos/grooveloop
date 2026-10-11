from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grooveloop.delivery.domain.review_comment import ReviewComment
    from grooveloop.delivery.domain.slice import Slice


class AddressingTask:
    def build(self, a_slice: Slice, *, automatic: bool) -> str:
        comments = a_slice.pull_request.comments if a_slice.pull_request is not None else []
        rendered = self._render_comments([comment for comment in comments if not comment.only_requests_learning()])

        return (
            f"{self._headline(a_slice, automatic=automatic)} "
            "Implement the requested changes, reply in each review thread and push to the PR branch.\n\n"
            f"## Review comments\n{rendered}"
        )

    def resumption(self, a_slice: Slice) -> str:
        return (
            f'Your previous turn ended without pushing commits to the PR of the slice "{a_slice.title}". Continue in '
            "this same worktree from where you left off: finish the requested changes, reply in each review thread "
            "and push to the PR branch. Do not run commands in the background or end your turn waiting for a task: "
            "wait in the foreground for long commands. You work in autonomous mode: do not ask questions and "
            "finish when you push."
        )

    def _headline(self, a_slice: Slice, *, automatic: bool) -> str:
        if automatic:
            return f'Address the blocking verdict of the automatic reviewer on the PR of the slice "{a_slice.title}".'

        return f'Address the "Request changes" review on the PR of the slice "{a_slice.title}".'

    def _render_comments(self, comments: list[ReviewComment]) -> str:
        return "\n\n".join(self._render_thread(header, thread) for header, thread in self._group_by_thread(comments))

    def _group_by_thread(self, comments: list[ReviewComment]) -> list[tuple[str, list[ReviewComment]]]:
        threads: dict[str, list[ReviewComment]] = {}
        conversation: list[ReviewComment] = []

        for comment in comments:
            if comment.thread_id is None:
                conversation.append(comment)
            else:
                threads.setdefault(comment.thread_id, []).append(comment)

        grouped = []
        for thread in threads.values():
            ordered = sorted(thread, key=lambda comment: comment.created_at)
            grouped.append((self._thread_header(ordered[0]), ordered))

        grouped.sort(key=lambda item: item[1][0].created_at)

        if conversation:
            grouped.append(("Conversation", sorted(conversation, key=lambda comment: comment.created_at)))

        return grouped

    def _thread_header(self, root: ReviewComment) -> str:
        if root.path is not None and root.line is not None:
            return f"Thread {root.path}:{root.line}"

        return "Thread"

    def _render_thread(self, header: str, thread: list[ReviewComment]) -> str:
        lines = [f"### {header}"]
        lines.extend(f"- {comment.body}" for comment in thread)

        return "\n".join(lines)
