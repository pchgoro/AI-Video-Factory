from __future__ import annotations

import webbrowser
import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QStringListModel, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
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
from services.parser import ChatGptAnswerParser, ChatGptParseError
from services.project_service import ProjectService
from services.prompt_builder import build_chatgpt_prompt
from services.settings_service import SettingsService
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
QSplitter::handle { background: #333333; }
"""


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

    def _build_ui(self) -> None:
        root = QSplitter(Qt.Horizontal)
        root.addWidget(self._build_left_panel())
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
        layout.addWidget(self.project_list, stretch=2)

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
        layout.addWidget(topic_box, stretch=1)
        return panel

    def _build_main_tabs(self) -> QTabWidget:
        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(self._build_dashboard_tab(), "ホーム")
        self.main_tabs.addTab(self._build_wizard_tab(), "制作ウィザード")
        return self.main_tabs

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
        layout.addWidget(self._build_form_box())

        action_row = QHBoxLayout()
        buttons = [
            ("ChatGPTを開く", self.open_chatgpt),
            ("プロンプト生成", self.generate_prompt),
            ("プロンプトをコピー", self.copy_prompt),
            ("プロジェクト作成", self.create_project),
            ("VOICEVOX音声生成", self.generate_voice),
            ("FFmpeg動画生成", self.render_video),
            ("投稿", self.not_implemented),
        ]
        for label, handler in buttons:
            button = QPushButton(label)
            button.clicked.connect(handler)
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
        self.image_count_box = QSpinBox()
        self.image_count_box.setRange(3, 8)
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("例: 宇宙, 初心者向け, 90秒, TikTok")

        form.addWidget(QLabel("テーマ"), 0, 0)
        form.addWidget(self.topic_input, 0, 1, 1, 5)
        form.addWidget(QLabel("テンプレート"), 1, 0)
        form.addWidget(self.template_box, 1, 1)
        form.addWidget(QLabel("動画時間"), 1, 2)
        form.addWidget(self.duration_box, 1, 3)
        form.addWidget(QLabel("画像枚数"), 1, 4)
        form.addWidget(self.image_count_box, 1, 5)
        form.addWidget(QLabel("ジャンル"), 2, 0)
        form.addWidget(self.genre_box, 2, 1)
        form.addWidget(QLabel("タグ"), 2, 2)
        form.addWidget(self.tags_input, 2, 3, 1, 2)
        save_tags_button = QPushButton("タグ保存")
        save_tags_button.clicked.connect(self.save_current_tags)
        form.addWidget(save_tags_button, 2, 5)
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

    def _build_assets_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.asset_list = QListWidget()
        self.asset_list.itemDoubleClicked.connect(self.open_asset_folder)
        layout.addWidget(self.asset_list)
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

    def apply_settings_to_ui(self) -> None:
        self.duration_box.setCurrentText(self.settings.default_duration)
        self.image_count_box.setValue(self.settings.default_image_count)
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
        self.image_count_box.setValue(self.current_project.image_count)
        self.template_box.setCurrentText(self.current_project.template_name)
        self.tags_input.setText(", ".join(self.current_project.tags))
        self._load_project_texts(self.current_project.path)
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
        image_count = self.image_count_box.value()
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

    def save_current_tags(self) -> None:
        if self.current_project is None:
            QMessageBox.warning(self, "タグ保存エラー", "先にプロジェクトを作成または選択してください。")
            return
        self.current_project = self.project_service.save_tags(self.current_project, self._parse_tags())
        self.reload_projects()
        self.status_label.setText("タグを保存しました。")

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

    def _wizard_states(self) -> list[bool]:
        progress = self.current_project.progress if self.current_project else {}
        return [
            bool(self.topic_input.text().strip()),
            bool(self.prompt_text.toPlainText().strip()),
            bool(progress.get("台本")),
            bool(progress.get("画像")),
            bool(progress.get("音声")),
            bool(progress.get("字幕")),
            bool(progress.get("動画")),
            bool(progress.get("投稿")),
        ]

    def update_asset_list(self) -> None:
        self.asset_list.clear()
        if self.current_project is None:
            return
        for label, status, path in self.project_service.asset_statuses(self.current_project):
            item = QListWidgetItem(f"{label}    {status}")
            item.setData(Qt.UserRole, str(path))
            self.asset_list.addItem(item)

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
        return topic, self.duration_box.currentText(), self.genre_box.currentText(), self.image_count_box.value(), self._parse_tags()

    def _parse_tags(self) -> list[str]:
        raw = self.tags_input.text().replace("、", ",")
        return [tag.strip() for tag in raw.split(",") if tag.strip()]

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
