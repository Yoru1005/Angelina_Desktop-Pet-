from __future__ import annotations

import ctypes
import json
import os
import random
import sys
import tempfile
import urllib.error
import urllib.request
import winreg
from pathlib import Path

from PySide6.QtCore import QPoint, QLockFile, QThread, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QIcon, QMouseEvent, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)


BASE_SIZE = 380
MIN_SCALE = 0.5
MAX_SCALE = 1.5
APP_NAME = "Angelina 桌寵"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "AngelinaDesktopPet"
HISTORY_LIMIT = 200
SAYINGS = (
    "博士，今天也要記得休息喔。",
    "需要我陪你一起工作嗎？",
    "風很舒服呢。",
    "我會一直待在這裡陪你的。",
)


def resource_path(name: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name


def writable_root() -> Path:
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


ROOT = writable_root()
SETTINGS_PATH = ROOT / "settings.json"
HISTORY_PATH = ROOT / "chat_history.json"
DEFAULT_SETTINGS = {
    "scale": 1.0,
    "topmost": True,
    "locked": False,
    "mode": "fixed",
    "auto_hide_fullscreen": False,
    "startup": False,
    "pos_x": None,
    "pos_y": None,
    "chat_enabled": False,
    "chat_base_url": "https://api.openai.com/v1",
    "chat_api_key": "",
    "chat_model": "",
    "subtitle_size": 14,
}


def load_json(path: Path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except (OSError, ValueError, TypeError):
        return default


def save_json(path: Path, data) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{executable}" "{Path(__file__).resolve()}"'


def set_startup(enabled: bool) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, startup_command())
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


class ChatWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, base_url: str, api_key: str, model: str, messages: list[dict]) -> None:
        super().__init__()
        self.base_url, self.api_key, self.model = base_url, api_key, model
        self.messages = messages

    def run(self) -> None:
        try:
            url = self.base_url.rstrip("/") + "/chat/completions"
            body = json.dumps({"model": self.model, "messages": self.messages}).encode()
            request = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
            self.completed.emit(str(data["choices"][0]["message"]["content"]).strip())
        except (OSError, ValueError, KeyError, IndexError, urllib.error.URLError) as exc:
            self.failed.emit(str(exc))


class Subtitle(QWidget):
    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self.label)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def display(self, text: str, size: int, milliseconds: int = 8000) -> None:
        self.label.setText(text)
        self.label.setStyleSheet(
            f"QLabel {{ color:#392c34; background:rgba(255,250,252,235); border:1px solid #d9a8b7; "
            f"border-radius:12px; padding:8px; font-size:{size}px; }}"
        )
        self.setFixedWidth(340)
        self.adjustSize()
        self.show()
        self.raise_()
        self.timer.start(milliseconds)


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("桌寵設定")
        self.enabled = QCheckBox("啟用聊天")
        self.enabled.setChecked(bool(settings["chat_enabled"]))
        self.base_url = QLineEdit(str(settings["chat_base_url"]))
        self.api_key = QLineEdit(str(settings["chat_api_key"]))
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.model = QLineEdit(str(settings["chat_model"]))
        self.subtitle_size = QSpinBox()
        self.subtitle_size.setRange(10, 30)
        self.subtitle_size.setValue(int(settings["subtitle_size"]))
        form = QFormLayout()
        form.addRow(self.enabled)
        form.addRow("API 網址", self.base_url)
        form.addRow("API 金鑰", self.api_key)
        form.addRow("模型", self.model)
        form.addRow("字幕大小", self.subtitle_size)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("API 金鑰只會儲存在本機 settings.json，請勿提交到 Git。"))
        layout.addWidget(buttons)

    def values(self) -> dict:
        return {
            "chat_enabled": self.enabled.isChecked(),
            "chat_base_url": self.base_url.text().strip(),
            "chat_api_key": self.api_key.text().strip(),
            "chat_model": self.model.text().strip(),
            "subtitle_size": self.subtitle_size.value(),
        }


class ChatDialog(QDialog):
    submitted = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("和 Angelina 聊天")
        self.input = QLineEdit()
        self.input.setPlaceholderText("輸入訊息……")
        button = QPushButton("傳送")
        button.clicked.connect(self.submit)
        self.input.returnPressed.connect(self.submit)
        row = QHBoxLayout(self)
        row.addWidget(self.input)
        row.addWidget(button)
        self.resize(430, 70)

    def submit(self) -> None:
        text = self.input.text().strip()
        if text:
            self.input.clear()
            self.submitted.emit(text)


class AngelinaPet(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.assets = resource_path("assets")
        self.actions = json.loads((self.assets / "manifest.json").read_text(encoding="utf-8"))
        self.settings = dict(DEFAULT_SETTINGS)
        loaded = load_json(SETTINGS_PATH, {})
        if isinstance(loaded, dict):
            self.settings.update(loaded)
        self.history = load_json(HISTORY_PATH, [])
        if not isinstance(self.history, list):
            self.history = []

        self.action_index = self.frame_index = self.loops = 0
        self.scale_factor = float(self.settings["scale"])
        self.topmost = bool(self.settings["topmost"])
        self.locked = bool(self.settings["locked"])
        self.mode = str(self.settings["mode"])
        self.auto_hide_fullscreen = bool(self.settings["auto_hide_fullscreen"])
        self.switch_after_loops = random.randint(2, 4)
        self.frames: list[QPixmap] = []
        self.drag_offset: QPoint | None = None
        self.roam_target: QPoint | None = None
        self.chat_worker: ChatWorker | None = None
        self.chat_dialog: ChatDialog | None = None
        self.subtitle = Subtitle()

        self.setWindowTitle(APP_NAME)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(self.window_flags())
        self.setMouseTracking(True)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.advance_frame)
        self.roam_timer = QTimer(self)
        self.roam_timer.setInterval(35)
        self.roam_timer.timeout.connect(self.roam_step)
        self.roam_schedule = QTimer(self)
        self.roam_schedule.setSingleShot(True)
        self.roam_schedule.timeout.connect(self.start_roam)
        self.fullscreen_timer = QTimer(self)
        self.fullscreen_timer.setInterval(1500)
        self.fullscreen_timer.timeout.connect(self.check_fullscreen)
        self.fullscreen_timer.start()
        self.speech_timer = QTimer(self)
        self.speech_timer.setSingleShot(True)
        self.speech_timer.timeout.connect(self.proactive_speech)

        self.load_frames()
        self.update_size()
        self.restore_position()
        self.show_frame()
        self.setup_tray()
        self.schedule_roam()
        self.schedule_speech()

    def window_flags(self):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowSystemMenuHint
        return flags | Qt.WindowType.WindowStaysOnTopHint if self.topmost else flags

    def restore_position(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x, y = self.settings.get("pos_x"), self.settings.get("pos_y")
        if isinstance(x, int) and isinstance(y, int):
            self.move(x, y)
        else:
            self.move(screen.right() - self.width() - 30, screen.bottom() - self.height() - 30)
        self.clamp_to_screen()

    def load_frames(self) -> None:
        action = self.actions[self.action_index]
        folder = self.assets / action["id"]
        self.frames = [QPixmap(str(folder / f"{i:04d}.png")) for i in range(action["frames"])]
        if not self.frames or any(frame.isNull() for frame in self.frames):
            raise RuntimeError(f"無法載入動畫素材：{folder}")

    def set_action(self, index: int) -> None:
        self.timer.stop()
        self.action_index, self.frame_index, self.loops = index, 0, 0
        self.switch_after_loops = random.randint(2, 4)
        self.load_frames()
        self.show_frame()

    def next_action(self) -> None:
        choices = [i for i in range(len(self.actions)) if i != self.action_index]
        if choices:
            self.set_action(random.choice(choices))

    def update_size(self) -> None:
        size = max(1, int(BASE_SIZE * self.scale_factor))
        self.setFixedSize(size, size)

    def show_frame(self) -> None:
        frame = self.frames[self.frame_index]
        self.current_pixmap = frame.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.update()
        self.position_subtitle()
        self.timer.start(max(1, int(self.actions[self.action_index]["durations"][self.frame_index])))

    def advance_frame(self) -> None:
        self.frame_index += 1
        if self.frame_index >= len(self.frames):
            self.frame_index = 0
            self.loops += 1
            if self.loops >= self.switch_after_loops:
                self.next_action()
                return
        self.show_frame()

    def resize_pet(self, delta: float) -> None:
        self.scale_factor = max(MIN_SCALE, min(MAX_SCALE, round(self.scale_factor + delta, 1)))
        self.settings["scale"] = self.scale_factor
        self.update_size()
        self.clamp_to_screen()
        self.show_frame()
        self.save_settings()

    def set_topmost(self, enabled: bool) -> None:
        position = self.pos()
        self.topmost = enabled
        self.settings["topmost"] = enabled
        self.setWindowFlags(self.window_flags())
        self.move(position)
        self.show()
        self.save_settings()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(0, 0, self.current_pixmap)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self.locked:
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            self.position_subtitle()
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = None
            self.clamp_to_screen()
            self.save_position()
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.enter_chat()
            else:
                self.next_action()
            event.accept()

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.resize_pet(0.1 if event.angleDelta().y() > 0 else -0.1)
        event.accept()

    def contextMenuEvent(self, event) -> None:
        self.timer.stop()
        menu = QMenu(self)
        action_menu = menu.addMenu("切換動作")
        group = QActionGroup(action_menu)
        group.setExclusive(True)
        for index, item in enumerate(self.actions):
            action = QAction(item["name"], group)
            action.setCheckable(True)
            action.setChecked(index == self.action_index)
            action.triggered.connect(lambda _checked=False, i=index: self.set_action(i))
            action_menu.addAction(action)
        menu.addAction("隨機動作", self.next_action)
        menu.addSeparator()
        mode_menu = menu.addMenu("形態")
        fixed = mode_menu.addAction("固定形態", lambda: self.set_mode("fixed"))
        free = mode_menu.addAction("自由移動形態", lambda: self.set_mode("free"))
        fixed.setCheckable(True); free.setCheckable(True)
        fixed.setChecked(self.mode == "fixed"); free.setChecked(self.mode == "free")
        chat_menu = menu.addMenu("聊天")
        chat_menu.addAction("開始聊天", self.enter_chat)
        chat_menu.addAction("歷史對話", self.show_history)
        chat_menu.addAction("聊天設定…", self.open_settings)
        menu.addSeparator()
        menu.addAction("放大桌寵", lambda: self.resize_pet(0.1))
        menu.addAction("縮小桌寵", lambda: self.resize_pet(-0.1))
        lock = menu.addAction("解除拖曳鎖定" if self.locked else "鎖定拖曳", self.toggle_lock)
        top = menu.addAction("永遠置頂")
        top.setCheckable(True); top.setChecked(self.topmost); top.toggled.connect(self.set_topmost)
        fullscreen = menu.addAction("全螢幕時自動隱藏", self.toggle_fullscreen)
        fullscreen.setCheckable(True); fullscreen.setChecked(self.auto_hide_fullscreen)
        startup = menu.addAction("開機自動啟動", self.toggle_startup)
        startup.setCheckable(True); startup.setChecked(bool(self.settings["startup"]))
        menu.addAction("設定…", self.open_settings)
        menu.addSeparator()
        menu.addAction("退出桌寵", self.quit_pet)
        menu.exec(event.globalPos())
        if not self.timer.isActive():
            self.show_frame()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.settings["mode"] = mode
        if mode == "fixed":
            self.roam_timer.stop()
            self.roam_schedule.stop()
        else:
            self.schedule_roam(1000)
        self.save_settings()

    def schedule_roam(self, delay: int | None = None) -> None:
        if self.mode == "free":
            self.roam_schedule.start(delay or random.randint(8000, 20000))

    def start_roam(self) -> None:
        if self.mode != "free" or self.locked:
            self.schedule_roam()
            return
        screen = self.screen().availableGeometry()
        self.roam_target = QPoint(
            random.randint(screen.left(), max(screen.left(), screen.right() - self.width())),
            random.randint(screen.top(), max(screen.top(), screen.bottom() - self.height())),
        )
        self.roam_timer.start()

    def roam_step(self) -> None:
        if self.roam_target is None or self.mode != "free":
            self.roam_timer.stop()
            return
        delta = self.roam_target - self.pos()
        distance = abs(delta.x()) + abs(delta.y())
        if distance < 12:
            self.move(self.roam_target)
            self.roam_target = None
            self.roam_timer.stop()
            self.save_position()
            self.schedule_roam()
            return
        self.move(self.x() + max(-6, min(6, delta.x())), self.y() + max(-6, min(6, delta.y())))
        self.position_subtitle()

    def clamp_to_screen(self) -> None:
        screen = self.screen().availableGeometry()
        self.move(max(screen.left(), min(self.x(), screen.right() - self.width())), max(screen.top(), min(self.y(), screen.bottom() - self.height())))

    def toggle_lock(self) -> None:
        self.locked = not self.locked
        self.settings["locked"] = self.locked
        self.save_settings()

    def toggle_fullscreen(self, enabled: bool) -> None:
        self.auto_hide_fullscreen = enabled
        self.settings["auto_hide_fullscreen"] = enabled
        self.save_settings()

    def check_fullscreen(self) -> None:
        if not self.auto_hide_fullscreen:
            if not self.isVisible(): self.show()
            return
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        fullscreen = bool(hwnd and ctypes.windll.user32.IsZoomed(hwnd))
        self.setVisible(not fullscreen)

    def toggle_startup(self, enabled: bool) -> None:
        if set_startup(enabled):
            self.settings["startup"] = enabled
            self.save_settings()
        else:
            QMessageBox.warning(self, APP_NAME, "設定開機自動啟動失敗。")

    def setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        icon = QIcon(self.frames[0])
        self.tray = QSystemTrayIcon(icon, self)
        tray_menu = QMenu()
        tray_menu.addAction("顯示／隱藏", lambda: self.setVisible(not self.isVisible()))
        startup = tray_menu.addAction("開機自動啟動")
        startup.setCheckable(True); startup.setChecked(bool(self.settings["startup"])); startup.toggled.connect(self.toggle_startup)
        tray_menu.addSeparator()
        tray_menu.addAction("關閉", self.quit_pet)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(lambda reason: self.setVisible(not self.isVisible()) if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings.update(dialog.values())
            self.save_settings()

    def enter_chat(self) -> None:
        if not self.settings["chat_enabled"] or not self.settings["chat_api_key"] or not self.settings["chat_model"]:
            QMessageBox.information(self, APP_NAME, "請先在右鍵 → 設定中啟用聊天並填寫 API 資料。")
            return
        if self.chat_dialog is None:
            self.chat_dialog = ChatDialog(self)
            self.chat_dialog.submitted.connect(self.send_chat)
        self.chat_dialog.show(); self.chat_dialog.raise_(); self.chat_dialog.activateWindow()

    def send_chat(self, text: str) -> None:
        if self.chat_worker and self.chat_worker.isRunning():
            return
        messages = [{"role": "system", "content": "你是溫柔的桌寵 Angelina，使用繁體中文簡短回應使用者。"}]
        messages.extend(self.history[-20:])
        messages.append({"role": "user", "content": text})
        self.subtitle_text("思考中……", 60000)
        self.chat_worker = ChatWorker(str(self.settings["chat_base_url"]), str(self.settings["chat_api_key"]), str(self.settings["chat_model"]), messages)
        self.chat_worker.completed.connect(lambda reply: self.finish_chat(text, reply))
        self.chat_worker.failed.connect(lambda error: self.subtitle_text(f"連線失敗：{error}", 10000))
        self.chat_worker.start()

    def finish_chat(self, user_text: str, reply: str) -> None:
        self.history.extend(({"role": "user", "content": user_text}, {"role": "assistant", "content": reply}))
        self.history = self.history[-HISTORY_LIMIT:]
        save_json(HISTORY_PATH, self.history)
        self.subtitle_text(reply, 15000)

    def show_history(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("歷史對話")
        text = QPlainTextEdit(); text.setReadOnly(True)
        text.setPlainText("\n\n".join(("你：" if item.get("role") == "user" else "Angelina：") + str(item.get("content", "")) for item in self.history) or "尚無歷史對話。")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(dialog.reject)
        layout = QVBoxLayout(dialog); layout.addWidget(text); layout.addWidget(buttons)
        dialog.resize(520, 420); dialog.exec()

    def subtitle_text(self, text: str, milliseconds: int = 8000) -> None:
        self.subtitle.display(text, int(self.settings["subtitle_size"]), milliseconds)
        self.position_subtitle()

    def position_subtitle(self) -> None:
        if self.subtitle.isVisible():
            self.subtitle.move(self.x() + (self.width() - self.subtitle.width()) // 2, self.y() - self.subtitle.height() - 8)

    def schedule_speech(self) -> None:
        self.speech_timer.start(random.randint(45000, 90000))

    def proactive_speech(self) -> None:
        self.subtitle_text(random.choice(SAYINGS))
        self.schedule_speech()

    def save_settings(self) -> None:
        save_json(SETTINGS_PATH, self.settings)

    def save_position(self) -> None:
        self.settings["pos_x"], self.settings["pos_y"] = self.x(), self.y()
        self.save_settings()

    def closeEvent(self, event) -> None:
        self.save_position()
        event.accept()

    def quit_pet(self) -> None:
        self.save_position()
        QApplication.instance().quit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    lock = QLockFile(str(Path(tempfile.gettempdir()) / "angelina-desktop-pet.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, APP_NAME, "桌寵已經在執行了。")
        return 0
    pet = AngelinaPet()
    pet.show()
    result = app.exec()
    lock.unlock()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
