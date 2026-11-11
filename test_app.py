# test_app.py — TextIQ happy-flow test suite (front end + managers)
"""Run:  QT_QPA_PLATFORM=offscreen python3 -m pytest test_app.py -v"""
import os

import documents_manager as docs
import history_manager
import reminders_manager
from datetime import datetime, timedelta


# ============================================================
# Managers (pure logic, no UI)
# ============================================================

class TestDocumentsManager:
    def test_create_document_with_chosen_extension(self, tmp_path):
        path = docs.create_document(str(tmp_path), "My Notes", ext=".md")
        assert path.endswith(".md") and os.path.exists(path)

    def test_create_document_makes_unique_names(self, tmp_path):
        p1 = docs.create_document(str(tmp_path), "Same", ext=".txt")
        p2 = docs.create_document(str(tmp_path), "Same", ext=".txt")
        assert p1 != p2 and os.path.exists(p1) and os.path.exists(p2)

    def test_invalid_extension_falls_back(self, tmp_path):
        path = docs.create_document(str(tmp_path), "X", ext=".exe")
        assert path.endswith(docs.SUPPORTED_EXTS[0])

    def test_save_read_delete_roundtrip(self, tmp_path):
        path = docs.create_document(str(tmp_path), "RT", ext=".md")
        docs.save_document(path, "hello world")
        assert docs.read_document(path) == "hello world"
        docs.delete_document(path)
        assert not os.path.exists(path)

    def test_create_folder(self, tmp_path):
        folder = docs.create_folder(str(tmp_path), "Projects")
        assert os.path.isdir(folder)
        nested = docs.create_document(folder, "inside", ext=".md")
        assert os.path.dirname(nested) == folder

    def test_list_documents_shows_supported_only(self, tmp_path):
        docs.create_document(str(tmp_path), "a", ext=".md")
        docs.create_document(str(tmp_path), "b", ext=".txt")
        with open(tmp_path / "ignore.exe", "w") as f:
            f.write("x")
        found = docs.list_documents(str(tmp_path))
        assert len(found) == 2


class TestHistoryManager:
    def test_save_list_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(history_manager, "HISTORY_DIR", str(tmp_path))
        path = history_manager.save_transcription("raw text", "optimized text")
        sessions = history_manager.list_sessions()
        assert len(sessions) == 1 and sessions[0] == path
        raw, optimized = history_manager.load_session(path)
        assert raw == "raw text" and optimized == "optimized text"

    def test_empty_optimized_marker(self, tmp_path, monkeypatch):
        monkeypatch.setattr(history_manager, "HISTORY_DIR", str(tmp_path))
        path = history_manager.save_transcription("only raw", "")
        _raw, optimized = history_manager.load_session(path)
        assert optimized == ""


class TestRemindersManager:
    def test_add_due_and_mark_fired(self, tmp_path, monkeypatch):
        monkeypatch.setattr(reminders_manager, "REMINDERS_FILE", str(tmp_path / "r.json"))
        past = datetime.now() - timedelta(minutes=5)
        reminders_manager.add_reminder("/docs/a.md", "a", past)
        due = reminders_manager.due_reminders()
        assert len(due) == 1 and due[0]["title"] == "a"
        reminders_manager.mark_fired("/docs/a.md")
        assert reminders_manager.due_reminders() == []

    def test_future_reminder_not_due(self, tmp_path, monkeypatch):
        monkeypatch.setattr(reminders_manager, "REMINDERS_FILE", str(tmp_path / "r.json"))
        future = datetime.now() + timedelta(hours=2)
        reminders_manager.add_reminder("/docs/b.md", "b", future)
        assert reminders_manager.due_reminders() == []
        assert len(reminders_manager.pending_reminders()) == 1

    def test_one_reminder_per_document(self, tmp_path, monkeypatch):
        monkeypatch.setattr(reminders_manager, "REMINDERS_FILE", str(tmp_path / "r.json"))
        reminders_manager.add_reminder("/docs/c.md", "c", datetime.now())
        reminders_manager.add_reminder("/docs/c.md", "c", datetime.now())
        assert len(reminders_manager.pending_reminders()) == 1


# ============================================================
# App-level happy flows (Qt widgets)
# ============================================================

class TestAppStartup:
    def test_panels_exist(self, app_window):
        w = app_window
        assert w.pane1 is not None and w.pane2 is None
        assert w.docs_tree.model() is w.fs_model
        assert w.status_label.text() != ""
        assert w.dictate_btn is not None and w.optimize_btn is not None

    def test_status_bar_items(self, app_window):
        w = app_window
        assert "words" in w.status_words_label.text()
        assert w.status_git_label.text().startswith("⎇")


class TestDocumentFlow:
    def _open_doc(self, w, tmp_path, name="flow", ext=".md"):
        path = docs.create_document(
            w.settings["documents_folder"], name, ext=ext)
        w.open_document_path(path)
        return path

    def test_open_document_shows_tab_and_content(self, app_window):
        w = app_window
        path = self._open_doc(w, None)
        assert w.pane1.tabs.count() == 1
        assert w.pane1.path == path
        assert w.editor is not None and not w.editor.isReadOnly()

    def test_typing_sets_dirty_and_word_count(self, app_window):
        w = app_window
        self._open_doc(w, None)
        w.editor.setPlainText("hello brave new world")
        assert w.pane1.dirty is True
        assert w.pane1.tabs.tabText(0).startswith("●")
        assert "4 words" in w.status_words_label.text()

    def test_save_clears_dirty_and_writes_markdown(self, app_window):
        w = app_window
        path = self._open_doc(w, None)
        w.editor.setPlainText("persist me")
        w.save_document()
        assert w.pane1.dirty is False
        assert "●" not in w.pane1.tabs.tabText(0)
        assert "persist me" in docs.read_document(path)

    def test_txt_extension_saves_plain_text(self, app_window):
        w = app_window
        path = self._open_doc(w, None, ext=".txt")
        w.editor.setPlainText("plain only")
        w.save_document()
        with open(path) as f:
            assert f.read() == "plain only"

    def test_close_tab_keeps_file_on_disk(self, app_window):
        w = app_window
        path = self._open_doc(w, None)
        w.editor.setPlainText("content")
        w.close_tab(w.pane1, 0)  # dirty -> auto-saved on close
        assert w.pane1.tabs.count() == 0
        assert os.path.exists(path)
        assert "content" in docs.read_document(path)

    def test_switching_tabs_restores_content(self, app_window):
        w = app_window
        p1 = self._open_doc(w, None, name="one")
        w.editor.setPlainText("first doc")
        p2 = self._open_doc(w, None, name="two")
        w.editor.setPlainText("second doc")
        w.pane1.tabs.setCurrentIndex(0)  # back to first
        assert "first doc" in w.editor.toPlainText()
        assert w.pane1.path == p1
        _ = p2


class TestEditingFeatures:
    def test_task_marker_cycle(self, app_window):
        w = app_window
        w.editor.setPlainText("my task line")
        cursor = w.editor.textCursor()
        cursor.movePosition(cursor.Start)
        w.editor.setTextCursor(cursor)
        w.toggle_task_marker()
        assert w.editor.toPlainText().startswith("☐ ")
        w.toggle_task_marker()
        assert w.editor.toPlainText().startswith("☑ ")
        w.toggle_task_marker()
        assert w.editor.toPlainText().startswith("my task line")

    def test_bold_toggle_applies_format(self, app_window):
        w = app_window
        w.editor.setPlainText("bold me")
        w.editor.selectAll()
        w.toggle_bold()
        from PyQt5.QtGui import QFont
        assert w.editor.currentCharFormat().fontWeight() >= QFont.Bold

    def test_markdown_autofmt_heading(self, app_window):
        w = app_window
        w.editor.setPlainText("# ")
        cursor = w.editor.textCursor()
        cursor.movePosition(cursor.End)
        w.editor.setTextCursor(cursor)
        w._maybe_markdown_autofmt(w.pane1)
        fmt = w.editor.currentCharFormat()
        from PyQt5.QtGui import QFont
        assert fmt.fontWeight() >= QFont.Bold
        assert w.editor.toPlainText().strip() == ""

    def test_markdown_autofmt_task(self, app_window):
        w = app_window
        w.editor.setPlainText("[] ")
        cursor = w.editor.textCursor()
        cursor.movePosition(cursor.End)
        w.editor.setTextCursor(cursor)
        w._maybe_markdown_autofmt(w.pane1)
        assert w.editor.toPlainText().startswith("☐ ")


class TestSpeechHelpers:
    def test_voice_commands(self, app_window):
        result = app_window._apply_voice_commands(
            "hello comma world period new line next")
        assert result == "hello, world.\nnext"

    def test_voice_commands_case_insensitive(self, app_window):
        assert "?" in app_window._apply_voice_commands("really Question Mark")

    def test_chunk_overlap_dedup(self, app_window):
        merged = app_window._merge_chunk_text(
            "the quick brown fox", "brown fox jumps high")
        assert merged == "jumps high"

    def test_chunk_no_overlap(self, app_window):
        merged = app_window._merge_chunk_text("first chunk", "second chunk")
        assert merged == "second chunk"


class TestContentSearch:
    def test_search_opens_temporary_unsaved_tab(self, app_window):
        w = app_window
        folder = w.settings["documents_folder"]
        p = docs.create_document(folder, "findable", ext=".md")
        docs.save_document(p, "the secret keyword is here")
        w.doc_search.setText("secret keyword")
        w.run_content_search()
        pane = w.pane1
        idx = pane.tabs.currentIndex()
        meta = pane.tabs.tabData(idx)
        assert meta.get("search") is True
        assert meta.get("path") is None          # never saved
        assert pane.editor.isReadOnly()
        assert "findable" in pane.editor.toPlainText()
        assert pane.dirty is False

    def test_search_no_results_still_opens_tab(self, app_window):
        w = app_window
        w.doc_search.setText("nothing-matches-this")
        w.run_content_search()
        assert "No matches" in w.pane1.editor.toPlainText()


class TestSpeechHistory:
    def test_history_item_opens_readonly_tab(self, app_window, tmp_path, monkeypatch):
        w = app_window
        path = history_manager.save_transcription("a past session", "")
        w._refresh_history()
        assert w.history_list.count() == 1
        w.load_history_item(w.history_list.item(0))
        idx = w.pane1.tabs.currentIndex()
        meta = w.pane1.tabs.tabData(idx)
        assert meta.get("history") is True
        assert w.editor.isReadOnly()
        assert "a past session" in w.editor.toPlainText()


class TestSplitView:
    def test_toggle_split_creates_and_closes_second_pane(self, app_window):
        w = app_window
        w.toggle_split_view()
        assert w.pane2 is not None
        assert w.panes_splitter.count() == 2
        w.toggle_split_view()
        assert w.pane2 is None
        assert w.active_pane is w.pane1
