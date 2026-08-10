from __future__ import annotations

import json
import random
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QMouseEvent, QPixmap, QWheelEvent
from PySide6.QtWidgets import QApplication, QMenu, QWidget


BASE_SIZE = 380
MIN_SCALE = 0.5
MAX_SCALE = 1.5


def resource_path(name: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name


class AngelinaPet(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.assets = resource_path("assets")
        self.actions = json.loads(
            (self.assets / "manifest.json").read_text(encoding="utf-8")
        )
        self.action_index = 0
        self.frame_index = 0
        self.loops = 0
        self.scale_factor = 1.0
        self.topmost = True
        self.switch_after_loops = random.randint(2, 4)
        self.frames: list[QPixmap] = []
        self.drag_offset: QPoint | None = None

        self.setWindowTitle("Angelina 桌寵")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(self.window_flags())
        self.setMouseTracking(True)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.advance_frame)

        self.load_frames()
        self.update_size()
        self.move_to_default_position()
        self.show_frame()

    def window_flags(self) -> Qt.WindowType:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowSystemMenuHint
        )
        if self.topmost:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        return flags

    def move_to_default_position(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 30, screen.bottom() - self.height() - 30)

    def load_frames(self) -> None:
        action = self.actions[self.action_index]
        folder = self.assets / action["id"]
        self.frames = [
            QPixmap(str(folder / f"{i:04d}.png")) for i in range(action["frames"])
        ]
        if not self.frames or any(frame.isNull() for frame in self.frames):
            raise RuntimeError(f"無法載入動畫素材：{folder}")

    def set_action(self, index: int) -> None:
        self.timer.stop()
        self.action_index = index
        self.frame_index = 0
        self.loops = 0
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
        scaled = frame.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.current_pixmap = scaled
        self.update()
        duration = self.actions[self.action_index]["durations"][self.frame_index]
        self.timer.start(max(1, int(duration)))

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
        self.scale_factor = max(
            MIN_SCALE, min(MAX_SCALE, round(self.scale_factor + delta, 1))
        )
        self.update_size()
        self.show_frame()

    def set_topmost(self, enabled: bool) -> None:
        position = self.pos()
        self.topmost = enabled
        self.setWindowFlags(self.window_flags())
        self.move(position)
        self.show()

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QPainter

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(0, 0, self.current_pixmap)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = None
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.next_action()
            event.accept()

    def wheelEvent(self, event: QWheelEvent) -> None:
        self.resize_pet(0.1 if event.angleDelta().y() > 0 else -0.1)
        event.accept()

    def contextMenuEvent(self, event) -> None:
        self.timer.stop()
        menu = QMenu(self)
        menu.setFont(QApplication.font())

        action_menu = menu.addMenu("切換動作")
        action_group = QActionGroup(action_menu)
        action_group.setExclusive(True)
        for index, item in enumerate(self.actions):
            action = QAction(item["name"], action_group)
            action.setCheckable(True)
            action.setChecked(index == self.action_index)
            action.triggered.connect(lambda _checked=False, i=index: self.set_action(i))
            action_menu.addAction(action)

        menu.addSeparator()
        menu.addAction("放大桌寵", lambda: self.resize_pet(0.1))
        menu.addAction("縮小桌寵", lambda: self.resize_pet(-0.1))
        topmost_action = menu.addAction("永遠置頂")
        topmost_action.setCheckable(True)
        topmost_action.setChecked(self.topmost)
        topmost_action.toggled.connect(self.set_topmost)

        help_menu = menu.addMenu("操作說明")
        for text in (
            "左鍵拖曳：移動桌寵",
            "滑鼠滾輪：調整大小",
            "雙擊左鍵：隨機切換動作",
            "右鍵：開啟這個選單",
        ):
            info = help_menu.addAction(text)
            info.setEnabled(False)

        menu.addSeparator()
        menu.addAction("退出桌寵", QApplication.instance().quit)

        menu.ensurePolished()
        menu_size = menu.sizeHint()
        screen = self.screen().availableGeometry()
        right_x = self.frameGeometry().right() + 8
        if right_x + menu_size.width() <= screen.right():
            x = right_x
        else:
            x = max(screen.left(), self.frameGeometry().left() - menu_size.width() - 8)
        y = max(screen.top(), min(event.globalPos().y(), screen.bottom() - menu_size.height()))
        menu.exec(QPoint(x, y))
        if not self.timer.isActive():
            self.show_frame()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Angelina 桌寵")
    pet = AngelinaPet()
    pet.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
