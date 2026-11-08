from __future__ import annotations

import copy
import math
import sys
import traceback
import wave
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QIcon, QPainter, QPen, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QAbstractSpinBox, QButtonGroup, QCheckBox, QColorDialog, QComboBox,
    QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSpinBox, QTabWidget, QTextEdit, QToolButton, QVBoxLayout, QWidget,
    QInputDialog, QProgressBar,
)

from .audio import convert_to_reference, read_waveform, wav_info
from .config import DEFAULT_WHISPER_MODEL, LANGUAGES, MODEL_CHOICES, PAGE_SIZE, VAD_DEFAULTS, WHISPER_DEFAULTS, build_model_choices
from .exporter import export_project
from .models import list_cached_models
from .project import (
    active_chunks, create_chunk, create_project, list_projects, move_project_to_trash,
    open_project, save_project, snapshot_chunks, undo_last,
)
from .transcribe import transcribe_reference
from .utils import default_project_dir, has_invalid_component_characters, new_id, parse_inf_float, sanitize_component, sanitize_component_raw


TEXT = {
    "English": {
        "title": "Speech Extractor", "project_tab": "Transcription", "transcription_settings": "Transcription settings", "proof_tab": "Proofreading",
        "export_tab": "Export", "project_folder": "Project folder", "browse": "Browse…",
        "project_name": "Project name", "source_file": "Source media (audio / video)",
        "channels": "Reference WAV", "stereo": "Stereo (default)", "mono": "Mono",
        "whisper_model": "Whisper model", "refresh_models": "Refresh models", "device": "Device",
        "vad": "Silero VAD", "vad_default": "Use faster-whisper defaults", "threshold": "threshold (0–1)",
        "min_speech": "min_speech_duration_ms", "max_speech": "max_speech_duration_s",
        "min_silence": "min_silence_duration_ms", "speech_pad": "speech_pad_ms",
        "whisper_options": "Whisper decoding options", "whisper_default": "Use faster-whisper defaults",
        "beam_size": "beam_size", "temperature": "temperature (0–1)",
        "condition_previous": "condition_on_previous_text",
        "compression_ratio": "compression_ratio_threshold", "log_prob": "log_prob_threshold",
        "no_speech": "no_speech_threshold (0–1)",
        "start": "START", "new_project": "New project", "load_project": "Load existing project", "refresh_projects": "Refresh",
        "load": "Load", "delete": "Delete project", "log": "Log", "save": "Save project",
        "page_prev": "← Previous", "page_next": "Next →", "all_reviewed": "Mark all fragments on this page reviewed",
        "to_review": "To be reviewed", "total": "Total active fragments", "play": "Play range", "stop": "Stop",
        "split": "Split", "split_shortcut": "Split (S)", "merge_next": "Merge with next", "delete_fragment": "Delete", "undo": "Undo",
        "start_time": "Start (s)", "end_time": "End (s)", "original": "Original (read-only)",
        "corrected": "Corrected text", "speaker": "Tag", "reviewed": "Reviewed", "speaker_tags": "Tag management",
        "speaker_name": "New tag (1–32 chars)", "add_speaker": "Add tag", "default_speaker": "Default tag",
        "merge_playhead": "Merge at playhead", "rename_tag": "Rename", "delete_tag": "Delete", "color_tag": "Change color", "tag_up": "Move up", "tag_down": "Move down",
        "export_dir": "Export directory", "numbered": "Prefix WAV names with sequence number", "zip": "Create ZIP archive",
        "export": "Export", "open_export": "Open export folder", "choose_source": "Select source media",
        "choose_folder": "Select folder", "confirm_delete": "Move this entire project to the system trash?",
        "confirm_replace_export": "The export folder already exists. Move the entire folder to the system trash and create a fresh one?",
        "yes": "Yes", "no": "No", "project_loaded": "Project loaded", "saved": "Project saved.",
        "audio_failed": "Audio conversion failed. The incomplete project will be moved to Trash.",
        "transcription_failed": "Transcription failed. The project and reference.wav have been kept so you can retry.",
        "export_done": "Export completed.", "empty_speaker": "(None)", "page": "Page",
        "filename_warning": "Filename is longer than 100 characters and will be truncated on export.",
    },
    "한국어": {
        "title": "음원 소스 추출기", "project_tab": "전사", "transcription_settings": "전사 설정", "proof_tab": "교정", "export_tab": "내보내기",
        "project_folder": "프로젝트 저장 폴더", "browse": "찾아보기…", "project_name": "프로젝트명",
        "source_file": "원본 미디어 (음원 / 영상)", "channels": "참조 WAV", "stereo": "스테레오 (기본값)",
        "mono": "모노", "whisper_model": "Whisper 모델", "refresh_models": "모델 새로고침", "device": "장치",
        "vad": "Silero VAD", "vad_default": "faster-whisper 기본값 사용", "threshold": "threshold (0–1)",
        "min_speech": "min_speech_duration_ms", "max_speech": "max_speech_duration_s", "min_silence": "min_silence_duration_ms",
        "speech_pad": "speech_pad_ms",
        "whisper_options": "Whisper 디코딩 옵션", "whisper_default": "faster-whisper 기본값 사용",
        "beam_size": "beam_size", "temperature": "temperature (0–1)",
        "condition_previous": "condition_on_previous_text",
        "compression_ratio": "compression_ratio_threshold", "log_prob": "log_prob_threshold",
        "no_speech": "no_speech_threshold (0–1)", "new_project": "새 프로젝트", "start": "시작", "load_project": "기존 프로젝트 불러오기", "refresh_projects": "새로고침",
        "load": "불러오기", "delete": "프로젝트 삭제", "log": "로그", "save": "프로젝트 저장",
        "page_prev": "← 이전", "page_next": "다음 →", "all_reviewed": "현재 페이지의 모든 fragment를 확인 완료로 표시",
        "to_review": "검수 필요", "total": "활성 fragment", "play": "구간 재생", "stop": "정지",
        "split": "분할", "split_shortcut": "분할 (S)", "merge_next": "다음 구간과 병합", "delete_fragment": "삭제", "undo": "실행 취소", "start_time": "시작 (초)",
        "end_time": "종료 (초)", "original": "초벌 전사 (읽기 전용)", "corrected": "교정 텍스트", "speaker": "태그",
        "reviewed": "검수 완료", "speaker_tags": "태그 관리", "speaker_name": "새 태그 (1–32자)",
        "add_speaker": "태그 추가", "default_speaker": "기본 태그", "merge_playhead": "재생 위치에서 병합", "rename_tag": "이름 변경", "delete_tag": "삭제", "color_tag": "색상 변경", "tag_up": "위로", "tag_down": "아래로", "export_dir": "내보내기 폴더",
        "numbered": "WAV 파일명 앞에 순번 붙이기", "zip": "ZIP 압축 파일 만들기", "export": "내보내기",
        "open_export": "내보내기 폴더 열기", "choose_source": "원본 미디어 선택", "choose_folder": "폴더 선택",
        "confirm_delete": "프로젝트 전체를 시스템 휴지통으로 이동할까요?",
        "confirm_replace_export": "내보내기 폴더가 이미 있습니다. 폴더 전체를 휴지통으로 이동하고 새 폴더를 만들까요?", "yes": "예", "no": "아니오",
        "project_loaded": "프로젝트를 불러왔습니다", "saved": "프로젝트를 저장했습니다.",
        "audio_failed": "음원 변환에 실패했습니다. 불완전한 프로젝트를 휴지통으로 이동합니다.",
        "transcription_failed": "전사에 실패했습니다. reference.wav와 프로젝트는 유지했으므로 다시 시도할 수 있습니다.",
        "export_done": "내보내기가 완료되었습니다.", "empty_speaker": "(없음)", "page": "페이지",
        "filename_warning": "100자를 초과하여 내보내기 시 파일명이 잘립니다.",
    },
    "日本語": {
        "title": "音声切り出しツール", "project_tab": "文字起こし", "transcription_settings": "文字起こし設定", "proof_tab": "校正", "export_tab": "書き出し",
        "project_folder": "プロジェクト保存先", "browse": "参照…", "project_name": "プロジェクト名",
        "source_file": "ソースメディア（音声 / 動画）", "channels": "参照 WAV", "stereo": "ステレオ（標準）",
        "mono": "モノラル", "whisper_model": "Whisper モデル", "refresh_models": "モデルを更新", "device": "デバイス",
        "vad": "Silero VAD", "vad_default": "faster-whisper の既定値を使用", "threshold": "threshold (0–1)",
        "min_speech": "min_speech_duration_ms", "max_speech": "max_speech_duration_s", "min_silence": "min_silence_duration_ms",
        "speech_pad": "speech_pad_ms",
        "whisper_options": "Whisper デコード設定", "whisper_default": "faster-whisper の既定値を使用",
        "beam_size": "beam_size", "temperature": "temperature (0–1)",
        "condition_previous": "condition_on_previous_text",
        "compression_ratio": "compression_ratio_threshold", "log_prob": "log_prob_threshold",
        "no_speech": "no_speech_threshold (0–1)", "new_project": "新規プロジェクト", "start": "開始", "load_project": "既存プロジェクトを開く", "refresh_projects": "更新",
        "load": "開く", "delete": "プロジェクト削除", "log": "ログ", "save": "保存", "page_prev": "← 前へ",
        "page_next": "次へ →", "all_reviewed": "このページのすべての断片を確認済みにする", "to_review": "要確認",
        "total": "有効な断片数", "play": "範囲を再生", "stop": "停止", "split": "分割", "split_shortcut": "分割 (S)", "merge_next": "次と結合",
        "delete_fragment": "削除", "undo": "元に戻す", "start_time": "開始 (秒)", "end_time": "終了 (秒)",
        "original": "元の文字起こし（編集不可）", "corrected": "修正テキスト", "speaker": "タグ", "reviewed": "確認済み",
        "speaker_tags": "タグ管理", "speaker_name": "新しいタグ (1～32文字)", "add_speaker": "タグを追加",
        "default_speaker": "既定タグ", "merge_playhead": "再生位置で結合", "rename_tag": "名前を変更", "delete_tag": "削除", "color_tag": "色を変更", "tag_up": "上へ", "tag_down": "下へ", "export_dir": "書き出し先", "numbered": "WAV 名に連番を付ける",
        "zip": "ZIP アーカイブを作成", "export": "書き出し", "open_export": "書き出し先を開く",
        "choose_source": "ソースメディアを選択", "choose_folder": "フォルダーを選択",
        "confirm_delete": "プロジェクト全体をシステムのゴミ箱に移動しますか？",
        "confirm_replace_export": "書き出しフォルダーは既に存在します。フォルダー全体をゴミ箱に移動して新しく作成しますか？", "yes": "はい", "no": "いいえ",
        "project_loaded": "プロジェクトを読み込みました", "saved": "プロジェクトを保存しました。",
        "audio_failed": "音声変換に失敗しました。未完成のプロジェクトをゴミ箱に移動します。",
        "transcription_failed": "文字起こしに失敗しました。reference.wav とプロジェクトは保持されます。",
        "export_done": "書き出しが完了しました。", "empty_speaker": "（なし）", "page": "ページ",
        "filename_warning": "100文字を超えているため、書き出し時にファイル名が短縮されます。",
    },
}


class WorkThread(QThread):
    progress = Signal(str)
    chunk_added = Signal(dict)
    succeeded = Signal(list, dict)
    failed = Signal(str, str)  # stage, traceback/message

    def __init__(self, source: Path, reference: Path, model_id: str,
                 vad_parameters: dict[str, Any] | None, whisper_parameters: dict[str, Any] | None,
                 device: str, convert: bool, channels: int):
        super().__init__()
        self.source = source
        self.reference = reference
        self.model_id = model_id
        self.vad_parameters = vad_parameters
        self.whisper_parameters = whisper_parameters
        self.device = device
        self.convert = convert
        self.channels = channels

    def run(self):
        if self.convert:
            try:
                self.progress.emit("Converting source media to 48 kHz PCM16 WAV…")
                convert_to_reference(self.source, self.reference, channels=self.channels,
                                     progress=self.progress.emit)
            except Exception:
                self.failed.emit("audio", traceback.format_exc())
                return
        try:
            self.progress.emit("Starting transcription (task=transcribe)…")
            chunks, metadata = transcribe_reference(
                self.reference, self.model_id, self.vad_parameters, self.device,
                progress=self.progress.emit,
                chunk_callback=self.chunk_added.emit,
                whisper_parameters=self.whisper_parameters,
            )
            self.succeeded.emit(chunks, metadata)
        except Exception:
            self.failed.emit("transcription", traceback.format_exc())


class WaveformWidget(QWidget):
    """Waveform with draggable start/end handles and a clickable playback cursor."""
    def __init__(self, wav_path: Path, start: float, end: float, duration: float,
                 on_seek, on_boundary, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(76)
        self.setMaximumHeight(76)
        self.setMouseTracking(True)
        self.wav_path = wav_path
        self.start = start
        self.end = end
        self.duration = duration
        self.on_seek = on_seek
        self.on_boundary = on_boundary
        self.window_start = 0.0
        self.window_end = 0.0
        self.minimum, self.maximum = [], []
        self.playhead = start
        self.drag_mode: str | None = None
        self.update_range(start, end)
        self.setToolTip("Click: seek · Shift+click: set start · Ctrl/Cmd+click: set end · Drag an edge marker")

    def update_bounds(self, start: float, end: float):
        """Update boundary markers without changing the visible time axis."""
        self.start = float(start)
        self.end = float(end)
        self.update()

    def update_range(self, start: float, end: float):
        self.update_bounds(start, end)
        self.window_start = max(0.0, self.start - 3.0)
        self.window_end = min(self.duration, self.end + 3.0)
        try:
            self.minimum, self.maximum = read_waveform(self.wav_path, self.window_start, self.window_end)
        except Exception:
            self.minimum, self.maximum = [], []
        self.update()

    def set_playhead(self, seconds: float):
        self.playhead = max(0.0, min(self.duration, float(seconds)))
        self.update()

    def _time_at_x(self, x: float) -> float:
        rect = self.rect().adjusted(5, 2, -5, -2)
        fraction = max(0.0, min(1.0, (x - rect.left()) / max(1, rect.width())))
        return self.window_start + fraction * max(0.0, self.window_end - self.window_start)

    def _x_at_time(self, seconds: float, rect) -> int:
        span = max(0.001, self.window_end - self.window_start)
        return rect.left() + int((seconds - self.window_start) / span * rect.width())

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        x = float(event.position().x())
        when = self._time_at_x(x)
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ShiftModifier:
            self.on_boundary("start", when)
        elif mods & Qt.KeyboardModifier.ControlModifier or mods & Qt.KeyboardModifier.MetaModifier:
            self.on_boundary("end", when)
        else:
            rect = self.rect().adjusted(5, 2, -5, -2)
            start_x = self._x_at_time(self.start, rect)
            end_x = self._x_at_time(self.end, rect)
            if abs(x - start_x) <= 10:
                self.drag_mode = "start"
            elif abs(x - end_x) <= 10:
                self.drag_mode = "end"
            else:
                self.on_seek(when)
        event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_mode:
            self.on_boundary(self.drag_mode, self._time_at_x(float(event.position().x())))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self.drag_mode is not None
            self.drag_mode = None
            if was_dragging:
                # Recenter only after the drag, keeping pointer-to-time mapping stable.
                self.update_range(self.start, self.end)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(5, 2, -5, -2)
        painter.fillRect(rect, QColor("#171b24"))
        mid = rect.center().y()
        painter.setPen(QPen(QColor("#515b6b"), 1))
        painter.drawLine(rect.left(), mid, rect.right(), mid)
        if len(self.minimum):
            painter.setPen(QPen(QColor("#63b3ed"), 1))
            count = len(self.minimum)
            width = max(1, rect.width())
            for i in range(min(count, width)):
                x = rect.left() + i
                idx = min(count - 1, int(i * count / width))
                y1 = mid - int(float(self.maximum[idx]) * (rect.height() * 0.40))
                y2 = mid - int(float(self.minimum[idx]) * (rect.height() * 0.40))
                painter.drawLine(x, y1, x, y2)
        for when, color in ((self.start, "#f6c453"), (self.end, "#f08a5d")):
            x = self._x_at_time(when, rect)
            painter.setPen(QPen(QColor(color), 2))
            painter.drawLine(x, rect.top(), x, rect.bottom())
        if self.window_start <= self.playhead <= self.window_end:
            x = self._x_at_time(self.playhead, rect)
            painter.setPen(QPen(QColor("#7ee787"), 2))
            painter.drawLine(x, rect.top(), x, rect.bottom())
        painter.setPen(QColor("#cbd5e1"))
        painter.drawText(rect.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignBottom,
                         f"{self.window_start:.2f}s   |   ▶ {self.playhead:.2f}s   |   {self.window_end:.2f}s")


class ReviewedTextEdit(QTextEdit):
    enterPressed = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.enterPressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


def _color_icon(color: str) -> QIcon:
    pixmap = QPixmap(14, 14)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(color).darker(125), 1))
    painter.setBrush(QColor(color))
    painter.drawEllipse(2, 2, 10, 10)
    painter.end()
    return QIcon(pixmap)


def split_text_at_fraction(text: str, fraction: float) -> tuple[str, str]:
    text = str(text or "")
    if not text:
        return "", ""
    fraction = min(0.99, max(0.01, fraction))
    words = text.split()
    if len(words) >= 2:
        cut = min(len(words) - 1, max(1, round(len(words) * fraction)))
        return " ".join(words[:cut]), " ".join(words[cut:])
    cut = min(len(text) - 1, max(1, round(len(text) * fraction))) if len(text) > 1 else 1
    return text[:cut].strip(), text[cut:].strip()


class FragmentCard(QFrame):
    def __init__(self, index: int, chunk: dict[str, Any], tags: dict[str, Any], default_tag: str,
                 wav_path: Path, duration: float, language_text: dict[str, str], callbacks: dict[str, Any]):
        super().__init__()
        self.chunk_id = chunk["id"]
        self.t = language_text
        self.cb = callbacks
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame { border: 1px solid #596273; border-radius: 6px; }")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(9, 7, 9, 7)
        outer.setSpacing(6)

        heading = QHBoxLayout()
        heading.addWidget(QLabel(f"#{index:04d}  ·  {str(chunk['id'])[:8]}"))
        heading.addStretch(1)
        self.reviewed = QCheckBox(self.t["reviewed"])
        self.reviewed.setChecked(bool(chunk.get("reviewed", False)))
        self.reviewed.stateChanged.connect(lambda state: self.cb["change"](self.chunk_id, "reviewed", state == Qt.CheckState.Checked.value))
        heading.addWidget(self.reviewed)
        outer.addLayout(heading)

        self.wave = WaveformWidget(
            wav_path, float(chunk["start"]), float(chunk["end"]), duration,
            on_seek=self.cb["seek"], on_boundary=self._set_boundary_from_wave,
        )
        outer.addWidget(self.wave)

        controls = QHBoxLayout()
        self.start_box = QDoubleSpinBox()
        self.start_box.setDecimals(3)
        self.start_box.setRange(0, max(0.001, duration))
        self.start_box.setSingleStep(0.05)
        self.start_box.setValue(float(chunk["start"]))
        self.end_box = QDoubleSpinBox()
        self.end_box.setDecimals(3)
        self.end_box.setRange(0, max(0.001, duration))
        self.end_box.setSingleStep(0.05)
        self.end_box.setValue(float(chunk["end"]))
        self.start_box.valueChanged.connect(lambda value: self.cb["change"](self.chunk_id, "start", value))
        self.end_box.valueChanged.connect(lambda value: self.cb["change"](self.chunk_id, "end", value))
        controls.addWidget(QLabel(self.t["start_time"]))
        controls.addWidget(self.start_box)
        controls.addWidget(QLabel(self.t["end_time"]))
        controls.addWidget(self.end_box)
        self.play_button = QPushButton(self.t["play"])
        self.play_button.clicked.connect(lambda: self.cb["play"](self.chunk_id))
        controls.addWidget(self.play_button)
        self.split_button = QPushButton(self.t["split"])
        self.split_button.setToolTip(self.t.get("split_shortcut", self.t["split"]))
        self.split_button.clicked.connect(lambda: self.cb["split"](self.chunk_id))
        controls.addWidget(self.split_button)
        self.merge_button = QPushButton(self.t["merge_next"])
        self.merge_button.setToolTip(f"{self.t['merge_next']} ({'⌘M' if sys.platform == 'darwin' else 'Ctrl+M'})")
        self.merge_button.clicked.connect(lambda: self.cb["merge"](self.chunk_id))
        controls.addWidget(self.merge_button)
        self.delete_button = QPushButton(self.t["delete_fragment"])
        self.delete_button.clicked.connect(lambda: self.cb["delete"](self.chunk_id))
        controls.addWidget(self.delete_button)
        outer.addLayout(controls)

        tag_wrap = QHBoxLayout()
        tag_wrap.setContentsMargins(0, 0, 0, 0)
        tag_wrap.setSpacing(5)
        tag_label = QLabel(self.t["speaker"] + ":")
        tag_label.setFixedWidth(42)
        tag_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        tag_wrap.addWidget(tag_label)
        self.tag_group = QButtonGroup(self)
        self.tag_group.setExclusive(True)
        self.tag_buttons: dict[str, QToolButton] = {}
        ordered = list(tags.items())
        ordered.sort(key=lambda item: item[0] != default_tag)
        none_choice = ("", {"color": "#7b8494"})
        choices = ordered + [none_choice] if default_tag in tags else [none_choice] + ordered
        current = str(chunk.get("speaker", "") or "")
        if current not in tags:
            current = ""
        for choice_index, (name, meta) in enumerate(choices):
            color = str((meta or {}).get("color", "#7b8494"))
            button = QToolButton()
            button.setText(self.t["empty_speaker"] if not name else name)
            button.setToolTip(self.t["empty_speaker"] if not name else name)
            button.setIcon(_color_icon(color))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setCheckable(True)
            button.setChecked(name == current)
            button.setStyleSheet(
                "QToolButton { border: 1px solid #687386; border-radius: 11px; padding: 3px 6px; }"
                "QToolButton:checked { background: #34445b; border: 2px solid #8ab4f8; }"
            )
            self.tag_group.addButton(button)
            self.tag_buttons[name] = button
            button.toggled.connect(lambda checked, tag=name: checked and self.cb["change"](self.chunk_id, "speaker", tag))
            tag_wrap.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
        tag_wrap.addStretch(1)
        outer.addLayout(tag_wrap)

        texts = QGridLayout()
        texts.addWidget(QLabel(self.t["original"]), 0, 0)
        original = QLabel(str(chunk.get("original_text", "")))
        original.setWordWrap(True)
        original.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        texts.addWidget(original, 0, 1)
        texts.addWidget(QLabel(self.t["corrected"]), 1, 0)
        self.corrected = ReviewedTextEdit()
        self.corrected.setPlainText(str(chunk.get("corrected_text", "")))
        self.corrected.setFixedHeight(58)
        self.length_warning = QLabel("⚠ " + self.t["filename_warning"])
        self.length_warning.setStyleSheet("color: #c47b00; font-size: 11px;")
        self.length_warning.setVisible(len(self.corrected.toPlainText()) > 100)
        self.corrected.textChanged.connect(self._corrected_changed)
        self.corrected.enterPressed.connect(lambda: self.cb["enter_next"](self.chunk_id))
        texts.addWidget(self.corrected, 1, 1)
        texts.addWidget(self.length_warning, 2, 1)
        outer.addLayout(texts)

    def _set_boundary_from_wave(self, key: str, value: float):
        if key == "start":
            self.start_box.setValue(max(0.0, min(float(value), self.end_box.value() - 0.01)))
        else:
            self.end_box.setValue(min(self.wave.duration, max(float(value), self.start_box.value() + 0.01)))

    def set_playhead(self, seconds: float):
        self.wave.set_playhead(seconds)

    def _corrected_changed(self):
        value = self.corrected.toPlainText()
        self.length_warning.setVisible(len(value) > 100)
        self.cb["change"](self.chunk_id, "corrected_text", value)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.language = "English"
        self.t = TEXT[self.language]
        self.project_dir: Path | None = None
        self.data: dict[str, Any] | None = None
        self.project_items: list[tuple[str, Path, dict[str, Any]]] = []
        self.duration = 0.0
        self.current_page = 0
        self.worker: WorkThread | None = None
        self._saving = False
        self._export_dir: Path | None = None
        self.current_play_chunk_id: str | None = None
        self.playhead_seconds = 0.0
        self.fragment_cards: dict[str, FragmentCard] = {}
        self.waveform_cards: list[FragmentCard] = []

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.play_start = 0.0
        self.play_end = 0.0
        self.loop_playback = True
        self.play_timer = QTimer(self)
        self.play_timer.setInterval(40)
        self.play_timer.timeout.connect(self._check_playback_end)
        self.player.errorOccurred.connect(lambda *_: self.log(f"Audio playback error: {self.player.errorString()}"))
        self.player.positionChanged.connect(self._update_playhead_indicators)

        self._build_ui()
        QApplication.instance().installEventFilter(self)
        self.project_root_edit.setText(str(default_project_dir()))
        self.refresh_projects()
        self.refresh_models()
        self.retranslate()

    def tr(self, key: str) -> str:
        return TEXT[self.language].get(key, key)

    def _build_ui(self):
        central = QWidget()
        main = QVBoxLayout(central)
        main.setContentsMargins(10, 8, 10, 8)
        header = QHBoxLayout()
        self.title_label = QLabel("Speech Extractor")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        header.addWidget(self.title_label)
        header.addStretch(1)
        self.language_combo = QComboBox()
        self.language_combo.addItems(list(LANGUAGES))
        self.language_combo.currentTextChanged.connect(self.change_language)
        header.addWidget(QLabel("UI"))
        header.addWidget(self.language_combo)
        main.addLayout(header)

        self.tabs = QTabWidget()
        self.project_tab = QWidget()
        self.proof_tab = QWidget()
        self.export_tab = QWidget()
        self.tabs.addTab(self.project_tab, "Transcription")
        self.tabs.addTab(self.proof_tab, "Proofreading")
        self.tabs.addTab(self.export_tab, "Export")
        main.addWidget(self.tabs, 1)

        self._build_project_tab()
        self._build_proof_tab()
        self._build_export_tab()

        log_group = QGroupBox("Log")
        self.log_group = log_group
        log_layout = QVBoxLayout(log_group)
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumBlockCount(1500)
        self.log_box.setMinimumHeight(72)
        self.log_box.setMaximumHeight(112)
        log_layout.addWidget(self.log_box)
        main.addWidget(log_group)
        self.setCentralWidget(central)
        self.resize(1420, 1000)
        self.setMinimumSize(1000, 720)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(800)
        self.save_timer.timeout.connect(self.save_current_project)

    def _build_project_tab(self):
        layout = QVBoxLayout(self.project_tab)
        settings_group = QGroupBox()
        self.settings_group = settings_group
        form = QGridLayout(settings_group)

        self.project_folder_label = QLabel()
        self.project_root_edit = QLineEdit()
        self.project_root_browse = QPushButton()
        self.project_root_browse.clicked.connect(self.choose_project_root)
        form.addWidget(self.project_folder_label, 0, 0)
        form.addWidget(self.project_root_edit, 0, 1)
        form.addWidget(self.project_root_browse, 0, 2)

        self.project_name_label = QLabel()
        self.project_name_edit = QLineEdit()
        self.project_name_edit.setMaxLength(100)
        self.project_name_edit.setPlaceholderText("1–100 characters")
        form.addWidget(self.project_name_label, 1, 0)
        form.addWidget(self.project_name_edit, 1, 1, 1, 2)

        self.source_label = QLabel()
        self.source_edit = QLineEdit()
        self.source_browse = QPushButton()
        self.source_browse.clicked.connect(self.choose_source)
        form.addWidget(self.source_label, 2, 0)
        form.addWidget(self.source_edit, 2, 1)
        form.addWidget(self.source_browse, 2, 2)

        self.channels_label = QLabel()
        self.stereo_check = QCheckBox()
        self.stereo_check.setChecked(True)
        self.mono_check = QCheckBox()
        self.mono_check.setChecked(False)
        self.stereo_check.toggled.connect(lambda checked: self.mono_check.setChecked(not checked))
        self.mono_check.toggled.connect(lambda checked: self.stereo_check.setChecked(not checked))
        channel_row = QWidget()
        channel_layout = QHBoxLayout(channel_row)
        channel_layout.setContentsMargins(0, 0, 0, 0)
        channel_layout.addWidget(self.stereo_check)
        channel_layout.addWidget(self.mono_check)
        channel_layout.addStretch(1)
        form.addWidget(self.channels_label, 3, 0)
        form.addWidget(channel_row, 3, 1, 1, 2)

        self.model_label = QLabel()
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(MODEL_CHOICES)
        self.model_combo.setCurrentText(DEFAULT_WHISPER_MODEL)
        self.refresh_models_button = QPushButton()
        self.refresh_models_button.clicked.connect(self.refresh_models)
        self.device_label = QLabel()
        self.device_combo = QComboBox()
        self.device_combo.addItems(["Auto", "CPU", "CUDA"])
        model_row = QWidget()
        model_layout = QHBoxLayout(model_row)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.addWidget(self.model_combo, 1)
        model_layout.addWidget(self.refresh_models_button)
        model_layout.addWidget(self.device_label)
        model_layout.addWidget(self.device_combo)
        form.addWidget(self.model_label, 4, 0)
        form.addWidget(model_row, 4, 1, 1, 2)

        self.vad_group = QGroupBox()
        vad_layout = QGridLayout(self.vad_group)
        self.vad_default_check = QCheckBox()
        self.vad_default_check.setChecked(True)
        vad_layout.addWidget(self.vad_default_check, 0, 0, 1, 4)
        self.vad_threshold = QDoubleSpinBox(); self.vad_threshold.setRange(0.0, 1.0); self.vad_threshold.setDecimals(3); self.vad_threshold.setSingleStep(0.05); self.vad_threshold.setValue(0.5)
        self.vad_min_speech = QSpinBox(); self.vad_min_speech.setRange(0, 2_147_483_647); self.vad_min_speech.setValue(0)
        self.vad_max_speech = QLineEdit("inf")
        self.vad_min_silence = QSpinBox(); self.vad_min_silence.setRange(0, 2_147_483_647); self.vad_min_silence.setValue(2000)
        self.vad_speech_pad = QSpinBox(); self.vad_speech_pad.setRange(0, 2_147_483_647); self.vad_speech_pad.setValue(400)
        self.vad_labels = [QLabel(), QLabel(), QLabel(), QLabel(), QLabel()]
        for i, (label, widget) in enumerate(zip(self.vad_labels, [self.vad_threshold, self.vad_min_speech, self.vad_max_speech, self.vad_min_silence, self.vad_speech_pad])):
            vad_layout.addWidget(label, (i // 3) + 1, (i % 3) * 2)
            vad_layout.addWidget(widget, (i // 3) + 1, (i % 3) * 2 + 1)
        self.vad_default_check.toggled.connect(self._set_vad_enabled)
        self._set_vad_enabled(True)
        form.addWidget(self.vad_group, 5, 0, 1, 3)

        self.whisper_group = QGroupBox()
        whisper_layout = QGridLayout(self.whisper_group)
        self.whisper_default_check = QCheckBox()
        self.whisper_default_check.setChecked(True)
        whisper_layout.addWidget(self.whisper_default_check, 0, 0, 1, 6)

        self.whisper_beam_size = QSpinBox()
        self.whisper_beam_size.setRange(1, 100)
        self.whisper_beam_size.setValue(WHISPER_DEFAULTS["beam_size"])
        self.whisper_temperature = QDoubleSpinBox()
        self.whisper_temperature.setRange(0.0, 1.0)
        self.whisper_temperature.setDecimals(2)
        self.whisper_temperature.setSingleStep(0.05)
        self.whisper_temperature.setValue(WHISPER_DEFAULTS["temperature"])
        self.whisper_condition_previous = QComboBox()
        self.whisper_condition_previous.addItem("False", False)
        self.whisper_condition_previous.addItem("True", True)
        self.whisper_condition_previous.setCurrentIndex(0)
        self.whisper_compression_ratio = QDoubleSpinBox()
        self.whisper_compression_ratio.setRange(0.0, 100.0)
        self.whisper_compression_ratio.setDecimals(2)
        self.whisper_compression_ratio.setSingleStep(0.1)
        self.whisper_compression_ratio.setValue(WHISPER_DEFAULTS["compression_ratio_threshold"])
        self.whisper_log_prob = QDoubleSpinBox()
        self.whisper_log_prob.setRange(-100.0, 100.0)
        self.whisper_log_prob.setDecimals(2)
        self.whisper_log_prob.setSingleStep(0.1)
        self.whisper_log_prob.setValue(WHISPER_DEFAULTS["log_prob_threshold"])
        self.whisper_no_speech = QDoubleSpinBox()
        self.whisper_no_speech.setRange(0.0, 1.0)
        self.whisper_no_speech.setDecimals(2)
        self.whisper_no_speech.setSingleStep(0.05)
        self.whisper_no_speech.setValue(WHISPER_DEFAULTS["no_speech_threshold"])

        self.whisper_labels = [QLabel() for _ in range(6)]
        whisper_widgets = [
            self.whisper_beam_size, self.whisper_temperature, self.whisper_condition_previous,
            self.whisper_compression_ratio, self.whisper_log_prob, self.whisper_no_speech,
        ]
        for i, (label, widget) in enumerate(zip(self.whisper_labels, whisper_widgets)):
            row = (i // 3) + 1
            col = (i % 3) * 2
            whisper_layout.addWidget(label, row, col)
            whisper_layout.addWidget(widget, row, col + 1)
        self.whisper_default_check.toggled.connect(self._set_whisper_enabled)
        self._set_whisper_enabled(True)
        form.addWidget(self.whisper_group, 6, 0, 1, 3)
        layout.addWidget(settings_group)

        action_row = QHBoxLayout()
        self.start_button = QPushButton()
        self.start_button.setMinimumHeight(40)
        self.start_button.clicked.connect(self.start_or_resume)
        self.new_project_button = QPushButton()
        self.new_project_button.clicked.connect(self.new_project)
        action_row.addWidget(self.start_button)
        action_row.addWidget(self.new_project_button)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        action_row.addWidget(self.progress, 1)
        layout.addLayout(action_row)

        load_group = QGroupBox()
        self.load_group = load_group
        load_layout = QGridLayout(load_group)
        self.project_list_label = QLabel()
        self.project_combo = QComboBox()
        self.refresh_projects_button = QPushButton()
        self.refresh_projects_button.clicked.connect(self.refresh_projects)
        self.load_button = QPushButton()
        self.load_button.clicked.connect(self.load_selected_project)
        self.delete_button = QPushButton()
        self.delete_button.clicked.connect(self.delete_selected_project)
        load_layout.addWidget(self.project_list_label, 0, 0)
        load_layout.addWidget(self.project_combo, 0, 1)
        load_layout.addWidget(self.refresh_projects_button, 0, 2)
        load_layout.addWidget(self.load_button, 0, 3)
        load_layout.addWidget(self.delete_button, 0, 4)
        layout.addWidget(load_group)
        layout.addStretch(1)

    def _build_proof_tab(self):
        layout = QVBoxLayout(self.proof_tab)
        top = QHBoxLayout()
        self.progress_label = QLabel()
        top.addWidget(self.progress_label)
        top.addStretch(1)
        self.playhead_label = QLabel("0.000s")
        top.addWidget(self.playhead_label)
        self.all_reviewed_check = QCheckBox()
        self.all_reviewed_check.clicked.connect(self.mark_all_reviewed)
        top.addWidget(self.all_reviewed_check)
        self.merge_playhead_button = QPushButton()
        self.merge_playhead_button.clicked.connect(self.merge_at_playhead)
        self.stop_button = QPushButton()
        self.stop_button.clicked.connect(self.stop_playback)
        self.undo_button = QPushButton()
        self.undo_button.setToolTip(f"{self.tr('undo')} ({'⌘Z' if sys.platform == 'darwin' else 'Ctrl+Z'})")
        self.undo_button.clicked.connect(self.undo_edit)
        self.save_button = QPushButton()
        self.save_button.setToolTip(f"{self.tr('save')} ({'⌘S' if sys.platform == 'darwin' else 'Ctrl+S'})")
        self.save_button.clicked.connect(lambda: self.save_current_project(show_message=True))
        top.addWidget(self.merge_playhead_button)
        top.addWidget(self.stop_button)
        top.addWidget(self.undo_button)
        top.addWidget(self.save_button)
        layout.addLayout(top)

        page_row = QHBoxLayout()
        self.prev_button = QPushButton()
        self.prev_button.clicked.connect(self.previous_page)
        self.page_label = QLabel()
        self.next_button = QPushButton()
        self.next_button.clicked.connect(self.next_page)
        page_row.addWidget(self.prev_button)
        page_row.addStretch(1)
        page_row.addWidget(self.page_label)
        page_row.addStretch(1)
        page_row.addWidget(self.next_button)
        layout.addLayout(page_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.fragment_container = QWidget()
        self.fragment_layout = QVBoxLayout(self.fragment_container)
        self.fragment_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.fragment_container)
        layout.addWidget(self.scroll, 1)

        self.speaker_color = "#4C8BF5"
        self.tag_editor_toggle = QToolButton()
        self.tag_editor_toggle.setCheckable(True)
        self.tag_editor_toggle.setChecked(False)
        self.tag_editor_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.tag_editor_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.tag_editor_toggle.toggled.connect(self.toggle_tag_editor)
        layout.addWidget(self.tag_editor_toggle)

        self.tag_management_page = QWidget()
        self.tag_management_page.setVisible(False)
        tag_layout = QVBoxLayout(self.tag_management_page)
        tag_create_row = QHBoxLayout()
        self.speaker_name_edit = QLineEdit()
        self.speaker_name_edit.setMaxLength(32)
        self.speaker_color_button = QPushButton(self.speaker_color)
        self.speaker_color_button.clicked.connect(self.choose_speaker_color)
        self.add_speaker_button = QPushButton()
        self.add_speaker_button.clicked.connect(self.add_speaker)
        tag_create_row.addWidget(self.speaker_name_edit, 2)
        tag_create_row.addWidget(self.speaker_color_button)
        tag_create_row.addWidget(self.add_speaker_button)
        tag_layout.addLayout(tag_create_row)

        tag_manage_row = QHBoxLayout()
        self.tag_list = QListWidget()
        self.tag_list.setMaximumHeight(82)
        tag_manage_row.addWidget(self.tag_list, 2)
        tag_actions = QVBoxLayout()
        self.default_speaker_label = QLabel()
        self.default_speaker_combo = QComboBox()
        self.default_speaker_combo.currentIndexChanged.connect(self.set_default_speaker)
        self.rename_tag_button = QPushButton()
        self.rename_tag_button.clicked.connect(self.rename_selected_tag)
        self.change_tag_color_button = QPushButton()
        self.change_tag_color_button.clicked.connect(self.change_selected_tag_color)
        self.tag_up_button = QPushButton()
        self.tag_up_button.clicked.connect(lambda: self.move_selected_tag(-1))
        self.tag_down_button = QPushButton()
        self.tag_down_button.clicked.connect(lambda: self.move_selected_tag(1))
        self.delete_tag_button = QPushButton()
        self.delete_tag_button.clicked.connect(self.delete_selected_tag)
        tag_actions.addWidget(self.default_speaker_label)
        tag_actions.addWidget(self.default_speaker_combo)
        tag_actions.addWidget(self.rename_tag_button)
        tag_actions.addWidget(self.change_tag_color_button)
        tag_actions.addWidget(self.tag_up_button)
        tag_actions.addWidget(self.tag_down_button)
        tag_actions.addWidget(self.delete_tag_button)
        tag_actions.addStretch(1)
        tag_manage_row.addLayout(tag_actions, 1)
        tag_layout.addLayout(tag_manage_row)
        layout.addWidget(self.tag_management_page)

    def _build_export_tab(self):
        layout = QVBoxLayout(self.export_tab)
        form = QGridLayout()
        self.export_dir_label = QLabel()
        self.export_dir_edit = QLineEdit()
        self.export_browse_button = QPushButton()
        self.export_browse_button.clicked.connect(self.choose_export_dir)
        form.addWidget(self.export_dir_label, 0, 0)
        form.addWidget(self.export_dir_edit, 0, 1)
        form.addWidget(self.export_browse_button, 0, 2)
        layout.addLayout(form)
        self.numbered_check = QCheckBox()
        self.numbered_check.setChecked(True)
        self.zip_check = QCheckBox()
        options = QHBoxLayout()
        options.addWidget(self.numbered_check)
        options.addWidget(self.zip_check)
        options.addStretch(1)
        layout.addLayout(options)
        buttons = QHBoxLayout()
        self.export_button = QPushButton()
        self.export_button.setMinimumHeight(40)
        self.export_button.clicked.connect(self.run_export)
        self.open_export_button = QPushButton()
        self.open_export_button.clicked.connect(self.open_export_dir)
        buttons.addWidget(self.export_button)
        buttons.addWidget(self.open_export_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.export_summary = QLabel("")
        self.export_summary.setWordWrap(True)
        layout.addWidget(self.export_summary)
        layout.addStretch(1)

    def toggle_tag_editor(self, expanded: bool):
        self.tag_management_page.setVisible(expanded)
        self.tag_editor_toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )

    def retranslate(self):
        self.setWindowTitle(self.tr("title"))
        self.settings_group.setTitle(self.tr("transcription_settings"))
        self.load_group.setTitle(self.tr("load_project"))
        self.log_group.setTitle(self.tr("log"))
        self.tag_editor_toggle.setText(self.tr("speaker_tags"))
        self.merge_playhead_button.setText(self.tr("merge_playhead"))
        self.title_label.setText(self.tr("title"))
        self.tabs.setTabText(0, self.tr("project_tab"))
        self.tabs.setTabText(1, self.tr("proof_tab"))
        self.tabs.setTabText(2, self.tr("export_tab"))
        self.project_folder_label.setText(self.tr("project_folder"))
        self.project_root_browse.setText(self.tr("browse"))
        self.project_name_label.setText(self.tr("project_name"))
        self.source_label.setText(self.tr("source_file"))
        self.source_browse.setText(self.tr("browse"))
        self.channels_label.setText(self.tr("channels"))
        self.stereo_check.setText(self.tr("stereo"))
        self.mono_check.setText(self.tr("mono"))
        self.model_label.setText(self.tr("whisper_model"))
        self.refresh_models_button.setText(self.tr("refresh_models"))
        self.device_label.setText(self.tr("device"))
        self.vad_group.setTitle(self.tr("vad"))
        self.vad_default_check.setText(self.tr("vad_default"))
        for label, key in zip(self.vad_labels, ["threshold", "min_speech", "max_speech", "min_silence", "speech_pad"]):
            label.setText(self.tr(key))
        self.whisper_group.setTitle(self.tr("whisper_options"))
        self.whisper_default_check.setText(self.tr("whisper_default"))
        for label, key in zip(self.whisper_labels, ["beam_size", "temperature", "condition_previous", "compression_ratio", "log_prob", "no_speech"]):
            label.setText(self.tr(key))
        self.undo_button.setToolTip(f"{self.tr('undo')} ({'⌘Z' if sys.platform == 'darwin' else 'Ctrl+Z'})")
        self.save_button.setToolTip(f"{self.tr('save')} ({'⌘S' if sys.platform == 'darwin' else 'Ctrl+S'})")
        self.start_button.setText(self.tr("start"))
        self.new_project_button.setText(self.tr("new_project"))
        self.project_list_label.setText(self.tr("load_project"))
        self.refresh_projects_button.setText(self.tr("refresh_projects"))
        self.load_button.setText(self.tr("load"))
        self.delete_button.setText(self.tr("delete"))
        self.progress_label.setText(self._progress_text())
        self.all_reviewed_check.setText(self.tr("all_reviewed"))
        self.stop_button.setText(self.tr("stop"))
        self.undo_button.setText(self.tr("undo"))
        self.tag_editor_toggle.setArrowType(
            Qt.ArrowType.DownArrow if self.tag_editor_toggle.isChecked() else Qt.ArrowType.RightArrow
        )
        self.save_button.setText(self.tr("save"))
        self.prev_button.setText(self.tr("page_prev"))
        self.next_button.setText(self.tr("page_next"))
        self.add_speaker_button.setText(self.tr("add_speaker"))
        self.default_speaker_label.setText(self.tr("default_speaker"))
        self.rename_tag_button.setText(self.tr("rename_tag"))
        self.change_tag_color_button.setText(self.tr("color_tag"))
        self.tag_up_button.setText(self.tr("tag_up"))
        self.tag_down_button.setText(self.tr("tag_down"))
        self.delete_tag_button.setText(self.tr("delete_tag"))
        self.export_dir_label.setText(self.tr("export_dir"))
        self.export_browse_button.setText(self.tr("browse"))
        self.numbered_check.setText(self.tr("numbered"))
        self.zip_check.setText(self.tr("zip"))
        self.export_button.setText(self.tr("export"))
        self.open_export_button.setText(self.tr("open_export"))
        self.speaker_name_edit.setPlaceholderText(self.tr("speaker_name"))
        self.refresh_proof_page()

    def change_language(self, language: str):
        if language not in TEXT:
            return
        self.language = language
        self.t = TEXT[language]
        self.retranslate()

    def _set_vad_enabled(self, use_default: bool):
        for widget in (self.vad_threshold, self.vad_min_speech, self.vad_max_speech,
                       self.vad_min_silence, self.vad_speech_pad):
            widget.setEnabled(not use_default)

    def _set_whisper_enabled(self, use_default: bool):
        for widget in (self.whisper_beam_size, self.whisper_temperature,
                       self.whisper_condition_previous, self.whisper_compression_ratio,
                       self.whisper_log_prob, self.whisper_no_speech):
            widget.setEnabled(not use_default)

    def _progress_text(self):
        return ""

    def log(self, message: str):
        from datetime import datetime
        self.log_box.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def choose_project_root(self):
        path = QFileDialog.getExistingDirectory(self, self.tr("choose_folder"), self.project_root_edit.text())
        if path:
            self.project_root_edit.setText(path)
            self.refresh_projects()

    def choose_source(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr("choose_source"), "",
            "Media files (*.wav *.mp3 *.flac *.m4a *.aac *.ogg *.opus *.mp4 *.mkv *.mov *.avi *.webm *.m4v);;All files (*)")
        if path:
            self.source_edit.setText(path)

    def _selected_model_id(self) -> str:
        index = self.model_combo.currentIndex()
        if index >= 0 and self.model_combo.currentText() == self.model_combo.itemText(index):
            value = self.model_combo.itemData(index)
            if value:
                return str(value)
        return self.model_combo.currentText().removeprefix("✔ ").strip()

    def refresh_models(self):
        current = self._selected_model_id() if hasattr(self, "model_combo") else DEFAULT_WHISPER_MODEL
        cached = [model_id for model_id in list_cached_models()
                  if model_id.casefold() != "openai/whisper-large-v3"]
        cached_set = set(cached)
        # Built-in choices keep their configured order; cached custom models follow them.
        values = build_model_choices(cached)
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for model_id in values:
            installed = model_id in cached_set
            label = f"✔ {model_id}" if installed else model_id
            self.model_combo.addItem(label, model_id)
        self.model_combo.setEditable(True)
        self.model_combo.setToolTip("✔ indicates a model repository or converted model is already cached locally.")
        index = self.model_combo.findData(current)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
        else:
            self.model_combo.setEditText(current or DEFAULT_WHISPER_MODEL)
        self.model_combo.blockSignals(False)
        if cached:
            self.log("Cached models detected (✔): " + ", ".join(cached))
        else:
            self.log("No cached Whisper model was detected.")
        self.log(f"Model list refreshed; {len(cached)} cached Hugging Face / converted entries found.")

    def refresh_projects(self):
        root = Path(self.project_root_edit.text()).expanduser() if self.project_root_edit.text() else default_project_dir()
        self.project_items = list_projects(root)
        self.project_combo.clear()
        for name, folder, _data in self.project_items:
            self.project_combo.addItem(name, str(folder))
        self.log(f"Project list refreshed: {len(self.project_items)} project(s).")

    def load_selected_project(self):
        folder = self.project_combo.currentData()
        if not folder:
            QMessageBox.information(self, self.tr("load_project"), "Select a project first.")
            return
        try:
            self._load_project(Path(folder))
        except Exception as exc:
            QMessageBox.critical(self, self.tr("load_project"), str(exc))

    def _load_project(self, folder: Path):
        self.player.stop()
        self.project_dir = folder
        self.data = open_project(folder)
        self.project_name_edit.setText(str(self.data.get("name", "")))
        self.source_edit.setText(str(self.data.get("source", "")))
        self.project_root_edit.setText(str(folder.parent))
        ref = folder / "reference.wav"
        if ref.is_file():
            self.player.setSource(QUrl.fromLocalFile(str(ref.resolve())))
            try:
                _channels, _width, _rate, _frames, self.duration = wav_info(ref)
            except Exception:
                self.duration = 0.0
        else:
            self.duration = 0.0
        settings = self.data.get("settings", {})
        model = settings.get("whisper_model", DEFAULT_WHISPER_MODEL)
        model_index = self.model_combo.findData(model)
        if model_index >= 0:
            self.model_combo.setCurrentIndex(model_index)
        else:
            self.model_combo.setEditText(model)
        saved_vad = settings.get("vad_parameters", "faster-whisper defaults")
        self.vad_default_check.setChecked(not isinstance(saved_vad, dict))
        if isinstance(saved_vad, dict):
            self.vad_threshold.setValue(float(saved_vad.get("threshold", VAD_DEFAULTS["threshold"])))
            self.vad_min_speech.setValue(int(saved_vad.get("min_speech_duration_ms", 0)))
            self.vad_max_speech.setText(str(saved_vad.get("max_speech_duration_s", "inf")))
            self.vad_min_silence.setValue(int(saved_vad.get("min_silence_duration_ms", 2000)))
            self.vad_speech_pad.setValue(int(saved_vad.get("speech_pad_ms", 400)))
        saved_whisper = settings.get("whisper_parameters", "faster-whisper defaults")
        self.whisper_default_check.setChecked(not isinstance(saved_whisper, dict))
        if isinstance(saved_whisper, dict):
            self.whisper_beam_size.setValue(int(saved_whisper.get("beam_size", WHISPER_DEFAULTS["beam_size"])))
            self.whisper_temperature.setValue(float(saved_whisper.get("temperature", WHISPER_DEFAULTS["temperature"])))
            condition = bool(saved_whisper.get("condition_on_previous_text", WHISPER_DEFAULTS["condition_on_previous_text"]))
            self.whisper_condition_previous.setCurrentIndex(1 if condition else 0)
            self.whisper_compression_ratio.setValue(float(saved_whisper.get("compression_ratio_threshold", WHISPER_DEFAULTS["compression_ratio_threshold"])))
            self.whisper_log_prob.setValue(float(saved_whisper.get("log_prob_threshold", WHISPER_DEFAULTS["log_prob_threshold"])))
            self.whisper_no_speech.setValue(float(saved_whisper.get("no_speech_threshold", WHISPER_DEFAULTS["no_speech_threshold"])))
        self.export_dir_edit.setText(str((folder / "result").resolve()))
        self.current_page = 0
        chunks = active_chunks(self.data)
        if chunks and ref.exists():
            self.tabs.setCurrentIndex(1)
        elif ref.exists() and not chunks:
            self.tabs.setCurrentIndex(0)
            self.start_button.setEnabled(True)
        else:
            self.tabs.setCurrentIndex(0)
        can_resume = ref.is_file() and self.data.get("phase", "created") not in {"proofreading", "exported"}
        self.start_button.setEnabled(can_resume or not bool(chunks))
        self.refresh_proof_page()
        self.refresh_speakers()
        self.log(f"{self.tr('project_loaded')}: {self.data.get('name')} ({len(chunks)} active fragments)")

    def delete_selected_project(self):
        folder = self.project_combo.currentData()
        if not folder:
            return
        answer = QMessageBox.warning(self, self.tr("delete"), self.tr("confirm_delete"),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        path = Path(folder)
        try:
            move_project_to_trash(path)
            self.clear_project_view()
            self.refresh_projects()
            self.log(f"Moved project to system trash: {path}")
        except Exception as exc:
            QMessageBox.critical(self, self.tr("delete"), f"Could not move project to Trash: {exc}")
            self.log(f"ERROR: project deletion failed: {exc}")

    def new_project(self):
        self.clear_project_view()
        self.start_button.setEnabled(True)
        self.log("New project form ready.")

    def clear_project_view(self):
        self.player.stop()
        self.project_dir = None
        self.data = None
        self.duration = 0.0
        self.project_name_edit.clear()
        self.source_edit.clear()
        self.export_dir_edit.clear()
        self.progress_label.clear()
        self.export_summary.clear()
        self.start_button.setEnabled(True)
        self.current_page = 0
        self.refresh_proof_page()
        self.refresh_speakers()
        self.tabs.setCurrentIndex(0)

    def _read_vad_settings(self) -> dict[str, Any] | None:
        if self.vad_default_check.isChecked():
            return None
        threshold = float(self.vad_threshold.value())
        max_speech = parse_inf_float(self.vad_max_speech.text())
        if not (0.0 <= threshold <= 1.0):
            raise ValueError("threshold must be in [0, 1]")
        if max_speech <= 0:
            raise ValueError("max_speech_duration_s must be greater than 0")
        return {
            "threshold": threshold,
            "min_speech_duration_ms": int(self.vad_min_speech.value()),
            "max_speech_duration_s": max_speech,
            "min_silence_duration_ms": int(self.vad_min_silence.value()),
            "speech_pad_ms": int(self.vad_speech_pad.value()),
        }

    def start_or_resume(self):
        if self.worker and self.worker.isRunning():
            return
        try:
            model_id = self._selected_model_id()
            if not model_id:
                raise ValueError("Choose or enter a Whisper model ID / local path.")
            vad = self._read_vad_settings()
            whisper = self._read_whisper_settings()
            self.log(f"Selected Whisper model: {model_id}")
            phase = self.data.get("phase", "created") if self.data else "created"
            if (self.project_dir and self.data and (self.project_dir / "reference.wav").is_file()
                    and phase not in {"proofreading", "exported"}):
                folder = self.project_dir
                source = Path(self.data.get("source", ""))
                convert = False
                channels = int(self.data.get("settings", {}).get("audio_channels", 2))
                self.data["chunks"] = []  # Retry an interrupted/incomplete transcription from the reference WAV.
                self.data.setdefault("settings", {})["whisper_model"] = model_id
                self.data["settings"]["vad_filter"] = True
                self.data["settings"]["vad_parameters"] = self._serialize_vad(vad)
                self.data["settings"]["whisper_parameters"] = self._serialize_whisper(whisper)
            else:
                entered_name = self.project_name_edit.text()
                name = entered_name.strip()
                source = Path(self.source_edit.text()).expanduser()
                if not source.is_file():
                    raise ValueError("Choose an existing source audio / video file.")
                if name:
                    if len(name) > 100:
                        raise ValueError("Project name must contain 1–100 characters.")
                    if has_invalid_component_characters(name):
                        QMessageBox.warning(
                            self, self.tr("new_project"),
                            'Project name contains characters that are invalid on Windows, macOS, or Linux.\n'
                            r'Remove characters such as < > : " / \ | ? * and control characters, then try again.',
                        )
                        self.project_name_edit.setFocus()
                        return
                else:
                    # Empty project name: derive from the source file's sanitized stem.
                    name = sanitize_component_raw(source.stem)[:100]
                    if not name.strip():
                        name = new_id()
                    self.project_name_edit.setText(name)
                root = Path(self.project_root_edit.text()).expanduser()
                if not root.exists():
                    root.mkdir(parents=True, exist_ok=True)
                channels = 2 if self.stereo_check.isChecked() else 1
                folder, self.data = create_project(root, name, source, self._serialize_vad(vad), model_id,
                                                   stereo=(channels == 2),
                                                   whisper_settings=self._serialize_whisper(whisper))
                self.project_dir = folder
                self.export_dir_edit.setText(str((folder / "result").resolve()))
                convert = True
                self.log(f"Created project: {folder} (name: {self.data.get('name')})")
            self.data["phase"] = "transcribing"
            save_project(folder, self.data)
            self.start_button.setEnabled(False)
            self.progress.show()
            self.worker = WorkThread(source, folder / "reference.wav", model_id, vad, whisper,
                                     self.device_combo.currentText(), convert, channels)
            self.worker.progress.connect(self.log)
            self.worker.chunk_added.connect(self.on_transcription_chunk)
            self.worker.succeeded.connect(self.on_work_succeeded)
            self.worker.failed.connect(self.on_work_failed)
            self.worker.start()
        except Exception as exc:
            QMessageBox.warning(self, self.tr("start"), str(exc))

    @staticmethod
    def _serialize_vad(vad: dict[str, Any] | None):
        if vad is None:
            return "faster-whisper defaults"
        result = dict(vad)
        if math.isinf(float(result["max_speech_duration_s"])):
            result["max_speech_duration_s"] = "inf"
        return result

    def _read_whisper_settings(self) -> dict[str, Any] | None:
        if self.whisper_default_check.isChecked():
            return None
        temperature = float(self.whisper_temperature.value())
        no_speech_threshold = float(self.whisper_no_speech.value())
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("temperature must be in [0, 1]")
        if not 0.0 <= no_speech_threshold <= 1.0:
            raise ValueError("no_speech_threshold must be in [0, 1]")
        return {
            "beam_size": int(self.whisper_beam_size.value()),
            "temperature": temperature,
            "condition_on_previous_text": bool(self.whisper_condition_previous.currentData()),
            "compression_ratio_threshold": float(self.whisper_compression_ratio.value()),
            "log_prob_threshold": float(self.whisper_log_prob.value()),
            "no_speech_threshold": no_speech_threshold,
        }

    @staticmethod
    def _serialize_whisper(whisper: dict[str, Any] | None):
        return "faster-whisper defaults" if whisper is None else dict(whisper)

    def on_transcription_chunk(self, chunk: dict[str, Any]):
        if not self.data:
            return
        default_tag = str(self.data.get("default_speaker", "") or "")
        if default_tag in self.data.get("speakers", {}):
            chunk["speaker"] = default_tag
        self.data.setdefault("chunks", []).append(chunk)
        self.schedule_save()

    def on_work_succeeded(self, chunks: list, metadata: dict):
        self.progress.hide()
        self.start_button.setEnabled(False)
        if not self.data or not self.project_dir:
            return
        default_tag = str(self.data.get("default_speaker", "") or "")
        if default_tag in self.data.get("speakers", {}):
            for chunk in chunks:
                chunk["speaker"] = default_tag
        self.data["chunks"] = chunks
        self.data["transcription"] = metadata
        self.data["phase"] = "proofreading" if chunks else "audio_ready"
        save_project(self.project_dir, self.data)
        try:
            _ch, _width, _rate, _frames, self.duration = wav_info(self.project_dir / "reference.wav")
            self.player.setSource(QUrl.fromLocalFile(str((self.project_dir / "reference.wav").resolve())))
        except Exception as exc:
            self.log(f"Could not initialize playback: {exc}")
        self.current_page = 0
        self.refresh_proof_page()
        self.refresh_speakers()
        self.refresh_projects()
        self.tabs.setCurrentIndex(1)
        self.log(f"Transcription complete: {len(chunks)} fragments; language={metadata.get('language')}.")
        if not chunks:
            self.start_button.setEnabled(True)
            QMessageBox.warning(self, self.tr("start"), "No speech segments were returned. Check the audio and VAD settings.")

    def on_work_failed(self, stage: str, details: str):
        self.progress.hide()
        self.start_button.setEnabled(True)
        self.log(f"ERROR ({stage}):\n{details}")
        if stage == "audio" and self.project_dir:
            failed_dir = self.project_dir
            try:
                move_project_to_trash(failed_dir)
                self.log(self.tr("audio_failed"))
            except Exception as exc:
                self.log(f"Could not move failed project to Trash: {exc}")
            self.clear_project_view()
            self.refresh_projects()
            QMessageBox.critical(self, self.tr("start"), self.tr("audio_failed") + "\n\n" + details[-1800:])
        else:
            if self.data and self.project_dir:
                self.data["phase"] = "audio_ready" if (self.project_dir / "reference.wav").exists() else "created"
                save_project(self.project_dir, self.data)
            QMessageBox.critical(self, self.tr("start"), self.tr("transcription_failed") + "\n\n" + details[-1800:])

    def save_current_project(self, show_message: bool = False):
        if not self.data or not self.project_dir:
            return
        try:
            save_project(self.project_dir, self.data)
            if show_message:
                self.log(self.tr("saved"))
        except Exception as exc:
            self.log(f"ERROR saving project: {exc}")

    def schedule_save(self):
        if self.data and self.project_dir:
            self.save_timer.start()

    def refresh_proof_page(self):
        if not hasattr(self, "fragment_layout"):
            return
        while self.fragment_layout.count():
            item = self.fragment_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.fragment_cards = {}
        self.waveform_cards = []
        if not self.data or not self.project_dir or not (self.project_dir / "reference.wav").is_file():
            self.progress_label.setText(f"{self.tr('to_review')}: 0  /  {self.tr('total')}: 0")
            self.page_label.setText(f"{self.tr('page')} 0 / 0")
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            self.merge_playhead_button.setEnabled(False)
            return
        chunks = active_chunks(self.data)
        total = len(chunks)
        need_review = sum(1 for chunk in chunks if not chunk.get("reviewed", False))
        pages = max(1, math.ceil(total / PAGE_SIZE))
        # Keep the current page after edits; only clamp it when the total number
        # of pages shrinks (for example, merging the only items on the last page).
        self.current_page = max(0, min(self.current_page, pages - 1))
        page_chunks = chunks[self.current_page * PAGE_SIZE:(self.current_page + 1) * PAGE_SIZE]
        self.all_reviewed_check.blockSignals(True)
        self.all_reviewed_check.setChecked(bool(page_chunks) and all(chunk.get("reviewed", False) for chunk in page_chunks))
        self.all_reviewed_check.setEnabled(bool(page_chunks))
        self.all_reviewed_check.blockSignals(False)
        self.progress_label.setText(f"{self.tr('to_review')}: {need_review}  /  {self.tr('total')}: {total}")
        self.page_label.setText(f"{self.tr('page')} {self.current_page + 1} / {pages}")
        self.prev_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(self.current_page < pages - 1)
        self.merge_playhead_button.setEnabled(len(chunks) >= 2)
        callbacks = {
            "change": self.on_chunk_change,
            "play": self.play_chunk,
            "split": self.split_chunk,
            "merge": self.merge_with_next,
            "delete": self.delete_chunk,
            "seek": self.seek_playhead,
            "enter_next": self.on_enter_advance,
        }
        start_idx = self.current_page * PAGE_SIZE
        for i, chunk in enumerate(chunks[start_idx:start_idx + PAGE_SIZE], start=start_idx + 1):
            card = FragmentCard(
                i, chunk, self.data.get("speakers", {}), self.data.get("default_speaker", ""),
                self.project_dir / "reference.wav", self.duration, self.t, callbacks,
            )
            card.set_playhead(self.player.position() / 1000.0)
            self.fragment_cards[chunk["id"]] = card
            self.waveform_cards.append(card)
            self.fragment_layout.addWidget(card)
        self.fragment_layout.addStretch(1)
        self.undo_button.setEnabled(bool(self.data.get("history")))

    def on_chunk_change(self, chunk_id: str, key: str, value: Any):
        if not self.data:
            return
        chunk = next((c for c in self.data.get("chunks", []) if c.get("id") == chunk_id and c.get("status", True)), None)
        if not chunk:
            return
        if key in {"start", "end"}:
            other = float(chunk.get("end" if key == "start" else "start", 0.0))
            value = float(value)
            if key == "start":
                value = max(0.0, min(value, other - 0.01))
            else:
                value = min(self.duration, max(value, other + 0.01))
            value = round(value, 3)
        chunk[key] = value
        if key in {"start", "end"}:
            card = self.fragment_cards.get(chunk_id)
            if card:
                box = card.start_box if key == "start" else card.end_box
                box.blockSignals(True)
                box.setValue(float(chunk[key]))
                box.blockSignals(False)
                if card.wave.drag_mode:
                    card.wave.update_bounds(float(chunk["start"]), float(chunk["end"]))
                else:
                    card.wave.update_range(float(chunk["start"]), float(chunk["end"]))
        self.schedule_save()
        if key == "reviewed":
            active = active_chunks(self.data)
            need = sum(1 for c in active if not c.get("reviewed", False))
            self.progress_label.setText(f"{self.tr('to_review')}: {need}  /  {self.tr('total')}: {len(active)}")

    def previous_page(self):
        self.current_page = max(0, self.current_page - 1)
        self.refresh_proof_page()

    def next_page(self):
        total = len(active_chunks(self.data)) if self.data else 0
        pages = max(1, math.ceil(total / PAGE_SIZE))
        self.current_page = min(pages - 1, self.current_page + 1)
        self.refresh_proof_page()

    def mark_all_reviewed(self, checked: bool):
        if not self.data:
            return
        chunks = active_chunks(self.data)
        start = self.current_page * PAGE_SIZE
        for chunk in chunks[start:start + PAGE_SIZE]:
            chunk["reviewed"] = checked
        self.schedule_save()
        self.refresh_proof_page()

    def split_chunk(self, chunk_id: str):
        if not self.data:
            return
        target = next((c for c in self.data.get("chunks", []) if c.get("id") == chunk_id and c.get("status", True)), None)
        if not target:
            return
        start, end = float(target["start"]), float(target["end"])
        if end - start < 0.10:
            QMessageBox.warning(self, self.tr("split"), "This fragment is too short to split.")
            return
        playhead = self.playhead_seconds
        if start + 0.01 < playhead < end - 0.01:
            value = playhead
        else:
            value, ok = QInputDialog.getDouble(self, self.tr("split"), "Split time (seconds):", (start + end) / 2,
                                                start + 0.01, end - 0.01, 3)
            if not ok:
                return
        fraction = (value - start) / max(0.001, end - start)
        left_text, right_text = split_text_at_fraction(str(target.get("corrected_text", "")), fraction)
        left_original, right_original = split_text_at_fraction(str(target.get("original_text", "")), fraction)
        snapshot_chunks(self.data, "split")
        target["status"] = False
        target["reviewed"] = False
        a = create_chunk(start, value, left_text, str(target.get("speaker", "")))
        b = create_chunk(value, end, right_text, str(target.get("speaker", "")))
        a["original_text"] = left_original
        b["original_text"] = right_original
        self.data["chunks"].extend([a, b])
        self.refresh_proof_page()
        self.schedule_save()
        self.log(f"Split fragment {chunk_id[:8]} at {value:.3f}s (playhead-aware).")

    def delete_chunk(self, chunk_id: str):
        """Soft-delete a false-positive fragment; the operation is undoable."""
        if not self.data:
            return
        target = next(
            (chunk for chunk in self.data.get("chunks", [])
             if chunk.get("id") == chunk_id and chunk.get("status", True)),
            None,
        )
        if target is None:
            return
        snapshot_chunks(self.data, "delete")
        target["status"] = False
        if self.current_play_chunk_id == chunk_id:
            self.stop_playback()
        self.refresh_proof_page()
        self.schedule_save()
        self.log(f"Deleted fragment {chunk_id[:8]} (soft-delete; Undo can restore it).")

    def _merge_pair(self, first: dict[str, Any], second: dict[str, Any]):
        if not self.data:
            return
        chunks = active_chunks(self.data)
        try:
            index = next(i for i, item in enumerate(chunks) if item["id"] == first["id"])
        except StopIteration:
            return
        if index + 1 >= len(chunks) or chunks[index + 1]["id"] != second["id"]:
            QMessageBox.warning(self, self.tr("merge_next"), "Only adjacent active fragments can be merged.")
            return
        snapshot_chunks(self.data, "merge")
        first["status"] = False
        second["status"] = False
        first_text = str(first.get("corrected_text", "")).strip()
        second_text = str(second.get("corrected_text", "")).strip()
        merged_text = " ".join(x for x in (first_text, second_text) if x)
        merged_original = " ".join(x for x in (str(first.get("original_text", "")).strip(),
                                                str(second.get("original_text", "")).strip()) if x)
        same_tag = first.get("speaker", "") == second.get("speaker", "")
        merged = create_chunk(min(float(first["start"]), float(second["start"])),
                              max(float(first["end"]), float(second["end"])), merged_text,
                              str(first.get("speaker", "")) if same_tag else "")
        merged["original_text"] = merged_original
        self.data["chunks"].append(merged)
        self.refresh_proof_page()
        self.schedule_save()
        self.log(f"Merged adjacent fragments {first['id'][:8]} and {second['id'][:8]}.")

    def merge_with_next(self, chunk_id: str):
        if not self.data:
            return
        chunks = active_chunks(self.data)
        index = next((i for i, c in enumerate(chunks) if c.get("id") == chunk_id), -1)
        if index < 0 or index + 1 >= len(chunks):
            QMessageBox.information(self, self.tr("merge_next"), "There is no next active fragment to merge.")
            return
        self._merge_pair(chunks[index], chunks[index + 1])

    def merge_at_playhead(self):
        if not self.data:
            return
        chunks = active_chunks(self.data)
        if len(chunks) < 2:
            return
        playhead = self.playhead_seconds
        candidates = []
        for index in range(len(chunks) - 1):
            first, second = chunks[index], chunks[index + 1]
            combined_start = float(first["start"])
            combined_end = float(second["end"])
            if combined_start <= playhead <= combined_end:
                candidates.append((abs(playhead - float(first["end"])), index))
        if not candidates:
            QMessageBox.information(self, self.tr("merge_playhead"),
                                    "Move the playhead into the time range covered by two adjacent fragments first.")
            return
        _distance, index = min(candidates)
        self._merge_pair(chunks[index], chunks[index + 1])

    def on_enter_advance(self, chunk_id: str):
        if not self.data:
            return
        chunks = active_chunks(self.data)
        index = next((i for i, chunk in enumerate(chunks) if chunk["id"] == chunk_id), -1)
        if index < 0:
            return
        was_playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        current = next(c for c in self.data["chunks"] if c.get("id") == chunk_id and c.get("status", True))
        current["reviewed"] = True
        card = self.fragment_cards.get(chunk_id)
        if card:
            card.reviewed.blockSignals(True)
            card.reviewed.setChecked(True)
            card.reviewed.blockSignals(False)
        need = sum(1 for c in chunks if not c.get("reviewed", False))
        self.progress_label.setText(f"{self.tr('to_review')}: {need}  /  {self.tr('total')}: {len(chunks)}")
        self.schedule_save()
        next_index = index + 1
        if next_index >= len(chunks):
            return
        next_chunk = chunks[next_index]
        next_page = next_index // PAGE_SIZE
        if next_page != self.current_page:
            self.current_page = next_page
            self.refresh_proof_page()
        next_card = self.fragment_cards.get(next_chunk["id"])
        if next_card:
            next_card.corrected.setFocus()
            next_card.corrected.selectAll()
        if was_playing:
            self.play_chunk(next_chunk["id"])

    def undo_edit(self):
        if self.data and undo_last(self.data):
            self.refresh_proof_page()
            self.schedule_save()
            self.log("Last fragment edit undone.")

    def refresh_speakers(self):
        if not hasattr(self, "default_speaker_combo"):
            return
        self.default_speaker_combo.blockSignals(True)
        self.default_speaker_combo.clear()
        self.default_speaker_combo.addItem(self.tr("empty_speaker"), "")
        self.tag_list.clear()
        if self.data:
            tags = self.data.setdefault("speakers", {})
            default_tag = str(self.data.get("default_speaker", "") or "")
            ordered = list(tags.items())
            ordered.sort(key=lambda item: item[0] != default_tag)
            tags = {name: meta for name, meta in ordered}
            self.data["speakers"] = tags
            for name, meta in ordered:
                self.default_speaker_combo.addItem(("★ " if name == default_tag else "") + name, name)
                item = QListWidgetItem(("★ " if name == default_tag else "") + name)
                item.setData(Qt.ItemDataRole.UserRole, name)
                item.setForeground(QBrush(QColor((meta or {}).get("color", "#808080"))))
                self.tag_list.addItem(item)
            index = self.default_speaker_combo.findData(default_tag)
            self.default_speaker_combo.setCurrentIndex(max(0, index))
        self.default_speaker_combo.blockSignals(False)
        has_tags = self.tag_list.count() > 0
        self.rename_tag_button.setEnabled(has_tags)
        self.change_tag_color_button.setEnabled(has_tags)
        self.tag_up_button.setEnabled(has_tags)
        self.tag_down_button.setEnabled(has_tags)
        self.delete_tag_button.setEnabled(has_tags)
        self.refresh_proof_page()

    def choose_speaker_color(self):
        color = QColorDialog.getColor(QColor(self.speaker_color), self, self.tr("speaker_tags"))
        if color.isValid():
            self.speaker_color = color.name()
            self.speaker_color_button.setText(self.speaker_color)
            self.speaker_color_button.setStyleSheet(f"background:{self.speaker_color}; color:white;")

    def add_speaker(self):
        if not self.data:
            QMessageBox.information(self, self.tr("speaker_tags"), "Load or create a project first.")
            return
        tags = self.data.setdefault("speakers", {})
        if len(tags) >= 10:
            QMessageBox.warning(self, self.tr("speaker_tags"), "A project can contain at most 10 tags.")
            return
        name = self.speaker_name_edit.text().strip()
        if not 1 <= len(name) <= 32:
            QMessageBox.warning(self, self.tr("speaker_tags"), "Tag name must contain 1–32 characters.")
            return
        clean = sanitize_component_raw(name)
        if not clean or not 1 <= len(clean) <= 32:
            QMessageBox.warning(self, self.tr("speaker_tags"), "The tag name is empty or invalid after sanitization.")
            return
        if clean != name:
            self.log(f"Tag name sanitized: {name!r} → {clean!r}")
        if any(existing.casefold() == clean.casefold() for existing in tags):
            QMessageBox.warning(self, self.tr("speaker_tags"), "That tag already exists (tag names are case-insensitive).")
            return
        is_first = not tags
        tags[clean] = {"color": self.speaker_color}
        if is_first:
            self.data["default_speaker"] = clean
            # The first created tag becomes the default and is applied to all existing text.
            for chunk in self.data.get("chunks", []):
                chunk["speaker"] = clean
        self.speaker_name_edit.clear()
        self.refresh_speakers()
        self.schedule_save()
        self.log(f"Added tag: {clean}")

    def set_default_speaker(self, _index: int):
        if self.data:
            self.data["default_speaker"] = self.default_speaker_combo.currentData() or ""
            self.refresh_speakers()
            self.schedule_save()

    def rename_selected_tag(self):
        if not self.data or not self.tag_list.currentItem():
            return
        old_name = str(self.tag_list.currentItem().data(Qt.ItemDataRole.UserRole))
        new_name, ok = QInputDialog.getText(self, self.tr("speaker_tags"), "Rename tag:", text=old_name)
        if not ok:
            return
        new_name = new_name.strip()
        if not 1 <= len(new_name) <= 32:
            QMessageBox.warning(self, self.tr("speaker_tags"), "Tag name must contain 1–32 characters.")
            return
        clean = sanitize_component_raw(new_name)
        tags = self.data.setdefault("speakers", {})
        duplicate = any(existing.casefold() == clean.casefold() and existing != old_name for existing in tags)
        if not clean or duplicate:
            QMessageBox.warning(self, self.tr("speaker_tags"), "The tag name is empty or already exists.")
            return
        if clean != new_name:
            self.log(f"Tag name sanitized: {new_name!r} → {clean!r}")
        meta = tags.pop(old_name)
        tags[clean] = meta
        for chunk in self.data.get("chunks", []):
            if chunk.get("speaker") == old_name:
                chunk["speaker"] = clean
        if self.data.get("default_speaker") == old_name:
            self.data["default_speaker"] = clean
        self.refresh_speakers()
        self.schedule_save()
        self.log(f"Renamed tag: {old_name} → {clean}")

    def change_selected_tag_color(self):
        if not self.data or not self.tag_list.currentItem():
            return
        name = str(self.tag_list.currentItem().data(Qt.ItemDataRole.UserRole))
        current = QColor(self.data.get("speakers", {}).get(name, {}).get("color", "#808080"))
        color = QColorDialog.getColor(current, self, self.tr("speaker_tags"))
        if not color.isValid():
            return
        self.data["speakers"][name]["color"] = color.name()
        self.refresh_speakers()
        self.schedule_save()
        self.log(f"Changed tag color: {name} → {color.name()}")

    def move_selected_tag(self, delta: int):
        if not self.data or not self.tag_list.currentItem():
            return
        name = str(self.tag_list.currentItem().data(Qt.ItemDataRole.UserRole))
        tags = self.data.setdefault("speakers", {})
        keys = list(tags)
        if name not in keys:
            return
        default_tag = str(self.data.get("default_speaker", "") or "")
        minimum_index = 1 if default_tag in keys else 0
        old_index = keys.index(name)
        new_index = old_index + int(delta)
        if new_index < minimum_index or new_index >= len(keys):
            return
        keys.pop(old_index)
        keys.insert(new_index, name)
        self.data["speakers"] = {key: tags[key] for key in keys}
        self.refresh_speakers()
        for row in range(self.tag_list.count()):
            if self.tag_list.item(row).data(Qt.ItemDataRole.UserRole) == name:
                self.tag_list.setCurrentRow(row)
                break
        self.schedule_save()

    def delete_selected_tag(self):
        if not self.data or not self.tag_list.currentItem():
            return
        name = str(self.tag_list.currentItem().data(Qt.ItemDataRole.UserRole))
        answer = QMessageBox.question(
            self, self.tr("speaker_tags"),
            f"Delete tag '{name}'? Fragments using it will be changed to (None).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        tags = self.data.setdefault("speakers", {})
        tags.pop(name, None)
        for chunk in self.data.get("chunks", []):
            if chunk.get("speaker") == name:
                chunk["speaker"] = ""
        if self.data.get("default_speaker") == name:
            self.data["default_speaker"] = next(iter(tags), "")
        self.refresh_speakers()
        self.schedule_save()
        self.log(f"Deleted tag: {name}; assigned fragments are now untagged.")

    def play_chunk(self, chunk_id: str):
        if not self.data or not self.project_dir:
            return
        chunk = next((c for c in self.data.get("chunks", []) if c.get("id") == chunk_id and c.get("status", True)), None)
        if not chunk:
            return
        self.current_play_chunk_id = chunk_id
        self.play_start = max(0.0, float(chunk["start"]))
        self.play_end = min(self.duration, float(chunk["end"]))
        self.loop_playback = True
        if self.play_end <= self.play_start:
            self.log(f"WARNING: invalid playback range for fragment {chunk_id[:8]}")
            return
        self.playhead_seconds = self.play_start
        self.player.setPosition(int(self.play_start * 1000))
        self.player.play()
        self.play_timer.start()
        self._update_playhead_indicators(self.play_start * 1000)

    def seek_playhead(self, seconds: float):
        if not self.project_dir or not (self.project_dir / "reference.wav").is_file():
            return
        seconds = max(0.0, min(self.duration, float(seconds)))
        self.playhead_seconds = seconds
        if self.data:
            chunks = active_chunks(self.data)
            containing = next((c for c in chunks if float(c["start"]) <= seconds <= float(c["end"])), None)
            if containing:
                self.current_play_chunk_id = containing["id"]
            elif chunks:
                nearest = min(chunks, key=lambda c: min(abs(seconds - float(c["start"])), abs(seconds - float(c["end"]))))
                self.current_play_chunk_id = nearest["id"]
        self.player.setPosition(int(seconds * 1000))
        self._update_playhead_indicators(seconds * 1000)

    def _update_playhead_indicators(self, position_ms: int | None = None):
        seconds = (self.player.position() if position_ms is None else int(position_ms)) / 1000.0
        self.playhead_seconds = seconds
        if hasattr(self, "playhead_label"):
            self.playhead_label.setText(f"{seconds:.3f}s")
        for card in getattr(self, "waveform_cards", []):
            card.set_playhead(seconds)

    def _check_playback_end(self):
        position = self.player.position()
        self._update_playhead_indicators(position)
        if position >= int(self.play_end * 1000) and self.play_end > self.play_start:
            if self.loop_playback:
                self.player.setPosition(int(self.play_start * 1000))
                if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                    self.player.play()
            else:
                self.player.stop()
                self.play_timer.stop()

    def toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.stop_playback()
            return
        if not self.data:
            return

        chunks = active_chunks(self.data)
        if not chunks:
            return

        # Resume from the current playhead when it lies inside a fragment;
        # do not restart the fragment from its beginning after pausing.
        position = self.player.position() / 1000.0
        chunk = next((c for c in chunks
                      if float(c["start"]) <= position < float(c["end"])), None)
        if chunk is None and self.current_play_chunk_id:
            chunk = next((c for c in chunks if c["id"] == self.current_play_chunk_id), None)
        if chunk is None:
            position = self.playhead_seconds
            chunk = next((c for c in chunks
                          if float(c["start"]) <= position < float(c["end"])), None)
        if chunk is None:
            index = min(len(chunks) - 1, self.current_page * PAGE_SIZE)
            chunk = chunks[index]
            position = float(chunk["start"])

        self.current_play_chunk_id = chunk["id"]
        self.play_start = max(0.0, float(chunk["start"]))
        self.play_end = min(self.duration, float(chunk["end"]))
        self.loop_playback = True
        # Clamp only if the playhead is outside the chosen fragment.
        if not (self.play_start <= position < self.play_end):
            position = self.play_start
        self.playhead_seconds = position
        self.player.setPosition(int(position * 1000))
        self.player.play()
        self.play_timer.start()
        self._update_playhead_indicators(position * 1000)

    def _focused_fragment_id(self) -> str | None:
        widget = QApplication.focusWidget()
        while widget is not None and widget is not self:
            if isinstance(widget, FragmentCard):
                return widget.chunk_id
            widget = widget.parentWidget()
        return None

    def merge_next_shortcut(self) -> bool:
        """Merge the focused fragment with its next neighbor, or use the playhead target."""
        if not self.data:
            return False
        chunks = active_chunks(self.data)
        page_start = self.current_page * PAGE_SIZE
        page_chunks = chunks[page_start:page_start + PAGE_SIZE]
        visible_ids = {chunk["id"] for chunk in page_chunks}

        target_id = self._focused_fragment_id()
        if target_id not in visible_ids:
            target_id = None
        if target_id is None:
            position = self.playhead_seconds
            target = next((chunk for chunk in page_chunks
                           if float(chunk["start"]) <= position <= float(chunk["end"])), None)
            if target is not None:
                target_id = target["id"]
        if target_id is None and self.current_play_chunk_id in visible_ids:
            target_id = self.current_play_chunk_id
        if target_id is None:
            return False
        self.merge_with_next(target_id)
        return True

    def split_at_playhead_shortcut(self) -> bool:
        """Split the focused card, or the visible fragment under the playhead."""
        if not self.data:
            return False
        chunks = active_chunks(self.data)
        page_start = self.current_page * PAGE_SIZE
        page_chunks = chunks[page_start:page_start + PAGE_SIZE]
        visible_ids = {chunk["id"] for chunk in page_chunks}

        # A focused card takes priority, which makes S work naturally after
        # interacting with that card's controls without changing the playhead.
        target_id = self._focused_fragment_id()
        if target_id not in visible_ids:
            target_id = None

        # Otherwise split the visible fragment currently under the playhead.
        if target_id is None:
            position = self.playhead_seconds
            target = next((chunk for chunk in page_chunks
                           if float(chunk["start"]) <= position <= float(chunk["end"])), None)
            if target is not None:
                target_id = target["id"]

        # Fall back to the active playback fragment, but only when it is on
        # the page the user is currently reviewing.
        if target_id is None and self.current_play_chunk_id in visible_ids:
            target_id = self.current_play_chunk_id

        if target_id is None:
            return False
        self.split_chunk(target_id)
        return True

    def eventFilter(self, watched, event):
        belongs_to_window = isinstance(watched, QWidget) and (watched is self or self.isAncestorOf(watched))
        if belongs_to_window and QApplication.activeWindow() is self and event.type() == QEvent.Type.KeyPress:
            focus = QApplication.focusWidget()
            modifiers = event.modifiers()
            command_modifier = Qt.KeyboardModifier.ControlModifier
            has_command = bool(modifiers & command_modifier)
            has_alt_or_shift = bool(modifiers & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier))
            editable_focus = isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox))

            # Save is available from every tab, including while a text field is focused.
            if event.key() == Qt.Key.Key_S and has_command and not has_alt_or_shift:
                self.save_current_project(show_message=True)
                return True

            if self.tabs.currentWidget() is self.proof_tab:
                no_command_modifier = not (modifiers & (
                    Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier |
                    Qt.KeyboardModifier.MetaModifier
                ))
                if has_command and not has_alt_or_shift and event.key() == Qt.Key.Key_Z:
                    # Keep the text editor's native Undo behavior when editing text.
                    if editable_focus:
                        return False
                    self.undo_edit()
                    return True
                if has_command and not has_alt_or_shift and event.key() == Qt.Key.Key_M:
                    # Ctrl/Cmd+M merges the focused fragment with its next neighbor.
                    # It remains available while a fragment's corrected text has focus,
                    # but does not hijack unrelated text fields (e.g. tag-name input).
                    if editable_focus and self._focused_fragment_id() is None:
                        return False
                    if self.merge_next_shortcut():
                        return True
                if event.key() == Qt.Key.Key_S and no_command_modifier:
                    # Do not steal the letter from editable fields.
                    if editable_focus:
                        return False
                    if self.split_at_playhead_shortcut():
                        return True
                elif event.key() == Qt.Key.Key_Space and no_command_modifier:
                    # Preserve typing spaces and native keyboard control behavior.
                    if isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox,
                                          QPushButton, QCheckBox, QToolButton, QComboBox)):
                        return False
                    self.toggle_playback()
                    return True
        return super().eventFilter(watched, event)

    def stop_playback(self):
        # Pause instead of resetting the media position so the playhead remains where it stopped.
        self.player.pause()
        self.play_timer.stop()

    def choose_export_dir(self):
        path = QFileDialog.getExistingDirectory(self, self.tr("choose_folder"), self.export_dir_edit.text())
        if path:
            self.export_dir_edit.setText(path)

    def run_export(self):
        if not self.data or not self.project_dir:
            QMessageBox.warning(self, self.tr("export"), "Load or create a project first.")
            return
        user_path = self.export_dir_edit.text().strip()
        if not user_path:
            user_path = str(self.project_dir / "result")
        export_dir = Path(user_path).expanduser()
        project_resolved = self.project_dir.resolve()
        target_resolved = export_dir.resolve()
        # Never allow an export target to replace the project itself or one of its parents.
        if target_resolved == project_resolved or project_resolved.is_relative_to(target_resolved):
            QMessageBox.warning(self, self.tr("export"),
                                "The export folder cannot be the project folder or a parent of it.")
            return
        if export_dir.exists() and not export_dir.is_dir():
            QMessageBox.warning(self, self.tr("export"), "The selected export path exists and is not a folder.")
            return
        if export_dir.exists():
            answer = QMessageBox.question(
                self, self.tr("export"), self.tr("confirm_replace_export"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            self.save_current_project()
            if export_dir.exists():
                move_project_to_trash(export_dir)
                self.log(f"Moved previous export folder to system Trash: {export_dir}")
            export_dir.mkdir(parents=True, exist_ok=True)
            result_dir = export_project(self.data, self.project_dir, export_dir,
                                        numbered=self.numbered_check.isChecked(),
                                        make_zip=self.zip_check.isChecked(), log_cb=self.log)
            self._export_dir = result_dir
            self.data["phase"] = "exported"
            save_project(self.project_dir, self.data)
            self.export_summary.setText(f"{self.tr('export_done')}\n{result_dir}")
            self.log(self.tr("export_done"))
            answer = QMessageBox.information(self, self.tr("export"),
                f"{self.tr('export_done')}\n\n{result_dir}\n\nOpen folder?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if answer == QMessageBox.StandardButton.Yes:
                self.open_export_dir()
        except Exception as exc:
            QMessageBox.critical(self, self.tr("export"), str(exc))
            self.log(f"ERROR exporting: {exc}")

    def open_export_dir(self):
        if self._export_dir and self._export_dir.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._export_dir.resolve())))
        elif self.project_dir and self.project_dir.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.project_dir.resolve())))

    def closeEvent(self, event):
        self.stop_playback()
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, self.tr("title"), "Transcription is still running. Wait for it to finish before closing.")
            event.ignore()
            return
        self.save_current_project()
        event.accept()


def run_app():
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Speech Extractor")
    app.setWindowIcon(QIcon("resources/icon.ico"))
    window = MainWindow()
    window.show()
    return app.exec()
