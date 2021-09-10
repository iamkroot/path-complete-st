import os
from typing import List

import sublime
import sublime_plugin
from sublime import CompletionItem, CompletionList, Region


class TogglePathCompletionCommand(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit) -> None:
        PathCompletionListener.is_enabled = not PathCompletionListener.is_enabled
        # print("is_enabled", PathCompletionListener.is_enabled)
        # if PathCompletionListener.is_enabled:
        self.view.run_command("auto_complete", {"disable_auto_insert": True, "next_completion_if_showing": False})


class PathCompletionListener(sublime_plugin.ViewEventListener):
    # TODO: Cache the recent completions (use file watchers to invalidate cache)
    is_enabled = True
    COMPLETION_FLAGS = sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS

    def __init__(self, view: sublime.View) -> None:
        super().__init__(view)
        self.is_active = False
        self.sep = os.sep

    def on_activated(self):
        self.verify_activation()

    def on_deactivated(self):
        self.is_active = False

    def in_enabled_scope(self):
        # activate the path completions if inside string scope
        view: sublime.View = self.view
        sel = view.sel()
        if not sel:
            return
        return view.match_selector(sel[0].begin(), "string")

    def verify_activation(self):
        if self.in_enabled_scope():
            if not self.is_active:
                self.is_active = True
                # print("activated")
            return True
        elif self.is_active:
            # print("deactivated")
            self.is_active = False
        return False

    def on_selection_modified_async(self):
        if not self.is_enabled:
            assert not self.is_active
            return
        if not self.verify_activation():
            return

    def on_modified_async(self):
        if not self.is_enabled or not self.verify_activation():
            return
        end = self.view.sel()[0].end()
        endch = self.view.substr(end - 1)
        if endch == self.sep:
            # otherwise it won't show
            self.view.run_command("hide_auto_complete")

        self.view.run_command("auto_complete",
                              {"disable_auto_insert": True, "next_completion_if_showing": False})
        # FIXME: Breaks if parent is prefix of child: "~/Downloads/Downloads New/"

    def on_text_command(self, name, args):
        if name == "auto_complete":
            # we need to re-check if the scope is valid in case user manually triggerd completion
            self.verify_activation()

    def get_completion_item(self, basename: str, entry: os.DirEntry) -> CompletionItem:
        """Adapted from AutoFileName plugin"""
        name = entry.name
        annotation = ""
        annotation_head = ""
        annotation_head_kind = sublime.KIND_ID_AMBIGUOUS
        details_head = ""
        details_parts = []

        if entry.is_dir():
            name += self.sep
            annotation = "Dir"
            annotation_head = "📁"
            annotation_head_kind = sublime.KIND_ID_MARKUP
            details_head = "Directory"
        elif entry.is_file():
            annotation = "File"
            annotation_head = "📄"  # TODO: More icons
            annotation_head_kind = sublime.KIND_ID_MARKUP
            details_head = "File"
            # details_parts.append("Size: " + naturalsize(os.stat(fullpath).st_size))

        return CompletionItem(
            trigger=name,
            annotation=annotation,
            completion=name,
            kind=(annotation_head_kind, annotation_head, details_head),
            details=", ".join(details_parts)
        )

    def on_query_completions(self, prefix: str, locations: List[int]) -> CompletionList:
        if not self.is_enabled or not self.is_active:
            return None
        if not locations:
            return
        pt = locations[0]
        # TODO: Is -1 required?
        scope_region = self.view.extract_scope(pt - 1)
        # left_region = scope_region.intersection(Region(scope_region.begin(), pt))
        left_region = Region(scope_region.begin(), pt)
        # TODO: Make use of right_region too?
        typed_str = self.view.substr(left_region)
        typed_str = typed_str.strip('"\'')

        basename, part = os.path.split(typed_str)
        # FIXME: Doesn't deal with multiple trailing separators: "/path///abc"
        # print(f"{basename=} {part=}")

        if basename.startswith('~'):
            basename = os.path.expanduser(basename)

        entries = []
        # TODO: Currently, `part` is ignored completely
        if basename and os.path.isdir(basename):
            try:
                entries = os.scandir(basename)
            except PermissionError:
                pass
        else:
            return None
        items = (self.get_completion_item(basename, entry) for entry in entries)
        completions = CompletionList(items, self.COMPLETION_FLAGS)
        # print(completions)
        return completions
