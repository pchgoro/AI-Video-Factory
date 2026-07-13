from __future__ import annotations

import json
import webbrowser
import logging
import re
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QStringListModel, QUrl
from PySide6.QtGui import QGuiApplication, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
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
from services.ai_advisor_service import AdvisorReport, AiAdvisorService
from services.analytics_link_service import AnalyticsLinkService, AnalyticsLinkSummary
from services.analytics_service import AnalyticsError, AnalyticsReport, AnalyticsService
from services.category_service import CategoryService
from services.image_import_service import ImageImportError, ImageImportService
from services.parser import ChatGptAnswerParser, ChatGptParseError
from services.compilation_service import BrandingSegmentOptions, CompilationService
from services.project_service import ProjectService
from services.project_filter_service import ProjectBulkUpdate, ProjectFilterCriteria, ProjectFilterService, UNCATEGORIZED
from services.project_analytics_service import ProjectAnalyticsReport, ProjectAnalyticsService
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
        self.category_service = CategoryService(paths)
        self.project_filter_service = ProjectFilterService()
        self.analytics_service = AnalyticsService()
        self.analytics_link_service = AnalyticsLinkService(self.paths.base_dir)
        self.project_analytics_service = ProjectAnalyticsService()
        self.ai_advisor_service = AiAdvisorService()
        self.analytics_report = AnalyticsReport()
        self.analytics_link_summary = AnalyticsLinkSummary()
        self.ai_advisor_report = AdvisorReport()
        self.settings = settings_service.load()
        self.compilation_service = CompilationService(self.settings.ffmpeg_path, self.settings.output_width, self.settings.output_height)
        self.current_project: ProjectInfo | None = None
        self.projects: list[ProjectInfo] = []
        self.topics: list[str] = []
        self.templates: list[PromptTemplate] = []
        self.categories_by_genre: dict[str, list[str]] = {}
        self._suspend_project_classification_save = False

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
        layout.setContentsMargins(8, 8, 8, 8)
        header = QHBoxLayout()
        title = QLabel("AI Video Factory")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        settings_button = QPushButton("設定")
        settings_button.setMinimumWidth(72)
        settings_button.setMaximumWidth(86)
        settings_button.clicked.connect(self.open_settings)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(settings_button)
        layout.addLayout(header)

        filter_panel = QWidget()
        filter_layout = QVBoxLayout(filter_panel)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(6)
        self.project_search = QLineEdit()
        self.project_search.setPlaceholderText("タイトル / テーマ / ジャンル / 投稿日 / シリーズ / タグで検索")
        self.project_search.textChanged.connect(self.refresh_project_list)
        filter_layout.addWidget(self.project_search)

        self.genre_filter = QComboBox()
        self.genre_filter.currentTextChanged.connect(self.on_project_filter_genre_changed)
        filter_layout.addWidget(self.genre_filter)

        self.category_filter = QComboBox()
        self.category_filter.currentTextChanged.connect(self.on_project_filter_category_changed)
        filter_layout.addWidget(self.category_filter)

        self.series_filter = QComboBox()
        self.series_filter.currentTextChanged.connect(self.refresh_project_list)
        filter_layout.addWidget(self.series_filter)

        filter_grid = QGridLayout()
        filter_grid.setContentsMargins(0, 0, 0, 0)
        filter_grid.setVerticalSpacing(6)
        self.tag_filter = QLineEdit()
        self.tag_filter.setPlaceholderText("タグ")
        self.tag_filter.textChanged.connect(self.refresh_project_list)
        self.posted_filter = QComboBox()
        self.posted_filter.addItems(["すべての状態", "投稿済み", "手動で投稿済み", "CSVから投稿確認済み", "未投稿"])
        self.posted_filter.currentTextChanged.connect(self.refresh_project_list)
        self.progress_filter = QComboBox()
        self.progress_filter.addItems(["すべての状態", "制作中", "動画完成", "台本", "画像", "音声", "字幕"])
        self.progress_filter.currentTextChanged.connect(self.refresh_project_list)
        self.project_rating_filter = QComboBox()
        self.project_rating_filter.addItems(["評価すべて", "★以上", "★★以上", "★★★以上", "★★★★以上", "★★★★★"])
        self.project_rating_filter.currentTextChanged.connect(self.refresh_project_list)
        self.project_min_views_filter = QSpinBox()
        self.project_min_views_filter.setRange(0, 2_000_000_000)
        self.project_min_views_filter.setSingleStep(100)
        self.project_min_views_filter.valueChanged.connect(self.refresh_project_list)
        reset_filter_button = QPushButton("絞り込み解除")
        reset_filter_button.clicked.connect(self.reset_project_filters)
        filter_grid.addWidget(self.tag_filter, 0, 0, 1, 2)
        filter_grid.addWidget(self.posted_filter, 1, 0)
        filter_grid.addWidget(self.progress_filter, 1, 1)
        filter_grid.addWidget(self.project_rating_filter, 2, 0)
        filter_grid.addWidget(self.project_min_views_filter, 2, 1)
        filter_grid.addWidget(reset_filter_button, 3, 0, 1, 2)
        filter_layout.addLayout(filter_grid)

        self.project_count_label = QLabel("表示中: 0件 / 全0件")
        filter_layout.addWidget(self.project_count_label)
        filter_panel.setMinimumHeight(350)
        filter_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        filter_scroll = self._splitter_scroll_area(filter_panel)
        filter_scroll.setMinimumHeight(80)
        filter_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        filter_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.project_list = QListWidget()
        self.project_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.project_list.itemSelectionChanged.connect(self.load_selected_project)
        self.project_list.setMinimumHeight(140)
        self.project_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        project_list_widget = self.project_list

        topic_box = QGroupBox("一括ネタ管理")
        topic_layout = QVBoxLayout(topic_box)

        topic_list_panel = QWidget()
        topic_list_layout = QVBoxLayout(topic_list_panel)
        topic_list_layout.setContentsMargins(0, 0, 0, 0)
        self.topic_search = QLineEdit()
        self.topic_search.setPlaceholderText("ネタ検索")
        self.topic_search.textChanged.connect(self.refresh_topic_list)
        topic_list_layout.addWidget(self.topic_search)
        self.topic_list = QListWidget()
        self.topic_list.itemDoubleClicked.connect(self.use_selected_topic)
        self.topic_list.setMinimumHeight(120)
        self.topic_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        topic_list_layout.addWidget(self.topic_list, stretch=1)

        topic_controls_panel = QWidget()
        topic_controls_layout = QVBoxLayout(topic_controls_panel)
        topic_controls_layout.setContentsMargins(0, 0, 0, 0)
        self.topic_edit = QLineEdit()
        self.topic_edit.setPlaceholderText("テーマを追加・編集")
        topic_controls_layout.addWidget(self.topic_edit)

        topic_buttons = QHBoxLayout()
        for text, handler in [("追加", self.add_topic), ("編集", self.update_topic), ("削除", self.delete_topic)]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            topic_buttons.addWidget(button)
        topic_controls_layout.addLayout(topic_buttons)

        self.bulk_topics = QTextEdit()
        self.bulk_topics.setPlaceholderText("複数テーマを1行ずつ入力")
        self.bulk_topics.setFixedHeight(100)
        topic_controls_layout.addWidget(self.bulk_topics)
        topic_controls_layout.addWidget(QLabel("一括作成カテゴリ"))
        self.bulk_category_box = QComboBox()
        self.bulk_category_box.setEditable(True)
        topic_controls_layout.addWidget(self.bulk_category_box)
        topic_controls_layout.addWidget(QLabel("一括作成シリーズ"))
        self.bulk_series_input = QLineEdit()
        self.bulk_series_input.setPlaceholderText("未入力なら各テーマ名をシリーズにします")
        topic_controls_layout.addWidget(self.bulk_series_input)
        start_bulk_button = QPushButton("制作開始")
        start_bulk_button.clicked.connect(self.start_bulk_projects)
        topic_controls_layout.addWidget(start_bulk_button)

        classification_panel = QWidget()
        classification_layout = QVBoxLayout(classification_panel)
        classification_layout.setContentsMargins(0, 0, 0, 0)

        category_box = QGroupBox("カテゴリ管理")
        category_layout = QVBoxLayout(category_box)
        self.category_manage_genre_box = QComboBox()
        self.category_manage_genre_box.currentTextChanged.connect(self.refresh_category_manage_list)
        category_layout.addWidget(self.category_manage_genre_box)
        self.category_manage_list = QListWidget()
        category_layout.addWidget(self.category_manage_list)
        category_buttons = QGridLayout()
        for index, (text, handler) in enumerate([
            ("追加", self.add_category),
            ("編集", self.edit_category),
            ("削除", self.delete_category),
            ("上へ", lambda: self.move_category(-1)),
            ("下へ", lambda: self.move_category(1)),
            ("選択プロジェクトへ一括反映", self.bulk_update_selected_projects),
        ]):
            button = QPushButton(text)
            button.clicked.connect(handler)
            category_buttons.addWidget(button, index // 2, index % 2)
        category_layout.addLayout(category_buttons)
        classification_layout.addWidget(category_box)
        classification_layout.addStretch()

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
        topic_controls_layout.addWidget(memo_box)

        self.topic_management_splitter = QSplitter(Qt.Vertical)
        self.topic_management_splitter.setHandleWidth(8)
        self.topic_management_splitter.setChildrenCollapsible(False)
        self.topic_management_splitter.addWidget(topic_list_panel)
        self.topic_controls_scroll = self._splitter_scroll_area(topic_controls_panel)
        self.topic_management_splitter.addWidget(self.topic_controls_scroll)
        self.topic_management_splitter.setSizes([260, 760])
        self.topic_management_splitter.setMinimumHeight(720)
        topic_layout.addWidget(self.topic_management_splitter)
        topic_scroll = self._splitter_scroll_area(topic_box)

        project_tab = QWidget()
        project_tab_layout = QVBoxLayout(project_tab)
        project_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.left_content_splitter = QSplitter(Qt.Vertical)
        self.left_content_splitter.setHandleWidth(8)
        self.left_content_splitter.setChildrenCollapsible(False)
        self.left_content_splitter.addWidget(filter_scroll)
        self.left_content_splitter.addWidget(project_list_widget)
        self.left_content_splitter.setSizes([300, 360])
        project_tab_layout.addWidget(self.left_content_splitter)

        left_tabs = QTabWidget()
        left_tabs.addTab(project_tab, "プロジェクト")
        left_tabs.addTab(topic_scroll, "ネタ")
        left_tabs.addTab(self._splitter_scroll_area(classification_panel), "分類")
        layout.addWidget(left_tabs, stretch=1)
        return panel

    def _build_main_tabs(self) -> QTabWidget:
        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(self._scrollable_page(self._build_dashboard_tab()), "ホーム")
        self.main_tabs.addTab(self._scrollable_page(self._build_wizard_tab()), "制作ウィザード")
        self.main_tabs.addTab(self._build_compilation_tab(), "総集編")
        self.main_tabs.addTab(self._scrollable_page(self._build_analytics_tab()), "Analytics")
        self.main_tabs.addTab(self._scrollable_page(self._build_ai_advisor_tab()), "AIアドバイザー")
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

        analytics_box = QGroupBox("Analyticsサマリー")
        analytics_grid = QGridLayout(analytics_box)
        self.dashboard_analytics_labels: dict[str, QLabel] = {}
        analytics_items = [
            ("youtube_views", "YouTube総再生数"),
            ("tiktok_views", "TikTok総再生数"),
            ("best_week", "今週の最高成績動画"),
            ("unlinked", "未紐付け動画数"),
            ("csv_posted", "投稿確認済み"),
            ("improvement", "改善候補動画数"),
            ("continuation", "続編推奨動画数"),
        ]
        for index, (key, label) in enumerate(analytics_items):
            caption = QLabel(label)
            value = QLabel("CSV未取込")
            value.setStyleSheet("font-size: 16px; font-weight: 700; color: #ce9178;")
            self.dashboard_analytics_labels[key] = value
            analytics_grid.addWidget(caption, index // 3 * 2, index % 3)
            analytics_grid.addWidget(value, index // 3 * 2 + 1, index % 3)
        layout.addWidget(analytics_box)

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
        self.content_tabs.addTab(self._build_project_analytics_tab(), "個別分析")
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
        self.genre_box.currentTextChanged.connect(self.on_wizard_genre_changed)
        self.category_box = QComboBox()
        self.category_box.setEditable(True)
        self.category_box.currentIndexChanged.connect(self.save_current_project_classification)
        if self.category_box.lineEdit():
            self.category_box.lineEdit().editingFinished.connect(self.save_current_project_classification)
        self.series_input = QLineEdit()
        self.series_input.setPlaceholderText("例: ブラックホール基礎")
        self.series_input.editingFinished.connect(self.save_current_project_classification)
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
        form.addWidget(QLabel("カテゴリ"), 2, 2)
        form.addWidget(self.category_box, 2, 3)
        form.addWidget(QLabel("シリーズ"), 2, 4)
        form.addWidget(self.series_input, 2, 5)
        form.addWidget(QLabel("YouTubeタグ"), 3, 0)
        form.addWidget(self.youtube_tags_input, 3, 1, 1, 3)
        youtube_buttons = QHBoxLayout()
        save_youtube_tags_button = QPushButton("youtubeタグ保存")
        save_youtube_tags_button.clicked.connect(self.save_youtube_tags)
        copy_youtube_tags_button = QPushButton("コピー")
        copy_youtube_tags_button.clicked.connect(self.copy_youtube_tags_to_clipboard)
        youtube_buttons.addWidget(save_youtube_tags_button)
        youtube_buttons.addWidget(copy_youtube_tags_button)
        form.addLayout(youtube_buttons, 3, 4, 1, 2)
        form.addWidget(QLabel("TikTokタグ"), 4, 0)
        form.addWidget(self.tiktok_tags_input, 4, 1, 1, 3)
        tiktok_buttons = QHBoxLayout()
        save_tiktok_tags_button = QPushButton("tiktokタグ保存")
        save_tiktok_tags_button.clicked.connect(self.save_tiktok_tags)
        copy_tiktok_tags_button = QPushButton("コピー")
        copy_tiktok_tags_button.clicked.connect(self.copy_tiktok_tags_to_clipboard)
        tiktok_buttons.addWidget(save_tiktok_tags_button)
        tiktok_buttons.addWidget(copy_tiktok_tags_button)
        form.addLayout(tiktok_buttons, 4, 4, 1, 2)
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
        imported_images_header = QHBoxLayout()
        imported_images_header.addWidget(QLabel("取り込み済み画像"))
        imported_images_header.addStretch()
        imported_images_header.addWidget(QLabel("高さ"))
        self.image_thumbnail_height_box = QSpinBox()
        self.image_thumbnail_height_box.setRange(120, 1200)
        self.image_thumbnail_height_box.setSingleStep(40)
        self.image_thumbnail_height_box.setValue(420)
        self.image_thumbnail_height_box.setSuffix(" px")
        self.image_thumbnail_height_box.valueChanged.connect(self.set_image_thumbnail_area_height)
        imported_images_header.addWidget(self.image_thumbnail_height_box)
        imported_images_layout.addLayout(imported_images_header)
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
        self.set_image_thumbnail_area_height(self.image_thumbnail_height_box.value())
        return panel

    def _build_project_analytics_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        action_row = QHBoxLayout()
        refresh_button = QPushButton("個別分析を更新")
        refresh_button.clicked.connect(self.refresh_project_analytics_view)
        youtube_button = QPushButton("YouTube URLを開く")
        youtube_button.clicked.connect(lambda _checked=False: self.open_project_analytics_url("YouTube"))
        tiktok_button = QPushButton("TikTok URLを開く")
        tiktok_button.clicked.connect(lambda _checked=False: self.open_project_analytics_url("TikTok"))
        action_row.addWidget(refresh_button)
        action_row.addWidget(youtube_button)
        action_row.addWidget(tiktok_button)
        action_row.addStretch()
        layout.addLayout(action_row)
        self.project_analytics_text = QTextEdit()
        self.project_analytics_text.setReadOnly(True)
        self.project_analytics_text.setPlaceholderText("CSVを読み込むと、このプロジェクトの個別成績と改善案が表示されます。")
        layout.addWidget(self.project_analytics_text, stretch=1)
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

    def _build_compilation_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("ジャンル"))
        self.compilation_genre_box = QComboBox()
        self.compilation_genre_box.currentTextChanged.connect(self.on_compilation_genre_changed)
        top_row.addWidget(self.compilation_genre_box, stretch=1)
        top_row.addWidget(QLabel("カテゴリ"))
        self.compilation_category_box = QComboBox()
        self.compilation_category_box.currentTextChanged.connect(self.refresh_compilation_project_list)
        top_row.addWidget(self.compilation_category_box, stretch=1)
        refresh_button = QPushButton("更新")
        refresh_button.clicked.connect(self.refresh_compilation_genres)
        top_row.addWidget(refresh_button)
        layout.addLayout(top_row)

        self.compilation_summary_label = QLabel("ジャンル: - / 動画本数: 0 / 総時間: 00:00")
        layout.addWidget(self.compilation_summary_label)

        self.compilation_project_list = QListWidget()
        layout.addWidget(self.compilation_project_list, stretch=1)

        order_buttons = QHBoxLayout()
        up_button = QPushButton("上へ")
        up_button.clicked.connect(lambda _checked=False: self.move_compilation_item(-1))
        down_button = QPushButton("下へ")
        down_button.clicked.connect(lambda _checked=False: self.move_compilation_item(1))
        order_buttons.addWidget(up_button)
        order_buttons.addWidget(down_button)
        order_buttons.addStretch()
        layout.addLayout(order_buttons)

        create_button = QPushButton("総集編を作成")
        create_button.clicked.connect(self.create_compilation_video)
        layout.addWidget(create_button)
        return panel

    def _build_analytics_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        action_row = QHBoxLayout()
        import_button = QPushButton("CSVを読み込む")
        import_button.clicked.connect(self.import_analytics_csv)
        import_folder_button = QPushButton("CSVフォルダを読み込む")
        import_folder_button.clicked.connect(self.import_analytics_folder)
        export_button = QPushButton("分析結果CSV保存")
        export_button.clicked.connect(self.export_analytics_csv)
        refresh_button = QPushButton("再表示")
        refresh_button.clicked.connect(self.refresh_analytics_view)
        action_row.addWidget(import_button)
        action_row.addWidget(import_folder_button)
        action_row.addWidget(export_button)
        action_row.addWidget(refresh_button)
        action_row.addStretch()
        layout.addLayout(action_row)

        summary_box = QGroupBox("集計")
        summary_grid = QGridLayout(summary_box)
        self.analytics_summary_labels: dict[str, QLabel] = {}
        summary_items = [
            ("total_videos", "総動画数"),
            ("total_views", "総再生数"),
            ("average_views", "平均再生数"),
            ("max_views", "最高再生数"),
            ("min_views", "最低再生数"),
            ("total_likes", "総いいね"),
            ("total_comments", "総コメント"),
            ("average_like_rate", "平均いいね率"),
            ("average_comment_rate", "平均コメント率"),
        ]
        for index, (key, label) in enumerate(summary_items):
            caption = QLabel(label)
            value = QLabel("-")
            value.setStyleSheet("font-size: 18px; font-weight: 700; color: #9cdcfe;")
            self.analytics_summary_labels[key] = value
            summary_grid.addWidget(caption, index // 3 * 2, index % 3)
            summary_grid.addWidget(value, index // 3 * 2 + 1, index % 3)
        layout.addWidget(summary_box)

        link_box = QGroupBox("Project Analytics")
        link_grid = QGridLayout(link_box)
        self.analytics_link_labels: dict[str, QLabel] = {}
        link_items = [
            ("linked", "紐付け済み動画数"),
            ("unlinked", "未紐付け動画数"),
            ("rate", "紐付け率"),
            ("platforms", "YouTube / TikTok別"),
        ]
        for index, (key, label) in enumerate(link_items):
            caption = QLabel(label)
            value = QLabel("-")
            value.setStyleSheet("font-size: 16px; font-weight: 700; color: #ce9178;")
            self.analytics_link_labels[key] = value
            link_grid.addWidget(caption, index // 2 * 2, index % 2)
            link_grid.addWidget(value, index // 2 * 2 + 1, index % 2)
        layout.addWidget(link_box)

        search_box = QGroupBox("検索")
        search_layout = QGridLayout(search_box)
        self.analytics_title_filter = QLineEdit()
        self.analytics_title_filter.setPlaceholderText("タイトル")
        self.analytics_genre_filter = QLineEdit()
        self.analytics_genre_filter.setPlaceholderText("ジャンル")
        self.analytics_min_views_filter = QSpinBox()
        self.analytics_min_views_filter.setRange(0, 2_000_000_000)
        self.analytics_min_views_filter.setSingleStep(100)
        self.analytics_date_filter = QLineEdit()
        self.analytics_date_filter.setPlaceholderText("投稿日 例: 2026-07")
        self.analytics_rating_filter = QComboBox()
        self.analytics_rating_filter.addItems(["すべて", "★以上", "★★以上", "★★★以上", "★★★★以上", "★★★★★"])
        for widget in [
            self.analytics_title_filter,
            self.analytics_genre_filter,
            self.analytics_min_views_filter,
            self.analytics_date_filter,
            self.analytics_rating_filter,
        ]:
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self.apply_analytics_filters)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self.apply_analytics_filters)
            else:
                widget.textChanged.connect(self.apply_analytics_filters)
        search_layout.addWidget(QLabel("タイトル"), 0, 0)
        search_layout.addWidget(self.analytics_title_filter, 0, 1)
        search_layout.addWidget(QLabel("ジャンル"), 0, 2)
        search_layout.addWidget(self.analytics_genre_filter, 0, 3)
        search_layout.addWidget(QLabel("再生数以上"), 1, 0)
        search_layout.addWidget(self.analytics_min_views_filter, 1, 1)
        search_layout.addWidget(QLabel("投稿日"), 1, 2)
        search_layout.addWidget(self.analytics_date_filter, 1, 3)
        search_layout.addWidget(QLabel("評価"), 2, 0)
        search_layout.addWidget(self.analytics_rating_filter, 2, 1)
        layout.addWidget(search_box)

        self.analytics_tabs = QTabWidget()
        graph_panel = QWidget()
        graph_layout = QVBoxLayout(graph_panel)
        self.analytics_graph_label = QLabel("CSVを読み込むとグラフが表示されます。")
        self.analytics_graph_label.setAlignment(Qt.AlignCenter)
        self.analytics_graph_label.setMinimumHeight(420)
        graph_layout.addWidget(self.analytics_graph_label)

        self.analytics_ranking_text = QTextEdit()
        self.analytics_ranking_text.setReadOnly(True)
        self.analytics_genre_text = QTextEdit()
        self.analytics_genre_text.setReadOnly(True)
        self.analytics_title_text = QTextEdit()
        self.analytics_title_text.setReadOnly(True)
        self.analytics_records_text = QTextEdit()
        self.analytics_records_text.setReadOnly(True)
        self.analytics_comments_text = QTextEdit()
        self.analytics_comments_text.setReadOnly(True)
        self.analytics_project_text = QTextEdit()
        self.analytics_project_text.setReadOnly(True)
        unmatched_panel = QWidget()
        unmatched_layout = QVBoxLayout(unmatched_panel)
        self.analytics_linked_list = QListWidget()
        self.analytics_unmatched_list = QListWidget()
        self.analytics_project_combo = QComboBox()
        link_buttons = QHBoxLayout()
        save_link_button = QPushButton("紐付け保存")
        save_link_button.clicked.connect(self.save_manual_analytics_link)
        unlink_button = QPushButton("紐付け解除")
        unlink_button.clicked.connect(self.remove_manual_analytics_link)
        link_buttons.addWidget(QLabel("紐付け先"))
        link_buttons.addWidget(self.analytics_project_combo, stretch=1)
        link_buttons.addWidget(save_link_button)
        link_buttons.addWidget(unlink_button)
        unmatched_layout.addWidget(QLabel("紐付け済み動画一覧"))
        unmatched_layout.addWidget(self.analytics_linked_list, stretch=1)
        unmatched_layout.addWidget(QLabel("未紐付け動画一覧"))
        unmatched_layout.addWidget(self.analytics_unmatched_list, stretch=1)
        unmatched_layout.addLayout(link_buttons)

        self.analytics_tabs.addTab(graph_panel, "グラフ")
        self.analytics_tabs.addTab(self.analytics_ranking_text, "ランキング")
        self.analytics_tabs.addTab(self.analytics_genre_text, "ジャンル分析")
        self.analytics_tabs.addTab(self.analytics_title_text, "タイトル分析")
        self.analytics_tabs.addTab(self.analytics_records_text, "動画一覧")
        self.analytics_tabs.addTab(self.analytics_project_text, "プロジェクト別成績")
        self.analytics_tabs.addTab(unmatched_panel, "未紐付け管理")
        self.analytics_tabs.addTab(self.analytics_comments_text, "コメント")
        layout.addWidget(self.analytics_tabs, stretch=1)
        self.refresh_analytics_view()
        return panel

    def _build_ai_advisor_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        top_row = QHBoxLayout()
        refresh_button = QPushButton("提案を更新")
        refresh_button.clicked.connect(self.refresh_ai_advisor_view)
        top_row.addWidget(refresh_button)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.ai_advisor_daily_message = QLabel("")
        self.ai_advisor_daily_message.setStyleSheet("font-size: 18px; font-weight: 700; color: #dcdcaa; padding: 8px;")
        layout.addWidget(self.ai_advisor_daily_message)

        grid = QGridLayout()
        self.ai_today_text = QTextEdit()
        self.ai_comments_text = QTextEdit()
        self.ai_themes_text = QTextEdit()
        self.ai_titles_text = QTextEdit()
        self.ai_plan_text = QTextEdit()
        self.ai_improvements_text = QTextEdit()
        self.ai_goal_text = QTextEdit()
        self.ai_badges_text = QTextEdit()
        self.ai_inventory_text = QTextEdit()

        widgets = [
            ("今日の分析", self.ai_today_text),
            ("自動コメント", self.ai_comments_text),
            ("おすすめテーマ", self.ai_themes_text),
            ("おすすめタイトル", self.ai_titles_text),
            ("次の企画", self.ai_plan_text),
            ("改善ポイント", self.ai_improvements_text),
            ("制作目標", self.ai_goal_text),
            ("バッジ", self.ai_badges_text),
            ("ネタ在庫", self.ai_inventory_text),
        ]
        for index, (title, widget) in enumerate(widgets):
            widget.setReadOnly(True)
            widget.setMinimumHeight(135)
            box = QGroupBox(title)
            box_layout = QVBoxLayout(box)
            box_layout.addWidget(widget)
            grid.addWidget(box, index // 2, index % 2)
        layout.addLayout(grid, stretch=1)
        self.refresh_ai_advisor_view()
        return panel

    def set_image_thumbnail_area_height(self, height: int) -> None:
        if not hasattr(self, "image_thumbnail_scroll"):
            return
        self.image_thumbnail_scroll.setMinimumHeight(height)
        self.image_thumbnail_scroll.setMaximumHeight(height)
        if hasattr(self, "assets_splitter"):
            self.assets_splitter.setSizes([height + 40, 180])

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
        self.categories_by_genre = self.category_service.load()
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
        self.category_manage_genre_box.blockSignals(True)
        self.category_manage_genre_box.clear()
        self.category_manage_genre_box.addItems(self.settings.genres)
        self.category_manage_genre_box.blockSignals(False)
        self.genre_filter.blockSignals(True)
        self.genre_filter.clear()
        self.genre_filter.addItem("すべてのジャンル")
        self.genre_filter.addItems(self.settings.genres)
        self.genre_filter.blockSignals(False)
        self.refresh_form_categories()
        self.refresh_project_category_filter()
        self.refresh_category_manage_list()
        self.template_box.blockSignals(True)
        self.template_box.clear()
        self.template_box.addItems([template.name for template in self.templates])
        self.template_box.blockSignals(False)
        self.apply_template()

    def reload_projects(self) -> None:
        self.projects = self.project_service.list_projects()
        self.refresh_project_category_filter()
        self.refresh_project_series_filter()
        self.refresh_project_list()
        self.refresh_dashboard()
        self.refresh_completer()
        if hasattr(self, "compilation_genre_box"):
            self.refresh_compilation_genres()
        if hasattr(self, "analytics_records_text"):
            self.refresh_analytics_view()
        if hasattr(self, "ai_today_text"):
            self.refresh_ai_advisor_view()

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
        self.refresh_dashboard_analytics()

    def refresh_dashboard_analytics(self) -> None:
        if not hasattr(self, "dashboard_analytics_labels"):
            return
        if not self.analytics_report.records:
            for label in self.dashboard_analytics_labels.values():
                label.setText("CSV未取込")
            return
        youtube_views = sum(record.views for record in self.analytics_report.records if record.platform == "YouTube")
        tiktok_views = sum(record.views for record in self.analytics_report.records if record.platform == "TikTok")
        best = max(self.analytics_report.records, key=lambda record: record.views, default=None)
        improvement_count = sum(1 for record in self.analytics_report.records if record.rating <= 2)
        continuation_count = sum(1 for record in self.analytics_report.records if record.rating >= 4 and record.project_name)
        csv_posted = len({record.project_name for record in self.analytics_report.records if record.project_name})
        values = {
            "youtube_views": f"{youtube_views:,}",
            "tiktok_views": f"{tiktok_views:,}",
            "best_week": f"{best.title} ({best.views:,}回)" if best else "CSV未取込",
            "unlinked": str(self.analytics_link_summary.unlinked_count),
            "csv_posted": str(csv_posted),
            "improvement": str(improvement_count),
            "continuation": str(continuation_count),
        }
        for key, value in values.items():
            self.dashboard_analytics_labels[key].setText(value)

    def import_analytics_csv(self) -> None:
        file_paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "分析するCSVを選択",
            str(self.paths.base_dir),
            "CSVファイル (*.csv)",
        )
        if not file_paths:
            return
        self._import_analytics_paths([Path(path) for path in file_paths])

    def import_analytics_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "CSVフォルダを選択", str(self.paths.base_dir))
        if not folder:
            return
        self._import_analytics_paths([Path(folder)])

    def _import_analytics_paths(self, paths: list[Path]) -> None:
        try:
            self.analytics_report = self.analytics_service.import_paths(paths, self.projects)
            self.analytics_link_summary = self.analytics_link_service.apply_links(self.analytics_report.records, self.projects)
            self.project_analytics_service.save_project_analytics(self.projects, self.analytics_report.records)
            graph_path = self.paths.exports_dir / "analytics_dashboard.png"
            self.analytics_service.render_dashboard_graphs(self.analytics_report, graph_path)
        except AnalyticsError as exc:
            QMessageBox.warning(self, "Analyticsエラー", str(exc))
            return
        self.projects = self.project_service.list_projects()
        self.refresh_analytics_view()
        self.refresh_ai_advisor_view()
        self.refresh_project_analytics_view()
        QMessageBox.information(self, "Analytics", "CSVを読み込み、プロジェクト紐付けを更新しました。")

    def export_analytics_csv(self) -> None:
        if not self.analytics_report.records:
            QMessageBox.warning(self, "Analyticsエラー", "先にCSVを読み込んでください。")
            return
        output_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "分析結果CSVを保存",
            str(self.paths.exports_dir / "analytics_result.csv"),
            "CSVファイル (*.csv)",
        )
        if not output_path:
            return
        try:
            self.analytics_service.export_report_csv(self.analytics_report, Path(output_path))
        except AnalyticsError as exc:
            QMessageBox.warning(self, "Analyticsエラー", str(exc))
            return
        QMessageBox.information(self, "Analytics", "分析結果CSVを保存しました。")

    def refresh_analytics_view(self) -> None:
        if not hasattr(self, "analytics_summary_labels"):
            return
        report = self.analytics_report
        summary = report.summary
        values = {
            "total_videos": str(summary.total_videos),
            "total_views": f"{summary.total_views:,}",
            "average_views": f"{summary.average_views:,.0f}",
            "max_views": f"{summary.max_views:,}",
            "min_views": f"{summary.min_views:,}",
            "total_likes": f"{summary.total_likes:,}",
            "total_comments": f"{summary.total_comments:,}",
            "average_like_rate": f"{summary.average_like_rate:.2f}%",
            "average_comment_rate": f"{summary.average_comment_rate:.2f}%",
        }
        for key, value in values.items():
            self.analytics_summary_labels[key].setText(value)
        if hasattr(self, "analytics_link_labels"):
            self.analytics_link_summary = self.analytics_link_service.apply_links(report.records, self.projects)
            platform_text = " / ".join(
                f"{platform}: {linked}/{total}"
                for platform, (linked, total) in self.analytics_link_summary.platform_counts().items()
            ) or "-"
            link_values = {
                "linked": str(self.analytics_link_summary.linked_count),
                "unlinked": str(self.analytics_link_summary.unlinked_count),
                "rate": f"{self.analytics_link_summary.link_rate:.1f}%",
                "platforms": platform_text,
            }
            for key, value in link_values.items():
                self.analytics_link_labels[key].setText(value)
            self.refresh_dashboard_analytics()

        self.analytics_ranking_text.setPlainText(self._analytics_ranking_text(report))
        self.analytics_genre_text.setPlainText(self._analytics_genre_text(report))
        self.analytics_title_text.setPlainText(self._analytics_title_text(report))
        self.analytics_comments_text.setPlainText("\n".join(report.comments))
        if hasattr(self, "analytics_project_text"):
            self.analytics_project_text.setPlainText(self._analytics_project_text())
            self.refresh_analytics_link_controls()
        self.apply_analytics_filters()
        graph_path = self.paths.exports_dir / "analytics_dashboard.png"
        if graph_path.exists():
            pixmap = QPixmap(str(graph_path))
            if not pixmap.isNull():
                self.analytics_graph_label.setPixmap(
                    pixmap.scaled(self.analytics_graph_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        self.refresh_ai_advisor_view()
        self.refresh_project_analytics_view()

    def refresh_ai_advisor_view(self) -> None:
        if not hasattr(self, "ai_today_text"):
            return
        self.ai_advisor_report = self.ai_advisor_service.build(self.analytics_report, self.projects, self.topics)
        report = self.ai_advisor_report
        self.ai_advisor_daily_message.setText(report.daily_message)
        self.ai_today_text.setPlainText("\n".join(f"・{line}" for line in report.today_analysis))
        self.ai_comments_text.setPlainText("\n".join(f"・{line}" for line in report.comments))
        self.ai_themes_text.setPlainText(
            "\n".join(
                f"{'★' * item.stars}{'☆' * (5 - item.stars)}\n{item.name}\n{item.reason}".strip()
                for item in report.recommended_themes
            )
        )
        self.ai_titles_text.setPlainText("\n".join(f"・{title}" for title in report.recommended_titles))
        self.ai_plan_text.setPlainText("\n".join(report.next_plan))
        self.ai_improvements_text.setPlainText("\n".join(f"・{line}" for line in report.improvements))
        self.ai_goal_text.setPlainText(
            f"今月目標\n{report.goal.target}本\n\n現在\n{report.goal.current}本\n\n{report.goal.bar}\n{report.goal.percent}%"
        )
        self.ai_badges_text.setPlainText(
            "\n".join(f"{'✅' if badge.achieved else '□'} {badge.label}" for badge in report.badges)
        )
        self.ai_inventory_text.setPlainText(
            "\n".join(
                [
                    f"未制作\n{report.inventory.unmade}件",
                    f"制作中\n{report.inventory.in_progress}件",
                    f"完成\n{report.inventory.completed}件",
                    f"投稿済\n{report.inventory.posted}件",
                ]
            )
        )

    def apply_analytics_filters(self) -> None:
        if not hasattr(self, "analytics_records_text"):
            return
        rating_index = self.analytics_rating_filter.currentIndex()
        records = self.analytics_service.filter_records(
            self.analytics_report.records,
            title_keyword=self.analytics_title_filter.text(),
            genre_keyword=self.analytics_genre_filter.text(),
            min_views=self.analytics_min_views_filter.value(),
            posted_date=self.analytics_date_filter.text(),
            min_rating=rating_index,
        )
        if not records:
            self.analytics_records_text.setPlainText("該当する動画がありません。")
            return
        self.analytics_records_text.setPlainText("\n".join(self._analytics_record_line(record) for record in records))

    def _analytics_ranking_text(self, report: AnalyticsReport) -> str:
        if not report.records:
            return "CSVを読み込むとランキングが表示されます。"
        sections: list[str] = []
        for name, records in report.rankings.items():
            sections.append(f"【{name} TOP10】")
            for index, record in enumerate(records, start=1):
                if name == "いいね率":
                    value = f"{record.like_rate:.2f}%"
                elif name == "コメント率":
                    value = f"{record.comment_rate:.2f}%"
                elif name == "いいね":
                    value = f"{record.likes:,}"
                elif name == "コメント":
                    value = f"{record.comments:,}"
                else:
                    value = f"{record.views:,}"
                sections.append(f"{index}. {record.title} / {value}")
            sections.append("")
        return "\n".join(sections).strip()

    def _analytics_genre_text(self, report: AnalyticsReport) -> str:
        if not report.genre_metrics:
            return "ジャンル分析データがありません。"
        lines = ["【ジャンル別】"]
        for metric in report.genre_metrics:
            lines.append(
                f"{metric.name}: 動画数 {metric.count} / 平均再生数 {metric.average_views:,.0f} / 平均いいね {metric.average_likes:,.0f}"
            )
        lines.append("")
        lines.append("【カテゴリ別】")
        if not report.category_metrics:
            lines.append("カテゴリ分析データがありません。")
        for metric in report.category_metrics:
            stars = "★" * round(metric.average_rating or 1) + "☆" * (5 - round(metric.average_rating or 1))
            lines.append(
                f"{metric.name}: 動画数 {metric.count} / 総再生数 {metric.total_views:,} / 平均再生数 {metric.average_views:,.0f} "
                f"/ 平均いいね率 {metric.average_like_rate:.2f}% / 平均視聴率 {metric.average_view_percentage:.1f}% / 評価 {stars}"
            )
        return "\n".join(lines)

    def _analytics_title_text(self, report: AnalyticsReport) -> str:
        if not report.records:
            return "タイトル分析データがありません。"
        lines = ["【頻出ワード】"]
        for metric in report.word_metrics:
            lines.append(f"{metric.word}: {metric.count}件 / 平均再生数 {metric.average_views:,.0f}")
        lines.append("")
        lines.append("【タイトルパターン】")
        for metric in report.pattern_metrics:
            lines.append(
                f"{metric.name}: 動画数 {metric.count} / 平均再生数 {metric.average_views:,.0f} / 平均いいね {metric.average_likes:,.0f}"
            )
        return "\n".join(lines)

    def _analytics_record_line(self, record) -> str:
        stars = "★" * record.rating + "☆" * (5 - record.rating)
        project = f" / project: {record.project_name}" if record.project_name else " / project: 未紐付け"
        return (
            f"{stars}  {record.title}\n"
            f"  ジャンル: {record.genre} / カテゴリ: {record.category or '未分類'} / 再生数: {record.views:,} / いいね: {record.likes:,} "
            f"/ コメント: {record.comments:,} / いいね率: {record.like_rate:.2f}% / コメント率: {record.comment_rate:.2f}% "
            f"/ 投稿日: {record.posted_date or '-'}{project}"
        )

    def _analytics_project_text(self) -> str:
        if not self.analytics_report.records:
            return "CSVを読み込むとプロジェクト別成績が表示されます。"
        lines = [
            "【紐付け状況】",
            f"紐付け済み: {self.analytics_link_summary.linked_count}",
            f"未紐付け: {self.analytics_link_summary.unlinked_count}",
            f"紐付け率: {self.analytics_link_summary.link_rate:.1f}%",
            "",
            "【プロジェクト別成績】",
        ]
        grouped: dict[str, list] = {}
        for record in self.analytics_report.records:
            grouped.setdefault(record.project_name or "未紐付け", []).append(record)
        for project_name, records in sorted(grouped.items()):
            views = sum(record.views for record in records)
            likes = sum(record.likes for record in records)
            comments = sum(record.comments for record in records)
            lines.append(f"{project_name}: {len(records)}件 / 再生 {views:,} / いいね {likes:,} / コメント {comments:,}")
            for record in records:
                lines.append(f"  - {record.platform}: {record.title} ({record.views:,}回)")
        return "\n".join(lines)

    def refresh_analytics_link_controls(self) -> None:
        if not hasattr(self, "analytics_unmatched_list"):
            return
        self.analytics_unmatched_list.clear()
        self.analytics_linked_list.clear()
        for record in self.analytics_report.records:
            if record.project_name:
                item = QListWidgetItem(f"{record.platform}: {record.title} -> {record.project_name}")
                item.setData(Qt.UserRole, self.analytics_link_service.record_key(record))
                self.analytics_linked_list.addItem(item)
                continue
            item = QListWidgetItem(f"{record.platform}: {record.title}")
            item.setData(Qt.UserRole, self.analytics_link_service.record_key(record))
            self.analytics_unmatched_list.addItem(item)
        current_project = self.analytics_project_combo.currentText() if hasattr(self, "analytics_project_combo") else ""
        self.analytics_project_combo.blockSignals(True)
        self.analytics_project_combo.clear()
        for project in self.projects:
            self.analytics_project_combo.addItem(project.title or project.topic or project.name, project.name)
        if current_project:
            self.analytics_project_combo.setCurrentText(current_project)
        self.analytics_project_combo.blockSignals(False)

    def save_manual_analytics_link(self) -> None:
        record = self._selected_unmatched_record()
        if record is None:
            QMessageBox.warning(self, "Analyticsエラー", "紐付ける未紐付け動画を選択してください。")
            return
        project_name = self.analytics_project_combo.currentData()
        if not project_name:
            QMessageBox.warning(self, "Analyticsエラー", "紐付け先プロジェクトを選択してください。")
            return
        self.analytics_link_service.save_manual_link(record, str(project_name))
        record.project_name = str(project_name)
        self.analytics_link_summary = self.analytics_link_service.apply_links(self.analytics_report.records, self.projects)
        self.project_analytics_service.save_project_analytics(self.projects, self.analytics_report.records)
        self.refresh_analytics_view()
        QMessageBox.information(self, "Analytics", "手動紐付けを保存しました。")

    def remove_manual_analytics_link(self) -> None:
        record = self._selected_analytics_record_for_unlink()
        if record is None:
            QMessageBox.warning(self, "Analyticsエラー", "解除する動画を選択してください。未紐付け一覧または動画一覧の対象を選び直してください。")
            return
        self.analytics_link_service.remove_manual_link(record)
        record.project_name = ""
        self.analytics_link_summary = self.analytics_link_service.apply_links(self.analytics_report.records, self.projects)
        self.refresh_analytics_view()
        QMessageBox.information(self, "Analytics", "手動紐付けを解除しました。")

    def _selected_unmatched_record(self):
        selected = self.analytics_unmatched_list.currentItem() if hasattr(self, "analytics_unmatched_list") else None
        if selected is None:
            return None
        key = selected.data(Qt.UserRole)
        return next((record for record in self.analytics_report.records if self.analytics_link_service.record_key(record) == key), None)

    def _selected_analytics_record_for_unlink(self):
        selected = self.analytics_linked_list.currentItem() if hasattr(self, "analytics_linked_list") else None
        if selected is None:
            return None
        key = selected.data(Qt.UserRole)
        return next((record for record in self.analytics_report.records if self.analytics_link_service.record_key(record) == key), None)

    def refresh_project_analytics_view(self) -> None:
        if not hasattr(self, "project_analytics_text"):
            return
        if self.current_project is None:
            self.project_analytics_text.setPlainText("プロジェクトを選択してください。")
            return
        report = self.project_analytics_service.build_project_report(self.current_project, self.analytics_report, self.topics)
        self.project_analytics_text.setPlainText(self._project_analytics_report_text(report))

    def open_project_analytics_url(self, platform: str) -> None:
        if self.current_project is None:
            return
        report = self.project_analytics_service.build_project_report(self.current_project, self.analytics_report, self.topics)
        record = report.youtube if platform == "YouTube" else report.tiktok
        if not record or not record.url:
            QMessageBox.information(self, "Analytics", f"{platform} URLは未取得です。")
            return
        webbrowser.open(record.url)

    def _project_analytics_report_text(self, report: ProjectAnalyticsReport) -> str:
        lines = [f"個別分析: {report.project.title or report.project.topic or report.project.name}", ""]
        lines.extend(self._platform_project_lines("YouTube", report.youtube, report.youtube_insight))
        lines.append("")
        lines.extend(self._platform_project_lines("TikTok", report.tiktok, report.tiktok_insight))
        lines.append("")
        lines.append("【YouTube / TikTok 横断比較】")
        lines.extend(f"・{line}" for line in report.cross_platform_comments)
        lines.append("")
        lines.append("【続編候補】")
        lines.extend([f"・{topic}" for topic in report.continuation_topics] or ["分析データ不足"])
        return "\n".join(lines)

    def _platform_project_lines(self, platform: str, record, insight) -> list[str]:
        stars = "★" * insight.rating + "☆" * (5 - insight.rating)
        if record is None:
            return [f"【{platform}】", "投稿状態: 未投稿または未取得", "データ: 未取得"]
        if platform == "YouTube":
            metrics = [
                f"投稿状態: CSVから投稿確認済み",
                f"公開日: {record.posted_date or '未取得'}",
                f"URL: {record.url or '未取得'}",
                f"視聴回数: {record.views:,}",
                f"高評価数: {record.likes:,}",
                f"コメント数: {record.comments:,}",
                f"CTR: {record.ctr:.2f}%" if record.ctr else "CTR: 未取得",
                f"平均視聴時間: {record.average_view_duration:.1f}秒" if record.average_view_duration else "平均視聴時間: 未取得",
                f"平均視聴率: {record.average_percentage_viewed:.2f}%" if record.average_percentage_viewed else "平均視聴率: 未取得",
                f"登録者増減: {record.subscriber_change:,}",
            ]
        else:
            metrics = [
                f"投稿状態: CSVから投稿確認済み",
                f"投稿日: {record.posted_date or '未取得'}",
                f"URL: {record.url or '未取得'}",
                f"視聴回数: {record.views:,}",
                f"いいね数: {record.likes:,}",
                f"コメント数: {record.comments:,}",
                f"シェア数: {record.shares:,}",
                f"保存数: {record.saves:,}",
                f"平均視聴時間: {record.average_view_duration:.1f}秒" if record.average_view_duration else "平均視聴時間: 未取得",
                f"完視聴率: {record.completion_rate:.2f}%" if record.completion_rate else "完視聴率: 未取得",
                f"フォロワー増減: {record.follower_change:,}",
            ]
        lines = [f"【{platform}】", *metrics, f"評価: {stars} {insight.label}", "伸びた理由:"]
        lines.extend(f"・{line}" for line in insight.reasons)
        lines.append("次回改善案:")
        lines.extend(f"・{line}" for line in insight.improvements)
        return lines

    def refresh_project_list(self) -> None:
        criteria = self._project_filter_criteria()
        filtered_projects = self.project_filter_service.filter(self.projects, criteria)
        current_path = str(self.current_project.path) if self.current_project else ""
        self.project_list.blockSignals(True)
        self.project_list.clear()
        for project in filtered_projects:
            item = QListWidgetItem(self._project_display_name(project))
            item.setData(Qt.UserRole, str(project.path))
            item.setToolTip(self._project_tooltip(project))
            self.project_list.addItem(item)
            if current_path and str(project.path) == current_path:
                item.setSelected(True)
        self.project_list.blockSignals(False)
        self.project_count_label.setText(f"表示中: {len(filtered_projects)}件 / 全{len(self.projects)}件")

    def _project_filter_criteria(self) -> ProjectFilterCriteria:
        return ProjectFilterCriteria(
            keyword=self.project_search.text(),
            genre=self.genre_filter.currentText(),
            category=self.category_filter.currentData() or self.category_filter.currentText(),
            series=self.series_filter.currentText(),
            tag=self.tag_filter.text(),
            posted_status=self.posted_filter.currentText(),
            progress_status=self.progress_filter.currentText(),
            min_rating=self.project_rating_filter.currentIndex(),
            min_views=self.project_min_views_filter.value(),
        )

    def reset_project_filters(self) -> None:
        self.project_search.clear()
        self.tag_filter.clear()
        self.project_min_views_filter.setValue(0)
        self.project_rating_filter.setCurrentIndex(0)
        self.posted_filter.setCurrentIndex(0)
        self.progress_filter.setCurrentIndex(0)
        self.genre_filter.setCurrentIndex(0)
        self.refresh_project_category_filter()
        self.refresh_project_series_filter()
        self.refresh_project_list()

    def on_project_filter_genre_changed(self) -> None:
        self.refresh_project_category_filter()
        self.refresh_project_series_filter()
        self.refresh_project_list()

    def on_project_filter_category_changed(self) -> None:
        self.refresh_project_series_filter()
        self.refresh_project_list()

    def refresh_project_category_filter(self) -> None:
        if not hasattr(self, "category_filter"):
            return
        current = self.category_filter.currentData() or self.category_filter.currentText()
        genre = self.genre_filter.currentText() if hasattr(self, "genre_filter") else ""
        counts = self.project_filter_service.category_counts(self.projects, "" if genre == "すべてのジャンル" else genre)
        categories = sorted(counts)
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("すべてのカテゴリ", "")
        if genre and genre != "すべてのジャンル":
            for category in self.categories_by_genre.get(genre, []):
                label = f"{category}（{counts.get(category, 0)}）"
                self.category_filter.addItem(label, category)
        else:
            for category in categories:
                self.category_filter.addItem(f"{category}（{counts.get(category, 0)}）", category)
        if self.category_filter.findData(current) >= 0:
            self.category_filter.setCurrentIndex(self.category_filter.findData(current))
        self.category_filter.blockSignals(False)

    def refresh_project_series_filter(self) -> None:
        if not hasattr(self, "series_filter"):
            return
        current = self.series_filter.currentText()
        genre = self.genre_filter.currentText()
        category = self.category_filter.currentData() or self.category_filter.currentText()
        values = self.project_filter_service.series_values(self.projects, genre, category)
        self.series_filter.blockSignals(True)
        self.series_filter.clear()
        self.series_filter.addItem("すべてのシリーズ")
        self.series_filter.addItems(values)
        if current in values:
            self.series_filter.setCurrentText(current)
        self.series_filter.blockSignals(False)

    def refresh_compilation_genres(self) -> None:
        if not hasattr(self, "compilation_genre_box"):
            return
        self.categories_by_genre = self.category_service.load()
        self.projects = self.project_service.list_projects()
        current = self.compilation_genre_box.currentText()
        genres = sorted(
            {
                project.genre
                for project in self.projects
                if project.genre and (project.path / "video" / "final.mp4").exists()
            }
        )
        self.compilation_genre_box.blockSignals(True)
        self.compilation_genre_box.clear()
        self.compilation_genre_box.addItems(genres)
        if current in genres:
            self.compilation_genre_box.setCurrentText(current)
        self.compilation_genre_box.blockSignals(False)
        self.refresh_compilation_categories()
        self.refresh_compilation_project_list()

    def on_compilation_genre_changed(self) -> None:
        self.refresh_compilation_categories()
        self.refresh_compilation_project_list()

    def refresh_compilation_categories(self) -> None:
        if not hasattr(self, "compilation_category_box"):
            return
        current = self.compilation_category_box.currentData() or self.compilation_category_box.currentText()
        genre = self.compilation_genre_box.currentText() if hasattr(self, "compilation_genre_box") else ""
        categories = set(self.categories_by_genre.get(genre, []))
        categories.update(
            project.category or UNCATEGORIZED
            for project in self.projects
            if project.genre == genre
        )
        self.compilation_category_box.blockSignals(True)
        self.compilation_category_box.clear()
        self.compilation_category_box.addItem("すべてのカテゴリ", "")
        for category in sorted(categories):
            self.compilation_category_box.addItem(category, category)
        if self.compilation_category_box.findData(current) >= 0:
            self.compilation_category_box.setCurrentIndex(self.compilation_category_box.findData(current))
        self.compilation_category_box.blockSignals(False)

    def refresh_compilation_project_list(self) -> None:
        if not hasattr(self, "compilation_project_list"):
            return
        genre = self.compilation_genre_box.currentText()
        category = self.compilation_category_box.currentData() if hasattr(self, "compilation_category_box") else ""
        projects = self._compilation_projects(genre, category)
        self.compilation_project_list.clear()
        total_duration = 0.0
        for project in projects:
            video_path = project.path / "video" / "final.mp4"
            total_duration += self.compilation_service.media_duration(video_path) or self._duration_seconds(project.duration)
            series_label = f"{project.series}{project.series_number:03d}" if project.series else project.name
            category_label = project.category or UNCATEGORIZED
            label = f"{series_label}  {project.title or project.topic or project.name}  [{category_label}]"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, str(project.path))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.compilation_project_list.addItem(item)
        self.compilation_summary_label.setText(
            f"ジャンル: {genre or '-'} / カテゴリ: {category or 'すべて'} / 動画本数: {len(projects)} / 総時間: {self.compilation_service.format_timestamp(total_duration)}"
        )

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
        self._suspend_project_classification_save = True
        try:
            self.topic_input.setText(self.current_project.topic)
            self.duration_box.setCurrentText(self.current_project.duration or self.settings.default_duration)
            self.genre_box.setCurrentText(self.current_project.genre)
            self.refresh_form_categories()
            self.category_box.setCurrentText(self.current_project.category)
            self.series_input.setText(self.current_project.series)
            self._set_image_count(self.current_project.image_count)
            self.template_box.setCurrentText(self.current_project.template_name)
        finally:
            self._suspend_project_classification_save = False
        self._load_project_texts(self.current_project.path)
        self._load_platform_tag_fields()
        self.update_progress_view()
        self.update_asset_list()
        self.update_image_prompt_list()
        self.update_video_preview()
        self.refresh_project_analytics_view()
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
            self.refresh_form_categories()

    def on_wizard_genre_changed(self) -> None:
        self.refresh_form_categories()
        self.save_current_project_classification()

    def refresh_form_categories(self) -> None:
        if not hasattr(self, "category_box"):
            return
        current = self.category_box.currentText()
        genre = self.genre_box.currentText()
        categories = self.categories_by_genre.get(genre, [])
        self.category_box.blockSignals(True)
        self.category_box.clear()
        self.category_box.addItem("")
        self.category_box.addItems(categories)
        if current and self.category_box.findText(current) < 0:
            self.category_box.addItem(current)
        if current:
            self.category_box.setCurrentText(current)
        self.category_box.blockSignals(False)
        if hasattr(self, "bulk_category_box"):
            bulk_current = self.bulk_category_box.currentText()
            self.bulk_category_box.clear()
            self.bulk_category_box.addItem("")
            self.bulk_category_box.addItems(categories)
            if bulk_current and self.bulk_category_box.findText(bulk_current) < 0:
                self.bulk_category_box.addItem(bulk_current)
            if bulk_current:
                self.bulk_category_box.setCurrentText(bulk_current)

    def save_current_project_classification(self) -> None:
        if self._suspend_project_classification_save or not self.current_project:
            return
        genre = self.genre_box.currentText().strip()
        category = self.category_box.currentText().strip()
        series = self.series_input.text().strip()
        if (
            genre == self.current_project.genre
            and category == self.current_project.category
            and series == self.current_project.series
        ):
            return
        self.ensure_category_registered(genre, category)
        try:
            updated = self.project_service.update_project_classification(
                self.current_project,
                genre=genre,
                category=category,
                series=series,
            )
        except OSError as exc:
            QMessageBox.critical(self, "保存エラー", f"カテゴリ情報の保存に失敗しました。\n{exc}")
            return
        self.current_project = updated
        for index, project in enumerate(self.projects):
            if project.path == updated.path:
                self.projects[index] = updated
                break
        self.refresh_project_category_filter()
        self.refresh_project_series_filter()
        self.refresh_project_list()
        self.refresh_dashboard()

    def refresh_category_manage_list(self) -> None:
        if not hasattr(self, "category_manage_list"):
            return
        genre = self.category_manage_genre_box.currentText()
        self.category_manage_list.clear()
        for category in self.categories_by_genre.get(genre, []):
            self.category_manage_list.addItem(category)

    def add_category(self) -> None:
        genre = self.category_manage_genre_box.currentText() or self.genre_box.currentText()
        category, ok = QInputDialog.getText(self, "カテゴリ追加", f"{genre} に追加するカテゴリ")
        if not ok or not category.strip():
            return
        self.categories_by_genre = self.category_service.add_category(genre, category, self.categories_by_genre)
        self.category_service.save(self.categories_by_genre)
        self.refresh_category_ui()

    def edit_category(self) -> None:
        selected = self.category_manage_list.currentItem()
        if selected is None:
            QMessageBox.warning(self, "カテゴリ管理", "編集するカテゴリを選択してください。")
            return
        genre = self.category_manage_genre_box.currentText()
        old_category = selected.text()
        new_category, ok = QInputDialog.getText(self, "カテゴリ編集", "新しいカテゴリ名", text=old_category)
        if not ok or not new_category.strip():
            return
        self.categories_by_genre = self.category_service.rename_category(genre, old_category, new_category, self.categories_by_genre)
        self.category_service.save(self.categories_by_genre)
        self.refresh_category_ui()

    def delete_category(self) -> None:
        selected = self.category_manage_list.currentItem()
        if selected is None:
            QMessageBox.warning(self, "カテゴリ管理", "削除するカテゴリを選択してください。")
            return
        genre = self.category_manage_genre_box.currentText()
        category = selected.text()
        if self.category_service.is_category_used(self.projects, genre, category):
            QMessageBox.warning(self, "カテゴリ管理", "このカテゴリを使用中のプロジェクトがあります。先にプロジェクト側のカテゴリを変更してください。")
            return
        if QMessageBox.question(self, "カテゴリ削除", f"{category} をカテゴリ一覧から削除しますか？") != QMessageBox.Yes:
            return
        self.categories_by_genre = self.category_service.delete_category(genre, category, self.categories_by_genre)
        self.category_service.save(self.categories_by_genre)
        self.refresh_category_ui()

    def move_category(self, direction: int) -> None:
        selected = self.category_manage_list.currentItem()
        if selected is None:
            return
        genre = self.category_manage_genre_box.currentText()
        category = selected.text()
        self.categories_by_genre = self.category_service.move_category(genre, category, direction, self.categories_by_genre)
        self.category_service.save(self.categories_by_genre)
        self.refresh_category_ui()
        matching = self.category_manage_list.findItems(category, Qt.MatchExactly)
        if matching:
            self.category_manage_list.setCurrentItem(matching[0])

    def refresh_category_ui(self) -> None:
        self.refresh_form_categories()
        self.refresh_category_manage_list()
        self.refresh_project_category_filter()
        self.refresh_project_list()

    def current_template(self) -> PromptTemplate | None:
        name = self.template_box.currentText()
        return next((template for template in self.templates if template.name == name), None)

    def generate_prompt(self) -> None:
        values = self._read_form_values()
        if values is None:
            return
        topic, duration, genre, _category, _series, image_count, _tags = values
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
        topic, duration, genre, category, series, image_count, tags = values
        prompt = self.prompt_text.toPlainText().strip() or build_chatgpt_prompt(topic, duration, genre, image_count, self.current_template())
        self.prompt_text.setPlainText(prompt)
        self.ensure_category_registered(genre, category)
        try:
            self.current_project = self.project_service.create_project(topic, genre, duration, image_count, prompt, self.template_box.currentText(), tags, series or topic, category)
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
        category = self.bulk_category_box.currentText().strip() or self.category_box.currentText().strip()
        series = self.bulk_series_input.text().strip()
        image_count = int(self.image_count_box.currentText())
        template = self.current_template()
        tags = self._parse_tags()
        self.ensure_category_registered(genre, category)

        def make_prompt(topic: str) -> str:
            return build_chatgpt_prompt(topic, duration, genre, image_count, template)

        try:
            created = self.project_service.create_projects_from_topics(topics, genre, category, duration, image_count, self.template_box.currentText(), make_prompt, tags if tags else [],)
            if series:
                created = [self.project_service.update_project_classification(project, series=series) for project in created]
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

    def create_compilation_video(self) -> None:
        selected_projects = self._selected_compilation_projects()
        if not selected_projects:
            QMessageBox.warning(self, "総集編作成エラー", "総集編に使う動画を選択してください。")
            return
        intro_path = self.compilation_service.first_asset(self.paths.intro_dir) if self.settings.intro_enabled else None
        ending_path = self.compilation_service.first_asset(self.paths.ending_dir) if self.settings.ending_enabled else None
        bgm_path = None
        if self.paths.bgm_dir.exists():
            bgm_path = next(
                (
                    path
                    for path in sorted(self.paths.bgm_dir.iterdir())
                    if path.is_file() and path.suffix.lower() in {".mp3", ".wav"}
                ),
                None,
            )
        result = self.compilation_service.create_series_compilation(
            selected_projects,
            self.paths.exports_dir / "series",
            intro_path=intro_path,
            ending_path=ending_path,
            output_name=self._compilation_output_name(),
            intro_options=BrandingSegmentOptions(
                duration=self.settings.intro_duration_seconds,
                motion=self.settings.intro_motion,
                audio_mode=self.settings.intro_audio_mode,
                bgm_volume=self.settings.intro_bgm_volume_percent / 100,
            ),
            ending_options=BrandingSegmentOptions(
                duration=self.settings.ending_duration_seconds,
                motion=self.settings.ending_motion,
                audio_mode=self.settings.ending_audio_mode,
                bgm_volume=self.settings.ending_bgm_volume_percent / 100,
            ),
            bgm_path=bgm_path,
        )
        if not result.success:
            QMessageBox.warning(self, "総集編作成エラー", result.message)
            return
        self.status_label.setText(result.message)
        QMessageBox.information(self, "総集編作成", f"総集編を作成しました。\n{result.output_path}")

    def _selected_compilation_projects(self) -> list[ProjectInfo]:
        selected_paths: list[str] = []
        for index in range(self.compilation_project_list.count()):
            item = self.compilation_project_list.item(index)
            if item.checkState() == Qt.Checked:
                selected_paths.append(str(item.data(Qt.UserRole)))
        projects_by_path = {str(project.path): project for project in self.projects}
        return [projects_by_path[path] for path in selected_paths if path in projects_by_path]

    def move_compilation_item(self, direction: int) -> None:
        current_row = self.compilation_project_list.currentRow()
        if current_row < 0:
            return
        next_row = current_row + direction
        if next_row < 0 or next_row >= self.compilation_project_list.count():
            return
        item = self.compilation_project_list.takeItem(current_row)
        self.compilation_project_list.insertItem(next_row, item)
        self.compilation_project_list.setCurrentRow(next_row)

    def _compilation_output_name(self) -> str | None:
        genre = self.compilation_genre_box.currentText().strip()
        category = ""
        if hasattr(self, "compilation_category_box"):
            category = str(self.compilation_category_box.currentData() or "").strip()
        if genre and category:
            return f"{genre}_{category}"
        return genre or None

    def _compilation_projects(self, genre: str, category: str = "") -> list[ProjectInfo]:
        return sorted(
            [
                project
                for project in self.projects
                if project.genre == genre
                and (not category or (project.category or UNCATEGORIZED) == category)
                and (project.path / "video" / "final.mp4").exists()
            ],
            key=lambda project: (project.series, project.series_number, project.name),
        )

    def _duration_seconds(self, duration: str) -> float:
        match = re.search(r"\d+", duration or "")
        if not match:
            return 60.0
        value = float(match.group())
        if "分" in duration:
            return value * 60.0
        return value

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
        images = self.image_import_service.list_images(self.current_project.path)
        motions = self.video_render_service._determine_image_motions(self.current_project, len(images), self.settings.motion_style)
        for index, image_path in enumerate(images):
            motion = motions[index] if index < len(motions) else self.settings.motion_style
            self.image_thumbnail_layout.insertWidget(
                self.image_thumbnail_layout.count() - 1,
                self._image_thumbnail_row(image_path, motion),
            )

    def _image_thumbnail_row(self, image_path: Path, motion: str = "") -> QWidget:
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

        name_label = QLabel(f"{image_path.name}\n{motion or 'Static'}")
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
        self.compilation_service = CompilationService(self.settings.ffmpeg_path, self.settings.output_width, self.settings.output_height)
        QMessageBox.information(self, "設定保存", "設定を保存しました。")
        self.apply_settings_to_ui()

    def _read_form_values(self) -> tuple[str, str, str, str, str, int, list[str]] | None:
        topic = self.topic_input.text().strip()
        if not topic:
            QMessageBox.warning(self, "入力エラー", "テーマを入力してください。")
            return None
        return (
            topic,
            self.duration_box.currentText(),
            self.genre_box.currentText(),
            self.category_box.currentText().strip(),
            self.series_input.text().strip(),
            int(self.image_count_box.currentText()),
            self._parse_tags(),
        )

    def ensure_category_registered(self, genre: str, category: str) -> None:
        if not genre.strip() or not category.strip():
            return
        if category in self.categories_by_genre.get(genre, []):
            return
        if QMessageBox.question(self, "カテゴリ追加", f"「{category}」を「{genre}」のカテゴリ一覧へ追加しますか？") == QMessageBox.Yes:
            self.categories_by_genre = self.category_service.add_category(genre, category, self.categories_by_genre)
            self.category_service.save(self.categories_by_genre)
            self.refresh_category_ui()

    def bulk_update_selected_projects(self) -> None:
        selected_paths = [Path(item.data(Qt.UserRole)) for item in self.project_list.selectedItems()]
        if not selected_paths:
            QMessageBox.warning(self, "一括変更", "変更するプロジェクトを選択してください。")
            return
        selected_projects = [project for project in self.projects if project.path in selected_paths]
        genre = self.category_manage_genre_box.currentText() or self.genre_box.currentText()
        selected_category = self.category_manage_list.currentItem()
        category = selected_category.text() if selected_category else self.category_box.currentText().strip()
        series, ok = QInputDialog.getText(self, "一括カテゴリ変更", "シリーズ名（空欄なら変更しません）")
        if not ok:
            return
        tag_text, ok = QInputDialog.getText(self, "一括タグ変更", "追加タグ（カンマ区切り、空欄可）")
        if not ok:
            return
        remove_tag_text, ok = QInputDialog.getText(self, "一括タグ削除", "削除タグ（カンマ区切り、空欄可）")
        if not ok:
            return
        if QMessageBox.question(self, "一括変更", f"{len(selected_projects)}件のジャンル/カテゴリ/シリーズ/タグを変更しますか？") != QMessageBox.Yes:
            return
        add_tags = self.tag_service.parse_youtube_text(tag_text)
        remove_tags = self.tag_service.parse_youtube_text(remove_tag_text)
        self.project_service.bulk_update_classification(
            selected_projects,
            genre=genre,
            category=category,
            series=series.strip(),
            add_tags=add_tags,
            remove_tags=remove_tags,
        )
        self.reload_projects()
        self.status_label.setText(f"{len(selected_projects)}件のカテゴリ情報を一括変更しました。")

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
        category = project.category or UNCATEGORIZED
        return f"{title}  [{done_count}/{len(PROGRESS_ITEMS)}]\n{project.genre or '未設定'} > {category}\n{series}{tags}"

    def _project_tooltip(self, project: ProjectInfo) -> str:
        tags = ", ".join(project.tags) if project.tags else "-"
        return "\n".join(
            [
                project.title or project.topic or project.name,
                f"ジャンル: {project.genre or '-'}",
                f"カテゴリ: {project.category or UNCATEGORIZED}",
                f"シリーズ: {project.series or '-'} #{project.series_number:03d}",
                f"タグ: {tags}",
                f"再生数: {project.analytics_views:,}",
            ]
        )

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""
