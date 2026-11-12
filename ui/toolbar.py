# ui/toolbar.py — top bar (minimal) + second row (all editing tools)
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton

import config


def _sep(toolbar):
    line = QFrame()
    line.setObjectName("toolbarSep")
    line.setFrameShape(QFrame.VLine)
    toolbar.addWidget(line)


def _lbl(toolbar, text):
    """Small gray group label inside a toolbar row (e.g. 'Size:', 'Color:')."""
    label = QLabel(text)
    label.setObjectName("subtitle")
    toolbar.addWidget(label)


def build_toolbar(app, main_layout):
    """Row 1: document actions · find · optimize+preset · split · push · settings."""
    toolbar = QHBoxLayout()
    toolbar.setContentsMargins(10, 6, 10, 6)
    toolbar.setSpacing(6)

    toolbar.addWidget(app._tool_btn("📄 New", "New document", app.new_document))
    toolbar.addWidget(app._tool_btn("📂 Open", "Open a file from any folder", app.open_external_file))
    toolbar.addWidget(app._tool_btn("💾 Save", "Save document", app.save_document))
    toolbar.addWidget(app._tool_btn("🔍", "Find in document (⌘F / Ctrl+F)", app.show_find))

    _sep(toolbar)

    toolbar.addWidget(app._tool_btn("✨ Optimize", "Optimize selection / full document with Claude", app.optimize_document_text))
    app.preset_combo = QComboBox()
    app.preset_combo.addItems(list(config.OPTIMIZE_PRESETS.keys()))
    app.preset_combo.setFixedWidth(115)
    app.preset_combo.setToolTip("Optimize style")
    toolbar.addWidget(app.preset_combo)

    _sep(toolbar)

    # Split & Push hidden for now — methods/shortcuts still available
    app.git_push_btn = app._tool_btn("⬆ Push", "Commit & push all files to git", app.push_to_git)
    toolbar.addStretch()

    # Panel toggles (VS Code style)
    toolbar.addWidget(app._tool_btn("◧", "Toggle sidebar (⌘B)", app.toggle_left_panel))
    toolbar.addWidget(app._tool_btn("◨", "Toggle speech panel (⌘⇧B)", app.toggle_right_panel))

    # Top-right: search across ALL documents
    app.global_search = QLineEdit()
    app.global_search.setPlaceholderText("Search all documents…")
    app.global_search.setFixedWidth(220)
    app.global_search.setToolTip("Search inside every document (Enter)")
    app.global_search.returnPressed.connect(
        lambda: app.run_content_search(app.global_search.text())
    )
    toolbar.addWidget(app.global_search)
    toolbar.addWidget(app._tool_btn(
        "Search", "Search all documents",
        lambda: app.run_content_search(app.global_search.text()),
    ))

    app.settings_btn = QPushButton("Settings")
    app.settings_btn.setObjectName("settingsBtn")
    _cog = app._fa("fa5s.cog")
    if not _cog.isNull():
        app.settings_btn.setIcon(_cog)
        app.settings_btn.setIconSize(QSize(16, 16))
    app.settings_btn.setFixedHeight(28)
    app.settings_btn.setMinimumWidth(95)  # fits the full "Settings" text
    app.settings_btn.setToolTip("Open Settings")
    app.settings_btn.setCursor(Qt.PointingHandCursor)
    app.settings_btn.clicked.connect(app.open_settings)
    toolbar.addWidget(app.settings_btn)

    main_layout.addLayout(toolbar)


def build_tools_row(app, main_layout):
    """Row 2: all editing tools."""
    tools_row = QHBoxLayout()
    tools_row.setContentsMargins(10, 0, 10, 6)
    tools_row.setSpacing(4)

    tools_row.addWidget(app._tool_btn("↶", "Undo", lambda: app.editor.undo()))
    tools_row.addWidget(app._tool_btn("↷", "Redo", lambda: app.editor.redo()))
    _sep(tools_row)

    _lbl(tools_row, "Style:")
    app.bold_btn = app._tool_btn("B", "Bold (⌘B)", app.toggle_bold)
    tools_row.addWidget(app.bold_btn)
    app.italic_btn = app._tool_btn("I", "Italic (⌘I)", app.toggle_italic)
    tools_row.addWidget(app.italic_btn)
    app.underline_btn = app._tool_btn("U", "Underline (⌘U)", app.toggle_underline)
    tools_row.addWidget(app.underline_btn)
    tools_row.addWidget(app._tool_btn("S", "Strikethrough", app.toggle_strikethrough))
    _sep(tools_row)

    tools_row.addWidget(app._tool_btn("H1", "Heading 1", lambda: app.apply_heading(1)))
    tools_row.addWidget(app._tool_btn("H2", "Heading 2", lambda: app.apply_heading(2)))
    tools_row.addWidget(app._tool_btn("H3", "Heading 3", lambda: app.apply_heading(3)))
    _lbl(tools_row, "Size:")
    app.font_size_combo = QComboBox()
    app.font_size_combo.setEditable(True)
    app.font_size_combo.addItems(["10", "11", "12", "14", "18", "24"])
    app.font_size_combo.setCurrentText("12")
    app.font_size_combo.setFixedWidth(60)
    app.font_size_combo.setToolTip("Font size")
    app.font_size_combo.activated.connect(app._apply_font_size)
    tools_row.addWidget(app.font_size_combo)
    _lbl(tools_row, "Color:")
    tools_row.addWidget(app._tool_btn("🎨", "Text color", app.pick_text_color))
    tools_row.addWidget(app._tool_btn("🖍", "Highlight color", app.pick_highlight_color))
    _sep(tools_row)

    _lbl(tools_row, "List:")
    tools_row.addWidget(app._tool_btn("•", "Bullet list", lambda: app.toggle_list(False)))
    tools_row.addWidget(app._tool_btn("1.", "Numbered list", lambda: app.toggle_list(True)))
    tools_row.addWidget(app._tool_btn("☐", "Insert / toggle a task checkbox on this line", app.toggle_task_marker))
    _sep(tools_row)

    _lbl(tools_row, "Align:")
    tools_row.addWidget(app._tool_btn("⇤", "Align left", lambda: app.align(Qt.AlignLeft)))
    tools_row.addWidget(app._tool_btn("☰", "Align center", lambda: app.align(Qt.AlignCenter)))
    tools_row.addWidget(app._tool_btn("⇥", "Align right", lambda: app.align(Qt.AlignRight)))
    tools_row.addWidget(app._tool_btn("≣", "Justify", lambda: app.align(Qt.AlignJustify)))
    _sep(tools_row)

    _lbl(tools_row, "Insert:")
    tools_row.addWidget(app._tool_btn("</>", "Code snippet style", app.apply_code_style))
    tools_row.addWidget(app._tool_btn("▦", "Insert table", app.insert_table))
    tools_row.addWidget(app._tool_btn("🧹", "Clear formatting", app.clear_formatting))
    tools_row.addStretch()
    main_layout.addLayout(tools_row)
