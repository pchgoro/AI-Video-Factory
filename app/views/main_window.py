from __future__ import annotations

import json
import webbrowser
import logging
import re
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QStringListModel, QUrl
from PySide6.QtGui import QGuiApplication, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget

    MULTIMEDIA_AVAILABLE = True
except Exception:
    QAudioOutput = None
    QMediaPlayer = None
    QVideoWidget = None
    MULTIMEDIA_AVAILABLE = False

from config import AppPaths
from dialogs.settings_dialog import SettingsDialog
from models import DEFAULT_DURATIONS, PROGRESS_ITEMS, ProjectInfo, PromptTemplate, WIZARD_STEPS
from services.dashboard_service import DashboardService
from services.image_import_service import ImageImportError, ImageImportService
from services.parser import ChatGptAnswerParser, ChatGptParseError
from services.project_service import ProjectService
from services.prompt_builder import build_bulk_image_prompt, build_chatgpt_prompt
from services.settings_service import SettingsService
from services.tag_service import TagService
from services.template_service import TemplateService
from services.topic_service import TopicService
from services.video_render_service import VideoRenderService
from services.voicevox_service import VoicevoxService
from video_editors.factory import create_video_editor


DARK_STYLE = """
QWidget { background: #1e1e1e; color: #d4d4d4; font-family: "Yu Gothic UI", "Meiryo"; font-size: 13px; }
QLineEdit, QTextEdit, QComboBox, QSpinBox, QListWidget {
    background: #252526; color: #d4d4d4; border: 1px solid #3c3c3c; border-radius: 4px; padding: 6px;
}
QPushButton { background: #2d2d30; color: #ffffff; border: 1px solid #3c3c3c; border-radius: 4px; padding: 7px 10px; }
QPushButton:hover { background: #3a3d41; }
QPushButton:pressed { background: #094771; }
QGroupBox { border: 1px solid #3c3c3c; border-radius: 4px; margin-top: 14px; padding: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QTabWidget::pane { border: 1px solid #3c3c3c; }
QTabBar::tab { background: #252526; color: #d4d4d4; padding: 8px 12px; border: 1px solid #3c3c3c; }
QTabBar::tab:selected { background: #1e1e1e; border-bottom-color: #1e1e1e; }
QSplitter::handle { background: #4a4a4a; }
QSplitter::handle:vertical { min-height: 8px; margin: 2px 0; }
QSplitter::handle:horizontal { min-width: 8px; margin: 0 2px; }
"""


class ImageDropArea(QLabel):
    """画像ファイルを受け取るドラッグ＆ドロップ領域です。"""

    def __init__(self, parent: "MainWindow") -> None:
        super().__init__("ここに画像をドラッグ＆ドロップ\nまたは Ctrl+V で貼り付け")
        self.main_window = parent
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(110)
        self.setStyleSheet("border: 2px dashed #5a5a5a; border-radius: 6px; color: #cfcfcf;")

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        files = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if files:
            self.main_window.import_image_files(files)
            event.acceptProposedAction()
            return
        event.ignore()


class MainWindow(QMainWindow):
    """UIは操作の橋渡しだけを担当し、保存、解析、音声生成、動画生成はサービス層へ委譲します。"""

    def __init__(
        self,
        paths: AppPaths,
        settings_service: SettingsService,
        project_service: ProjectService,
        topic_service: TopicService,
        template_service: TemplateService,
        dashboard_service: DashboardService,
        video_render_service: VideoRenderService,
        voicevox_service: VoicevoxService,
        version_info: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.paths = paths
        self.settings_service = settings_service
        self.project_service = project_service
        self.topic_service = topic_service
        self.template_service = template_service
        self.dashboard_service = dashboard_service
        self.video_render_service = video_render_service
        self.voicevox_service = voicevox_service
        self.version_info = version_info or {}
        self.logger = logging.getLogger("ai_video_factory")
        self.parser = ChatGptAnswerParser()
        self.image_import_service = ImageImportService()
        self.tag_service = TagService()
        self.settings = settings_service.load()
        self.current_project: ProjectInfo | None = None
        self.projects: list[ProjectInfo] = []
        self.topics: list[str] = []
        self.templates: list[PromptTemplate] = []

        self.media_player = None
        self.audio_output = None
        self.video_widget = None

        self.auto_parse_timer = QTimer(self)
        self.auto_parse_timer.setSingleShot(True)
        self.auto_parse_timer.setInterval(500)
        self.auto_parse_timer.timeout.connect(self.auto_parse_answer)

        self.setWindowTitle("AI Video Factory")
        self.resize(1440, 900)
        self.setStyleSheet(DARK_STYLE)

        self._build_ui()
        self._load_initial_data()

    def keyPressEvent(self, event) -> None:
        focus_widget = self.focusWidget()
        if event.matches(QKeySequence.Paste) and not isinstance(focus_widget, (QLineEdit, QTextEdit)):
            self.paste_images_from_clipboard()
            return
        super().keyPressEvent(event)

    def _build_ui(self) -> None:
        root = QSplitter(Qt.Horizontal)
        root.addWidget(self._scrollable_page(self._build_left_panel()))
        root.addWidget(self._build_main_tabs())
        root.setSizes([350, 1090])
        self.setCentralWidget(root)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        header = QHBoxLayout()
        title = QLabel("AI Video Factory")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        settings_button = QPushButton("設定")
        settings_button.clicked.connect(self.open_settings)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(settings_button)
        layout.addLayout(header)

        self.project_search = QLineEdit()
        self.project_search.setPlaceholderText("タイトル / テーマ / ジャンル / 投稿日 / シリーズ / タグで検索")
        self.project_search.textChanged.connect(self.refresh_project_list)
        layout.addWidget(self.project_search)

        self.genre_filter = QComboBox()
        self.genre_filter.currentTextChanged.connect(self.refresh_project_list)
        layout.addWidget(self.genre_filter)

        self.project_list = QListWidget()
        self.project_list.itemSelectionChanged.connect(self.load_selected_project)
        self.project_list.setMinimumHeight(80)
        self.project_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        project_list_widget = self.project_list

        topic_box = QGroupBox("一括ネタ管理")
        topic_layout = QVBoxLayout(topic_box)
        self.topic_search = QLineEdit()
        self.topic_search.setPlaceholderText("ネタ検索")
        self.topic_search.textChanged.connect(self.refresh_topic_list)
        topic_layout.addWidget(self.topic_search)
        self.topic_list = QListWidget()
        self.topic_list.itemDoubleClicked.connect(self.use_selected_topic)
        topic_layout.addWidget(self.topic_list)
        self.topic_edit = QLineEdit()
        self.topic_edit.setPlaceholderText("テーマを追加・編集")
        topic_layout.addWidget(self.topic_edit)

        topic_buttons = QHBoxLayout()
        for text, handler in [("追加", self.add_topic), ("編集", self.update_topic), ("削除", self.delete_topic)]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            topic_buttons.addWidget(button)
        topic_layout.addLayout(topic_buttons)

        self.bulk_topics = QTextEdit()
        self.bulk_topics.setPlaceholderText("複数テーマを1行ずつ入力")
        self.bulk_topics.setFixedHeight(100)
        topic_layout.addWidget(self.bulk_topics)
        start_bulk_button = QPushButton("制作開始")
        start_bulk_button.clicked.connect(self.start_bulk_projects)
        topic_layout.addWidget(start_bulk_button)

        memo_box = QGroupBox("メモ")
        memo_layout = QVBoxLayout(memo_box)
        self.memo_edits: list[QTextEdit] = []
        for index in range(10):
            row = QHBoxLayout()
            memo_edit = QTextEdit()
            memo_edit.setPlaceholderText(f"メモ{index + 1}")
            memo_edit.setFixedHeight(70)
            memo_edit.textChanged.connect(self.save_memos)
            copy_button = QPushButton("コピー")
            copy_button.clicked.connect(lambda _checked=False, i=index: self.copy_memo_to_clipboard(i))
            row.addWidget(QLabel(f"{index + 1}"))
            row.addWidget(memo_edit, stretch=1)
            row.addWidget(copy_button)
            memo_layout.addLayout(row)
            self.memo_edits.append(memo_edit)
        topic_layout.addWidget(memo_box)
        topic_scroll = self._splitter_scroll_area(topic_box)
        self.left_content_splitter = QSplitter(Qt.Vertical)
        self.left_content_splitter.setHandleWidth(8)
        self.left_content_splitter.setChildrenCollapsible(False)
        self.left_content_splitter.addWidget(project_list_widget)
        self.left_content_splitter.addWidget(topic_scroll)
        self.left_content_splitter.setSizes([260, 420])
        layout.addWidget(self.left_content_splitter, stretch=1)
        return panel

    def _build_main_tabs(self) -> QTabWidget:
        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(self._scrollable_page(self._build_dashboard_tab()), "ホーム")
        self.main_tabs.addTab(self._scrollable_page(self._build_wizard_tab()), "制作ウィザード")
        return self.main_tabs

    def _scrollable_page(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    def _splitter_scroll_area(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(80)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        scroll.setWidget(widget)
        return scroll

    def _build_dashboard_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        stats_box = QGroupBox("Dashboard")
        grid = QGridLayout(stats_box)
        self.dashboard_labels: dict[str, QLabel] = {}
        labels = [
            ("today", "今日作る予定"),
            ("progress", "制作中"),
            ("completed", "完成"),
            ("posted", "投稿済"),
            ("videos", "総動画数"),
            ("projects", "総プロジェクト数"),
        ]
        for index, (key, label) in enumerate(labels):
            caption = QLabel(label)
            value = QLabel("0")
            value.setStyleSheet("font-size: 24px; font-weight: 700; color: #9cdcfe;")
            self.dashboard_labels[key] = value
            grid.addWidget(caption, index // 3 * 2, index % 3)
            grid.addWidget(value, index // 3 * 2 + 1, index % 3)
        layout.addWidget(stats_box)

        lists = QHBoxLayout()
        genre_box = QGroupBox("ジャンル別本数")
        genre_layout = QVBoxLayout(genre_box)
        self.genre_stats_list = QListWidget()
        genre_layout.addWidget(self.genre_stats_list)
        lists.addWidget(genre_box)
        recent_box = QGroupBox("最近編集した動画")
        recent_layout = QVBoxLayout(recent_box)
        self.recent_list = QListWidget()
        self.recent_list.itemDoubleClicked.connect(self.open_recent_project)
        recent_layout.addWidget(self.recent_list)
        lists.addWidget(recent_box)
        layout.addLayout(lists, stretch=1)
        return panel

    def _build_wizard_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(self._build_wizard_bar())
        self.next_action_label = QLabel("次に押す場所を青くハイライトします。")
        self.next_action_label.setStyleSheet("background:#252526; border:1px solid #3c3c3c; border-radius:4px; padding:8px; color:#dcdcaa;")
        layout.addWidget(self.next_action_label)
        layout.addWidget(self._build_form_box())

        action_row = QHBoxLayout()
        buttons = [
            ("open_chatgpt", "ChatGPTを開く", self.open_chatgpt),
            ("generate_prompt", "プロンプト生成", self.generate_prompt),
            ("copy_prompt", "プロンプトをコピー", self.copy_prompt),
            ("copy_bulk_image_prompt", "画像生成プロンプトをコピー", self.copy_bulk_image_prompt),
            ("create_project", "プロジェクト作成", self.create_project),
            ("generate_voice", "VOICEVOX音声生成", self.generate_voice),
            ("render_video", "FFmpeg動画生成", self.render_video),
            ("post", "投稿", self.not_implemented),
        ]
        self.action_buttons: dict[str, QPushButton] = {}
        for key, label, handler in buttons:
            button = QPushButton(label)
            button.clicked.connect(handler)
            self.action_buttons[key] = button
            action_row.addWidget(button)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.content_tabs = QTabWidget()
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText("JSON出力指定のChatGPT用プロンプトが表示されます。")
        self.answer_text = QTextEdit()
        self.answer_text.setPlaceholderText("ChatGPTのJSON回答を貼り付けると0.5秒後に自動解析します。旧形式にも対応しています。")
        self.answer_text.textChanged.connect(self.schedule_auto_parse)
        self.content_tabs.addTab(self.prompt_text, "ChatGPT")
        self.content_tabs.addTab(self.answer_text, "JSON回答貼り付け")
        self.content_tabs.addTab(self._build_preview_tab(), "プレビュー編集")
        self.content_tabs.addTab(self._build_image_prompts_tab(), "画像プロンプト")
        self.content_tabs.addTab(self._build_bulk_image_prompt_tab(), "一括画像生成")
        self.content_tabs.addTab(self._build_assets_tab(), "素材管理")
        self.content_tabs.addTab(self._build_video_preview_tab(), "完成動画プレビュー")
        layout.addWidget(self.content_tabs, stretch=2)

        bottom = QHBoxLayout()
        bottom.addWidget(self._build_progress_box(), stretch=1)
        bottom.addWidget(self._build_folder_box(), stretch=1)
        layout.addLayout(bottom)

        self.status_label = QLabel("準備完了")
        self.status_label.setStyleSheet("color: #9cdcfe;")
        footer = QHBoxLayout()
        footer.addWidget(self.status_label)
        footer.addStretch()
        version_text = f"{self.version_info.get('phase', 'Phase4.5')} v{self.version_info.get('version', '0.4.5')}"
        self.version_label = QLabel(version_text)
        self.version_label.setStyleSheet("color: #8a8a8a;")
        footer.addWidget(self.version_label)
        layout.addLayout(footer)
        return panel

    def _build_wizard_bar(self) -> QWidget:
        box = QGroupBox("制作ウィザード")
        layout = QHBoxLayout(box)
        self.step_labels: list[QLabel] = []
        for index, step in enumerate(WIZARD_STEPS, start=1):
            label = QLabel(f"STEP{index}\n{step}")
            label.setAlignment(Qt.AlignCenter)
            label.setMinimumWidth(110)
            self.step_labels.append(label)
            layout.addWidget(label)
        return box

    def _build_form_box(self) -> QGroupBox:
        box = QGroupBox("制作設定")
        form = QGridLayout(box)
        self.topic_input = QLineEdit()
        self.topic_completer_model = QStringListModel()
        self.topic_completer = QCompleter(self.topic_completer_model, self)
        self.topic_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.topic_input.setCompleter(self.topic_completer)

        self.template_box = QComboBox()
        self.template_box.currentTextChanged.connect(self.apply_template)
        self.duration_box = QComboBox()
        self.duration_box.addItems(DEFAULT_DURATIONS)
        self.genre_box = QComboBox()
        self.image_count_box = QComboBox()
        self.image_count_box.addItems(["3", "4", "5", "6", "8"])
        self.youtube_tags_input = QLineEdit()
        self.youtube_tags_input.setPlaceholderText("hashtags.txtから#を削除し、カンマ区切りで入力します")
        self.tiktok_tags_input = QLineEdit()
        self.tiktok_tags_input.setPlaceholderText("hashtags.txtをコピーし、最後に#VOICEVOXを追加します")

        form.addWidget(QLabel("テーマ"), 0, 0)
        form.addWidget(self.topic_input, 0, 1, 1, 4)
        copy_topic_button = QPushButton("テーマコピー")
        copy_topic_button.clicked.connect(self.copy_theme_to_clipboard)
        form.addWidget(copy_topic_button, 0, 5)
        form.addWidget(QLabel("テンプレート"), 1, 0)
        form.addWidget(self.template_box, 1, 1)
        form.addWidget(QLabel("動画時間"), 1, 2)
        form.addWidget(self.duration_box, 1, 3)
        form.addWidget(QLabel("画像枚数"), 1, 4)
        form.addWidget(self.image_count_box, 1, 5)
        form.addWidget(QLabel("ジャンル"), 2, 0)
        form.addWidget(self.genre_box, 2, 1)
        form.addWidget(QLabel("YouTubeタグ"), 2, 2)
        form.addWidget(self.youtube_tags_input, 2, 3, 1, 2)
        youtube_buttons = QHBoxLayout()
        save_youtube_tags_button = QPushButton("youtubeタグ保存")
        save_youtube_tags_button.clicked.connect(self.save_youtube_tags)
        copy_youtube_tags_button = QPushButton("コピー")
        copy_youtube_tags_button.clicked.connect(self.copy_youtube_tags_to_clipboard)
        youtube_buttons.addWidget(save_youtube_tags_button)
        youtube_buttons.addWidget(copy_youtube_tags_button)
        form.addLayout(youtube_buttons, 2, 5)
        form.addWidget(QLabel("TikTokタグ"), 3, 2)
        form.addWidget(self.tiktok_tags_input, 3, 3, 1, 2)
        tiktok_buttons = QHBoxLayout()
        save_tiktok_tags_button = QPushButton("tiktokタグ保存")
        save_tiktok_tags_button.clicked.connect(self.save_tiktok_tags)
        copy_tiktok_tags_button = QPushButton("コピー")
        copy_tiktok_tags_button.clicked.connect(self.copy_tiktok_tags_to_clipboard)
        tiktok_buttons.addWidget(save_tiktok_tags_button)
        tiktok_buttons.addWidget(copy_tiktok_tags_button)
        form.addLayout(tiktok_buttons, 3, 5)
        return box

    def _build_preview_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.preview_tabs = QTabWidget()
        self.preview_script = QTextEdit()
        self.preview_voice = QTextEdit()
        self.preview_images = QTextEdit()
        self.preview_subtitles = QTextEdit()
        self.preview_hashtags = QTextEdit()
        self.preview_tabs.addTab(self.preview_script, "script.txt")
        self.preview_tabs.addTab(self.preview_voice, "voice.txt")
        self.preview_tabs.addTab(self.preview_images, "image_prompts.txt")
        self.preview_tabs.addTab(self.preview_subtitles, "subtitles.txt")
        self.preview_tabs.addTab(self.preview_hashtags, "hashtags.txt")
        layout.addWidget(self.preview_tabs)
        save_button = QPushButton("プレビュー内容を保存")
        save_button.clicked.connect(self.save_preview_files)
        layout.addWidget(save_button)
        return panel

    def _build_image_prompts_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.image_prompt_scroll = QScrollArea()
        self.image_prompt_scroll.setWidgetResizable(True)
        self.image_prompt_container = QWidget()
        self.image_prompt_layout = QVBoxLayout(self.image_prompt_container)
        self.image_prompt_layout.addStretch()
        self.image_prompt_scroll.setWidget(self.image_prompt_container)
        layout.addWidget(self.image_prompt_scroll)
        return panel

    def _build_bulk_image_prompt_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.bulk_image_prompt_text = QTextEdit()
        self.bulk_image_prompt_text.setPlaceholderText("画像生成プロンプトのプレビューが表示されます。編集してからコピーできます。")
        layout.addWidget(self.bulk_image_prompt_text, stretch=1)

        buttons = QHBoxLayout()
        refresh_button = QPushButton("画像生成プロンプトを作成")
        refresh_button.clicked.connect(self.refresh_bulk_image_prompt)
        copy_button = QPushButton("画像生成プロンプトをコピー")
        copy_button.clicked.connect(self.copy_bulk_image_prompt)
        buttons.addWidget(refresh_button)
        buttons.addWidget(copy_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        return panel

    def _build_assets_tab(self) -> QWidget:
        panel = QWidget()
        self.assets_tab = panel
        layout = QVBoxLayout(panel)
        self.image_drop_area = ImageDropArea(self)
        layout.addWidget(self.image_drop_area)

        import_buttons = QHBoxLayout()
        self.select_images_button = QPushButton("画像ファイルを選択")
        self.select_images_button.clicked.connect(self.select_images_for_import)
        self.paste_images_button = QPushButton("Ctrl+V貼り付け")
        self.paste_images_button.clicked.connect(self.paste_images_from_clipboard)
        open_images_button = QPushButton("画像フォルダを開く")
        open_images_button.clicked.connect(lambda _checked=False: self.open_project_folder("images"))
        import_buttons.addWidget(self.select_images_button)
        import_buttons.addWidget(self.paste_images_button)
        import_buttons.addWidget(open_images_button)
        import_buttons.addStretch()
        layout.addLayout(import_buttons)

        imported_images_panel = QWidget()
        imported_images_panel.setMinimumHeight(80)
        imported_images_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        imported_images_layout = QVBoxLayout(imported_images_panel)
        imported_images_layout.setContentsMargins(0, 0, 0, 0)
        imported_images_layout.addWidget(QLabel("取り込み済み画像"))
        self.image_thumbnail_scroll = QScrollArea()
        self.image_thumbnail_scroll.setWidgetResizable(True)
        self.image_thumbnail_scroll.setMinimumHeight(60)
        self.image_thumbnail_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.image_thumbnail_container = QWidget()
        self.image_thumbnail_layout = QVBoxLayout(self.image_thumbnail_container)
        self.image_thumbnail_layout.addStretch()
        self.image_thumbnail_scroll.setWidget(self.image_thumbnail_container)
        imported_images_layout.addWidget(self.image_thumbnail_scroll)

        asset_list_panel = QWidget()
        asset_list_panel.setMinimumHeight(80)
        asset_list_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        asset_list_layout = QVBoxLayout(asset_list_panel)
        asset_list_layout.setContentsMargins(0, 0, 0, 0)
        asset_list_layout.addWidget(QLabel("素材一覧"))
        self.asset_list = QListWidget()
        self.asset_list.itemDoubleClicked.connect(self.open_asset_folder)
        self.asset_list.setMinimumHeight(60)
        self.asset_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        asset_list_layout.addWidget(self.asset_list)

        self.assets_splitter = QSplitter(Qt.Vertical)
        self.assets_splitter.setHandleWidth(8)
        self.assets_splitter.setChildrenCollapsible(False)
        self.assets_splitter.addWidget(imported_images_panel)
        self.assets_splitter.addWidget(asset_list_panel)
        self.assets_splitter.setSizes([420, 180])
        layout.addWidget(self.assets_splitter, stretch=1)
        return panel

    def _build_video_preview_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        if MULTIMEDIA_AVAILABLE:
            self.video_widget = QVideoWidget()
            self.media_player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.media_player.setAudioOutput(self.audio_output)
            self.media_player.setVideoOutput(self.video_widget)
            layout.addWidget(self.video_widget, stretch=1)
        else:
            layout.addWidget(QLabel("この環境ではQt Multimediaを利用できません。動画フォルダを開いて確認してください。"))

        controls = QHBoxLayout()
        for label, handler in [("再生", self.play_video), ("一時停止", self.pause_video), ("最初に戻る", self.rewind_video), ("動画フォルダを開く", lambda: self.open_project_folder("video"))]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            controls.addWidget(button)
        controls.addStretch()
        layout.addLayout(controls)
        return panel

    def _build_progress_box(self) -> QGroupBox:
        box = QGroupBox("進捗状況")
        layout = QHBoxLayout(box)
        self.progress_checks: dict[str, QCheckBox] = {}
        for item in PROGRESS_ITEMS:
            check = QCheckBox(item)
            check.setEnabled(False)
            self.progress_checks[item] = check
            layout.addWidget(check)
        layout.addStretch()
        return box

    def _build_folder_box(self) -> QGroupBox:
        box = QGroupBox("フォルダ")
        layout = QGridLayout(box)
        buttons = [("画像フォルダを開く", "images"), ("音声フォルダを開く", "audio"), ("動画フォルダを開く", "video"), ("プロジェクトフォルダを開く", "")]
        for index, (label, folder_name) in enumerate(buttons):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, name=folder_name: self.open_project_folder(name))
            layout.addWidget(button, index // 2, index % 2)
        return box

    def _load_initial_data(self) -> None:
        self.templates = self.template_service.load()
        self.topics = self.topic_service.load()
        self.apply_settings_to_ui()
        self.reload_projects()
        self.refresh_topic_list()
        self.update_wizard()
        self.load_memos()

    def apply_settings_to_ui(self) -> None:
        self.duration_box.setCurrentText(self.settings.default_duration)
        self._set_image_count(self.settings.default_image_count)
        self.genre_box.clear()
        self.genre_box.addItems(self.settings.genres)
        self.genre_filter.blockSignals(True)
        self.genre_filter.clear()
        self.genre_filter.addItem("すべてのジャンル")
        self.genre_filter.addItems(self.settings.genres)
        self.genre_filter.blockSignals(False)
        self.template_box.blockSignals(True)
        self.template_box.clear()
        self.template_box.addItems([template.name for template in self.templates])
        self.template_box.blockSignals(False)
        self.apply_template()

    def reload_projects(self) -> None:
        self.projects = self.project_service.list_projects()
        self.refresh_project_list()
        self.refresh_dashboard()
        self.refresh_completer()

    def refresh_dashboard(self) -> None:
        stats = self.dashboard_service.build(self.projects)
        self.dashboard_labels["today"].setText(str(stats.today_count))
        self.dashboard_labels["progress"].setText(str(stats.in_progress_count))
        self.dashboard_labels["completed"].setText(str(stats.completed_count))
        self.dashboard_labels["posted"].setText(str(stats.posted_count))
        self.dashboard_labels["videos"].setText(str(stats.total_videos))
        self.dashboard_labels["projects"].setText(str(stats.total_projects))
        self.genre_stats_list.clear()
        for genre, count in sorted(stats.genre_counts.items()):
            self.genre_stats_list.addItem(f"{genre}: {count}")
        self.recent_list.clear()
        for project in stats.recent_projects:
            item = QListWidgetItem(self._project_display_name(project))
            item.setData(Qt.UserRole, str(project.path))
            self.recent_list.addItem(item)

    def refresh_project_list(self) -> None:
        keyword = self.project_search.text().strip().lower()
        genre = self.genre_filter.currentText()
        current_path = str(self.current_project.path) if self.current_project else ""
        self.project_list.blockSignals(True)
        self.project_list.clear()
        for project in self.projects:
            fields = [project.title, project.topic, project.genre, project.posted_date, project.series, " ".join(project.tags), project.name]
            haystack = " ".join(fields).lower()
            if keyword and keyword not in haystack:
                continue
            if genre and genre != "すべてのジャンル" and project.genre != genre:
                continue
            item = QListWidgetItem(self._project_display_name(project))
            item.setData(Qt.UserRole, str(project.path))
            self.project_list.addItem(item)
            if current_path and str(project.path) == current_path:
                item.setSelected(True)
        self.project_list.blockSignals(False)

    def refresh_topic_list(self) -> None:
        keyword = self.topic_search.text().strip().lower()
        self.topic_list.clear()
        for topic in self.topics:
            if not keyword or keyword in topic.lower():
                self.topic_list.addItem(topic)

    def refresh_completer(self) -> None:
        candidates = list(dict.fromkeys(self.topics + [project.topic for project in self.projects if project.topic]))
        self.topic_completer_model.setStringList(candidates)

    def open_recent_project(self, item: QListWidgetItem) -> None:
        self._load_project(Path(item.data(Qt.UserRole)))
        self.main_tabs.setCurrentIndex(1)

    def load_selected_project(self) -> None:
        selected = self.project_list.selectedItems()
        if selected:
            self._load_project(Path(selected[0].data(Qt.UserRole)))

    def _load_project(self, path: Path) -> None:
        self.current_project = self.project_service.load_project(path)
        self.topic_input.setText(self.current_project.topic)
        self.duration_box.setCurrentText(self.current_project.duration or self.settings.default_duration)
        self.genre_box.setCurrentText(self.current_project.genre)
        self._set_image_count(self.current_project.image_count)
        self.template_box.setCurrentText(self.current_project.template_name)
        self._load_project_texts(self.current_project.path)
        self._load_platform_tag_fields()
        self.update_progress_view()
        self.update_asset_list()
        self.update_image_prompt_list()
        self.update_video_preview()
        self.update_wizard()
        self.status_label.setText(f"プロジェクトを開きました: {self.current_project.name}")

    def _load_project_texts(self, path: Path) -> None:
        self.prompt_text.setPlainText(self._read_text(path / "chatgpt_prompt.txt"))
        self.answer_text.blockSignals(True)
        self.answer_text.setPlainText(self._read_text(path / "raw_chatgpt.txt"))
        self.answer_text.blockSignals(False)
        self.preview_script.setPlainText(self._read_text(path / "script.txt"))
        self.preview_voice.setPlainText(self._read_text(path / "voice.txt"))
        self.preview_images.setPlainText(self._read_text(path / "image_prompts.txt"))
        self.preview_subtitles.setPlainText(self._read_text(path / "subtitles.txt"))
        self.preview_hashtags.setPlainText(self._read_text(path / "hashtags.txt"))

    def apply_template(self) -> None:
        template = self.current_template()
        if template:
            if self.genre_box.findText(template.genre) < 0:
                self.genre_box.addItem(template.genre)
            self.genre_box.setCurrentText(template.genre)

    def current_template(self) -> PromptTemplate | None:
        name = self.template_box.currentText()
        return next((template for template in self.templates if template.name == name), None)

    def generate_prompt(self) -> None:
        values = self._read_form_values()
        if values is None:
            return
        topic, duration, genre, image_count, _tags = values
        prompt = build_chatgpt_prompt(topic, duration, genre, image_count, self.current_template())
        self.prompt_text.setPlainText(prompt)
        self.content_tabs.setCurrentWidget(self.prompt_text)
        self.update_wizard()
        self.status_label.setText("JSON出力指定のChatGPT用プロンプトを生成しました。")

    def open_chatgpt(self) -> None:
        webbrowser.open("https://chatgpt.com/")
        self.status_label.setText("ChatGPTをブラウザで開きました。")

    def copy_prompt(self) -> None:
        text = self.prompt_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "コピーエラー", "コピーするプロンプトがありません。")
            return
        QGuiApplication.clipboard().setText(text)
        self.status_label.setText("プロンプトをコピーしました。ChatGPTへ貼り付けてください。")

    def refresh_bulk_image_prompt(self) -> None:
        image_count = int(self.image_count_box.currentText())
        prompt = build_bulk_image_prompt(
            self._current_image_prompts(),
            image_count,
            self.settings.image_common_conditions,
            self.current_template(),
        )
        self.bulk_image_prompt_text.setPlainText(prompt)
        self.content_tabs.setCurrentWidget(self.bulk_image_prompt_text.parentWidget())
        self.status_label.setText("画像生成プロンプトを作成しました。内容を確認してコピーできます。")

    def copy_bulk_image_prompt(self) -> None:
        if not self.bulk_image_prompt_text.toPlainText().strip():
            self.refresh_bulk_image_prompt()
        text = self.bulk_image_prompt_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "コピーエラー", "画像生成プロンプトがありません。")
            return
        QGuiApplication.clipboard().setText(text)
        self.status_label.setText("画像生成プロンプトをコピーしました。ChatGPTへ貼り付けてください。")
        QMessageBox.information(self, "コピー成功", "画像生成プロンプトをコピーしました。")

    def _current_image_prompts(self) -> list[str]:
        text = self.preview_images.toPlainText().strip()
        prompts = self._split_image_prompt_text(text)
        if prompts:
            return prompts
        if self.current_project is None:
            return []
        return [prompt for _index, prompt, _generated in self.project_service.image_prompt_items(self.current_project) if prompt.strip()]

    def _split_image_prompt_text(self, text: str) -> list[str]:
        if not text.strip():
            return []
        blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
        if len(blocks) > 1:
            return blocks
        return [line.strip() for line in text.splitlines() if line.strip()]

    def create_project(self) -> None:
        values = self._read_form_values()
        if values is None:
            return
        topic, duration, genre, image_count, tags = values
        prompt = self.prompt_text.toPlainText().strip() or build_chatgpt_prompt(topic, duration, genre, image_count, self.current_template())
        self.prompt_text.setPlainText(prompt)
        try:
            self.current_project = self.project_service.create_project(topic, genre, duration, image_count, prompt, self.template_box.currentText(), tags, topic)
        except OSError as exc:
            QMessageBox.critical(self, "作成エラー", f"プロジェクトの作成に失敗しました。\n{exc}")
            return
        if topic not in self.topics:
            self.topics.append(topic)
            self.topic_service.save(self.topics)
        self.reload_projects()
        self.update_progress_view()
        self.update_asset_list()
        self.update_image_prompt_list()
        self.update_wizard()
        self.status_label.setText(f"プロジェクトを作成しました: {self.current_project.name}")

    def start_bulk_projects(self) -> None:
        topics = list(dict.fromkeys([line.strip() for line in self.bulk_topics.toPlainText().splitlines() if line.strip()]))
        if not topics:
            QMessageBox.warning(self, "一括作成エラー", "作成するテーマを1行ずつ入力してください。")
            return
        duration = self.duration_box.currentText()
        genre = self.genre_box.currentText()
        image_count = int(self.image_count_box.currentText())
        template = self.current_template()
        tags = self._parse_tags()

        def make_prompt(topic: str) -> str:
            return build_chatgpt_prompt(topic, duration, genre, image_count, template)

        try:
            created = self.project_service.create_projects_from_topics(topics, genre, duration, image_count, self.template_box.currentText(), make_prompt, tags)
        except OSError as exc:
            QMessageBox.critical(self, "一括作成エラー", f"プロジェクト作成に失敗しました。\n{exc}")
            return
        self.topics = list(dict.fromkeys(self.topics + topics))
        self.topic_service.save(self.topics)
        self.current_project = created[-1]
        self.reload_projects()
        self._load_project(self.current_project.path)
        self.status_label.setText(f"{len(created)}件のプロジェクトを順番に作成しました。")

    def schedule_auto_parse(self) -> None:
        self.auto_parse_timer.start()

    def auto_parse_answer(self) -> None:
        if self.current_project is None:
            self.status_label.setText("回答を保存するには、先にプロジェクトを作成または選択してください。")
            return
        raw_text = self.answer_text.toPlainText().strip()
        if not raw_text:
            return
        try:
            parsed = self.parser.parse(raw_text)
        except ChatGptParseError as exc:
            self.status_label.setText(str(exc))
            QMessageBox.warning(self, "JSON解析エラー", str(exc))
            return
        self.project_service.save_chatgpt_import(self.current_project, raw_text, parsed)
        self.current_project = self.project_service.load_project(self.current_project.path)
        self._load_project_texts(self.current_project.path)
        self._load_platform_tag_fields()
        self.update_progress_view()
        self.update_asset_list()
        self.update_image_prompt_list()
        self.update_wizard()
        self.reload_projects()
        self.status_label.setText("ChatGPT回答をJSON解析して保存しました。")

    def save_preview_files(self) -> None:
        if self.current_project is None:
            QMessageBox.warning(self, "保存エラー", "先にプロジェクトを作成または選択してください。")
            return
        self.project_service.save_preview_files(
            self.current_project,
            {
                "script.txt": self.preview_script.toPlainText(),
                "voice.txt": self.preview_voice.toPlainText(),
                "image_prompts.txt": self.preview_images.toPlainText(),
                "subtitles.txt": self.preview_subtitles.toPlainText(),
                "hashtags.txt": self.preview_hashtags.toPlainText(),
            },
        )
        self.current_project = self.project_service.load_project(self.current_project.path)
        self.update_progress_view()
        self.update_asset_list()
        self.update_image_prompt_list()
        self.update_wizard()
        self.reload_projects()
        self.status_label.setText("プレビュー内容を保存しました。")

    def generate_voice(self) -> None:
        if self.current_project is None:
            QMessageBox.warning(self, "音声生成エラー", "先にプロジェクトを作成または選択してください。")
            return
        result = self.voicevox_service.synthesize_project(self.current_project.path)
        if not result.success:
            QMessageBox.warning(self, "VOICEVOXエラー", result.message)
            return
        self.current_project = self.project_service.load_project(self.current_project.path)
        self._load_project_texts(self.current_project.path)
        self._load_platform_tag_fields()
        self.update_progress_view()
        self.update_asset_list()
        self.update_wizard()
        self.reload_projects()
        self.status_label.setText(result.message)

    def render_video(self) -> None:
        if self.current_project is None:
            QMessageBox.warning(self, "動画生成エラー", "先にプロジェクトを作成または選択してください。")
            return
        result = self.video_render_service.render_project(self.current_project)
        if not result.success:
            QMessageBox.warning(self, "FFmpegエラー", result.message)
            return
        self.current_project = self.project_service.load_project(self.current_project.path)
        self.update_progress_view()
        self.update_asset_list()
        self.update_video_preview()
        self.update_wizard()
        self.reload_projects()
        self.status_label.setText(result.message)
        self.content_tabs.setCurrentIndex(5)

    def save_youtube_tags(self) -> None:
        if self.current_project is None:
            QMessageBox.warning(self, "YouTubeタグ保存エラー", "先にプロジェクトを作成または選択してください。")
            return
        tags = self.tag_service.youtube_tags_from_hashtags(self._current_hashtags_text())
        self.youtube_tags_input.setText(self.tag_service.youtube_text(tags))
        self.current_project = self.project_service.save_platform_tags(self.current_project, youtube_tags=tags)
        self.reload_projects()
        self.status_label.setText("YouTubeタグを保存しました。")

    def save_tiktok_tags(self) -> None:
        if self.current_project is None:
            QMessageBox.warning(self, "TikTokタグ保存エラー", "先にプロジェクトを作成または選択してください。")
            return
        tags = self.tag_service.tiktok_tags_from_hashtags(self._current_hashtags_text())
        self.tiktok_tags_input.setText(self.tag_service.tiktok_text(tags))
        self.current_project = self.project_service.save_platform_tags(self.current_project, tiktok_tags=tags)
        self.reload_projects()
        self.status_label.setText("TikTokタグを保存しました。")

    def copy_theme_to_clipboard(self) -> None:
        self._copy_text_to_clipboard(self.topic_input.text().strip(), "テーマ")

    def copy_youtube_tags_to_clipboard(self) -> None:
        self._copy_text_to_clipboard(self.youtube_tags_input.text().strip(), "YouTubeタグ")

    def copy_tiktok_tags_to_clipboard(self) -> None:
        self._copy_text_to_clipboard(self.tiktok_tags_input.text().strip(), "TikTokタグ")

    def copy_memo_to_clipboard(self, index: int) -> None:
        if index < 0 or index >= len(self.memo_edits):
            return
        self._copy_text_to_clipboard(self.memo_edits[index].toPlainText().strip(), f"メモ{index + 1}")

    def _copy_text_to_clipboard(self, text: str, label: str) -> None:
        if not text:
            QMessageBox.warning(self, "コピーエラー", f"{label}が空です。")
            return
        QGuiApplication.clipboard().setText(text)
        self.status_label.setText(f"{label}をコピーしました。")

    def load_memos(self) -> None:
        path = self._memos_path()
        if not path.exists():
            return
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(values, list):
            return
        for index, memo_edit in enumerate(getattr(self, "memo_edits", [])):
            memo_edit.blockSignals(True)
            memo_edit.setPlainText(str(values[index]) if index < len(values) else "")
            memo_edit.blockSignals(False)

    def save_memos(self) -> None:
        values = [memo.toPlainText() for memo in getattr(self, "memo_edits", [])]
        try:
            self._memos_path().write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            return

    def _memos_path(self) -> Path:
        return self.paths.base_dir / "memos.json"

    def not_implemented(self) -> None:
        QMessageBox.information(self, "未実装", "この機能は後で実装します。今回は自動投稿しません。")

    def update_progress_view(self) -> None:
        progress = self.current_project.progress if self.current_project else {}
        for name, check in self.progress_checks.items():
            check.setChecked(bool(progress.get(name, False)))

    def update_wizard(self) -> None:
        states = self._wizard_states()
        first_incomplete = next((index for index, done in enumerate(states) if not done), len(states) - 1)
        for index, label in enumerate(self.step_labels):
            if states[index]:
                label.setStyleSheet("background:#2d4a2d; border:1px solid #4e8f4e; border-radius:4px; padding:6px;")
            elif index == first_incomplete:
                label.setStyleSheet("background:#094771; border:1px solid #3794ff; border-radius:4px; padding:6px; font-weight:700;")
            else:
                label.setStyleSheet("background:#252526; border:1px solid #3c3c3c; border-radius:4px; padding:6px;")
        self.update_action_highlights(first_incomplete)

    def _wizard_states(self) -> list[bool]:
        progress = self.current_project.progress if self.current_project else {}
        return [
            bool(self.topic_input.text().strip()),
            bool(self.current_project),
            bool(progress.get("台本")),
            bool(progress.get("画像")),
            bool(progress.get("音声")),
            bool(progress.get("動画")),
            bool(progress.get("投稿")),
        ]

    def update_action_highlights(self, step_index: int) -> None:
        self._clear_action_highlights()
        instructions = [
            "STEP1: テーマを入力してください。",
            "STEP2: 「プロンプト生成」→「プロンプトをコピー」→「プロジェクト作成」の順に進めます。",
            "STEP3: ChatGPTのJSON回答を「JSON回答貼り付け」へ貼り付けます。",
            "STEP4: 「画像生成プロンプトをコピー」で画像を生成し、素材管理から画像を取り込みます。",
            "STEP5: 「VOICEVOX音声生成」を押します。",
            "STEP6: 「FFmpeg動画生成」を押します。",
            "STEP7: 投稿準備ができています。",
        ]
        if hasattr(self, "next_action_label"):
            self.next_action_label.setText(instructions[min(step_index, len(instructions) - 1)])
        if step_index == 0:
            self.topic_input.setStyleSheet(self._highlight_field_style())
            return
        if step_index == 1:
            if self.prompt_text.toPlainText().strip():
                self._highlight_buttons(["open_chatgpt", "copy_prompt", "create_project"])
            else:
                self._highlight_buttons(["generate_prompt"])
            return
        if step_index == 2:
            self.answer_text.setStyleSheet(self._highlight_field_style())
            self.content_tabs.setCurrentWidget(self.answer_text)
            return
        if step_index == 3:
            self._highlight_buttons(["copy_bulk_image_prompt"])
            if hasattr(self, "assets_tab"):
                self.content_tabs.setCurrentWidget(self.assets_tab)
            if hasattr(self, "select_images_button"):
                self.select_images_button.setStyleSheet(self._highlight_button_style())
            if hasattr(self, "paste_images_button"):
                self.paste_images_button.setStyleSheet(self._highlight_button_style())
            return
        if step_index == 4:
            self._highlight_buttons(["generate_voice"])
            return
        if step_index == 5:
            self._highlight_buttons(["render_video"])
            return
        if step_index == 6:
            self._highlight_buttons(["post"])

    def _clear_action_highlights(self) -> None:
        for button in getattr(self, "action_buttons", {}).values():
            button.setStyleSheet("")
        for widget_name in ["select_images_button", "paste_images_button"]:
            widget = getattr(self, widget_name, None)
            if widget:
                widget.setStyleSheet("")
        for widget_name in ["topic_input", "answer_text"]:
            widget = getattr(self, widget_name, None)
            if widget:
                widget.setStyleSheet("")

    def _highlight_buttons(self, keys: list[str]) -> None:
        for key in keys:
            button = self.action_buttons.get(key)
            if button:
                button.setStyleSheet(self._highlight_button_style())

    def _highlight_button_style(self) -> str:
        return "background:#0e639c; border:2px solid #ffd166; color:#ffffff; font-weight:700;"

    def _highlight_field_style(self) -> str:
        return "background:#252526; color:#ffffff; border:2px solid #ffd166; border-radius:4px; padding:6px;"

    def update_asset_list(self) -> None:
        self.asset_list.clear()
        if self.current_project is None:
            self.update_image_thumbnail_list()
            return
        for label, status, path in self.project_service.asset_statuses(self.current_project):
            item = QListWidgetItem(f"{label}    {status}")
            item.setData(Qt.UserRole, str(path))
            self.asset_list.addItem(item)
        self.update_image_thumbnail_list()

    def select_images_for_import(self) -> None:
        if self.current_project is None:
            QMessageBox.warning(self, "画像取り込みエラー", "先にプロジェクトを作成、または選択してください。")
            return
        files, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "取り込む画像を選択",
            str(self.current_project.path),
            "画像ファイル (*.png *.jpg *.jpeg *.webp)",
        )
        if files:
            self.import_image_files([Path(file) for file in files])

    def import_image_files(self, files: list[Path]) -> None:
        if self.current_project is None:
            QMessageBox.warning(self, "画像取り込みエラー", "先にプロジェクトを作成、または選択してください。")
            return
        mode = self._confirm_image_import_mode()
        if mode is None:
            return
        try:
            imported = self.image_import_service.import_files(self.current_project.path, files, mode)
        except ImageImportError as exc:
            QMessageBox.warning(self, "画像取り込みエラー", str(exc))
            return
        self._refresh_after_image_change()
        self.status_label.setText(f"{len(imported)}枚の画像を取り込みました。")

    def paste_images_from_clipboard(self) -> None:
        if self.current_project is None:
            QMessageBox.warning(self, "画像貼り付けエラー", "先にプロジェクトを作成、または選択してください。")
            return
        mime_data = QGuiApplication.clipboard().mimeData()
        if not mime_data.hasUrls() and not mime_data.hasImage():
            QMessageBox.warning(self, "画像貼り付けエラー", "クリップボードに画像がありません。")
            return
        mode = self._confirm_image_import_mode()
        if mode is None:
            return
        try:
            if mime_data.hasUrls():
                files = [Path(url.toLocalFile()) for url in mime_data.urls() if url.isLocalFile()]
                if not files:
                    QMessageBox.warning(self, "画像貼り付けエラー", "クリップボードに画像がありません。")
                    return
                imported = self.image_import_service.import_files(self.current_project.path, files, mode)
                count = len(imported)
            elif mime_data.hasImage():
                image = QGuiApplication.clipboard().image()
                self.image_import_service.import_qimage(self.current_project.path, image, mode)
                count = 1
            else:
                QMessageBox.warning(self, "画像貼り付けエラー", "クリップボードに画像がありません。")
                return
        except ImageImportError as exc:
            QMessageBox.warning(self, "画像貼り付けエラー", str(exc))
            return
        self._refresh_after_image_change()
        self.status_label.setText(f"{count}枚の画像を貼り付けました。")

    def _confirm_image_import_mode(self) -> str | None:
        if self.current_project is None:
            return None
        if not self.image_import_service.has_images(self.current_project.path):
            return "add"
        message = QMessageBox(self)
        message.setWindowTitle("画像取り込み")
        message.setText("既存画像があります。上書きしますか？")
        overwrite_button = message.addButton("上書きする", QMessageBox.AcceptRole)
        add_button = message.addButton("追加する", QMessageBox.ActionRole)
        cancel_button = message.addButton("キャンセル", QMessageBox.RejectRole)
        message.exec()
        clicked = message.clickedButton()
        if clicked == overwrite_button:
            return "overwrite"
        if clicked == add_button:
            return "add"
        if clicked == cancel_button:
            return None
        return None

    def update_image_thumbnail_list(self) -> None:
        while self.image_thumbnail_layout.count() > 1:
            item = self.image_thumbnail_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if self.current_project is None:
            return
        for image_path in self.image_import_service.list_images(self.current_project.path):
            self.image_thumbnail_layout.insertWidget(
                self.image_thumbnail_layout.count() - 1,
                self._image_thumbnail_row(image_path),
            )

    def _image_thumbnail_row(self, image_path: Path) -> QWidget:
        row = QFrame()
        row.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(row)
        preview = QLabel()
        preview.setFixedSize(QSize(96, 150))
        pixmap = QPixmap(str(image_path))
        if not pixmap.isNull():
            preview.setPixmap(pixmap.scaled(preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        preview.setAlignment(Qt.AlignCenter)
        layout.addWidget(preview)

        name_label = QLabel(image_path.name)
        name_label.setMinimumWidth(90)
        layout.addWidget(name_label)

        up_button = QPushButton("上へ")
        up_button.clicked.connect(lambda _checked=False, path=image_path: self.move_imported_image(path, -1))
        down_button = QPushButton("下へ")
        down_button.clicked.connect(lambda _checked=False, path=image_path: self.move_imported_image(path, 1))
        delete_button = QPushButton("削除")
        delete_button.clicked.connect(lambda _checked=False, path=image_path: self.delete_imported_image(path))
        layout.addWidget(up_button)
        layout.addWidget(down_button)
        layout.addWidget(delete_button)
        layout.addStretch()
        return row

    def move_imported_image(self, image_path: Path, direction: int) -> None:
        try:
            self.image_import_service.move_image(image_path, direction)
        except OSError as exc:
            QMessageBox.warning(self, "画像順番変更エラー", f"画像の順番変更に失敗しました。\n{exc}")
            return
        self._refresh_after_image_change()
        self.status_label.setText("画像の順番を変更しました。")

    def delete_imported_image(self, image_path: Path) -> None:
        try:
            self.image_import_service.delete_image(image_path)
        except OSError as exc:
            QMessageBox.warning(self, "画像削除エラー", f"画像の削除に失敗しました。\n{exc}")
            return
        self._refresh_after_image_change()
        self.status_label.setText(f"{image_path.name} を削除しました。")

    def _refresh_after_image_change(self) -> None:
        if self.current_project is None:
            return
        self.current_project = self.project_service.load_project(self.current_project.path)
        self.update_progress_view()
        self.update_asset_list()
        self.update_image_prompt_list()
        self.update_wizard()
        self.reload_projects()

    def update_image_prompt_list(self) -> None:
        while self.image_prompt_layout.count() > 1:
            item = self.image_prompt_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if self.current_project is None:
            return
        for index, prompt, generated in self.project_service.image_prompt_items(self.current_project):
            self.image_prompt_layout.insertWidget(self.image_prompt_layout.count() - 1, self._image_prompt_row(index, prompt, generated))

    def _image_prompt_row(self, index: int, prompt: str, generated: bool) -> QWidget:
        row = QFrame()
        row.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(row)
        status = "生成済" if generated else "未生成"
        title = QLabel(f"画像{index}    {status}")
        title.setStyleSheet("font-weight: 700; color: #9cdcfe;")
        layout.addWidget(title)
        prompt_box = QTextEdit()
        prompt_box.setPlainText(prompt)
        prompt_box.setReadOnly(True)
        prompt_box.setFixedHeight(90)
        layout.addWidget(prompt_box)
        buttons = QHBoxLayout()
        copy_button = QPushButton("コピー")
        copy_button.clicked.connect(lambda _checked=False, text=prompt: QGuiApplication.clipboard().setText(text))
        open_button = QPushButton("画像フォルダを開く")
        open_button.clicked.connect(lambda _checked=False: self.open_project_folder("images"))
        mark_button = QPushButton("生成済みにする")
        mark_button.clicked.connect(lambda _checked=False, i=index: self.mark_image_generated(i))
        buttons.addWidget(copy_button)
        buttons.addWidget(open_button)
        buttons.addWidget(mark_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        return row

    def mark_image_generated(self, index: int) -> None:
        if self.current_project is None:
            return
        path = self.project_service.mark_image_generated(self.current_project, index)
        self.current_project = self.project_service.load_project(self.current_project.path)
        self.update_progress_view()
        self.update_asset_list()
        self.update_image_prompt_list()
        self.update_wizard()
        self.status_label.setText(f"{path.name} を生成済みとして作成しました。実画像に差し替えてください。")

    def update_video_preview(self) -> None:
        if not MULTIMEDIA_AVAILABLE or self.current_project is None or self.media_player is None:
            return
        final_video = self.current_project.path / "video" / "final.mp4"
        if final_video.exists():
            self.media_player.setSource(QUrl.fromLocalFile(str(final_video)))

    def play_video(self) -> None:
        if self.media_player:
            self.update_video_preview()
            self.media_player.play()

    def pause_video(self) -> None:
        if self.media_player:
            self.media_player.pause()

    def rewind_video(self) -> None:
        if self.media_player:
            self.media_player.setPosition(0)

    def open_asset_folder(self, item: QListWidgetItem) -> None:
        self.project_service.open_folder(Path(item.data(Qt.UserRole)))

    def open_project_folder(self, folder_name: str) -> None:
        if self.current_project is None:
            QMessageBox.warning(self, "フォルダエラー", "先にプロジェクトを作成または選択してください。")
            return
        target = self.current_project.path / folder_name if folder_name else self.current_project.path
        self.project_service.open_folder(target)

    def add_topic(self) -> None:
        topic = self.topic_edit.text().strip()
        if not topic:
            QMessageBox.warning(self, "ネタ管理エラー", "追加するテーマを入力してください。")
            return
        if topic not in self.topics:
            self.topics.append(topic)
            self.topic_service.save(self.topics)
        self.refresh_topic_list()
        self.refresh_completer()
        self.topic_edit.clear()

    def update_topic(self) -> None:
        selected = self.topic_list.currentItem()
        new_topic = self.topic_edit.text().strip()
        if selected is None or not new_topic:
            QMessageBox.warning(self, "ネタ管理エラー", "編集するテーマを選び、新しい内容を入力してください。")
            return
        old_topic = selected.text()
        self.topics = [new_topic if topic == old_topic else topic for topic in self.topics]
        self.topic_service.save(self.topics)
        self.refresh_topic_list()
        self.refresh_completer()

    def delete_topic(self) -> None:
        selected = self.topic_list.currentItem()
        if selected is None:
            QMessageBox.warning(self, "ネタ管理エラー", "削除するテーマを選択してください。")
            return
        self.topics = [topic for topic in self.topics if topic != selected.text()]
        self.topic_service.save(self.topics)
        self.refresh_topic_list()
        self.refresh_completer()
        self.topic_edit.clear()

    def use_selected_topic(self, item: QListWidgetItem) -> None:
        self.topic_input.setText(item.text())
        self.topic_edit.setText(item.text())
        self.main_tabs.setCurrentIndex(1)
        self.update_wizard()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.paths, self)
        if dialog.exec() != SettingsDialog.Accepted:
            return
        self.settings = dialog.get_settings()
        try:
            self.settings_service.save(self.settings)
        except OSError as exc:
            QMessageBox.critical(self, "設定エラー", f"設定の保存に失敗しました。\n{exc}")
            return
        self.voicevox_service = VoicevoxService(self.settings.voicevox_url, self.settings.voicevox_speaker_id)
        self.video_render_service = VideoRenderService(create_video_editor(self.settings.video_editor_engine, self.settings.ffmpeg_path), self.settings)
        QMessageBox.information(self, "設定保存", "設定を保存しました。")
        self.apply_settings_to_ui()

    def _read_form_values(self) -> tuple[str, str, str, int, list[str]] | None:
        topic = self.topic_input.text().strip()
        if not topic:
            QMessageBox.warning(self, "入力エラー", "テーマを入力してください。")
            return None
        return topic, self.duration_box.currentText(), self.genre_box.currentText(), int(self.image_count_box.currentText()), self._parse_tags()

    def _set_image_count(self, image_count: int) -> None:
        value = str(image_count if image_count in {3, 4, 5, 6, 8} else 5)
        self.image_count_box.setCurrentText(value)

    def _parse_tags(self) -> list[str]:
        return self.tag_service.parse_youtube_text(self.youtube_tags_input.text())

    def _load_platform_tag_fields(self) -> None:
        if self.current_project is None:
            return
        hashtags_text = self._current_hashtags_text()
        youtube_tags = self.current_project.youtube_tags or self.current_project.tags or self.tag_service.youtube_tags_from_hashtags(hashtags_text)
        tiktok_tags = self.current_project.tiktok_tags or self.tag_service.tiktok_tags_from_hashtags(hashtags_text)
        self.youtube_tags_input.setText(self.tag_service.youtube_text(youtube_tags))
        self.tiktok_tags_input.setText(self.tag_service.tiktok_text(tiktok_tags))

    def _current_hashtags_text(self) -> str:
        text = self.preview_hashtags.toPlainText().strip()
        if text:
            return text
        if self.current_project is None:
            return ""
        return self._read_text(self.current_project.path / "hashtags.txt").strip()

    def _project_display_name(self, project: ProjectInfo) -> str:
        done_count = sum(1 for value in project.progress.values() if value)
        title = project.title or project.topic or project.name
        tags = f" #{' #'.join(project.tags[:3])}" if project.tags else ""
        series = f"{project.series}{project.series_number:03d}" if project.series else project.name
        return f"{title}  [{done_count}/{len(PROGRESS_ITEMS)}]\n{series} / {project.genre}{tags}"

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""
