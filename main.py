"""
Quadrant Ranking - PySide6
A desktop application that visualizes items on a 2D quadrant (x and y axes, each -100..100).

Features:
- Add entries with an image and a name (images are copied into ./data/images)
- Show entries on a quadrant canvas (map -100..100 to canvas coordinates)
- Drag entries around to update their x/y values
- Edit entry details (name, x, y) via dialog
- View entry detail (larger image and info)
- Delete entries
- Axis settings: set axis names and left/right (or top/bottom) side labels
- Save/load entries to data/entries.json automatically

Dependencies:
- PySide6

Run: python quadrant_ranking.py
"""

import sys
import os
import json
import shutil
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QHBoxLayout, QVBoxLayout, QSplitter, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QDialog, QFormLayout, QLineEdit, QSpinBox, QMessageBox,
    QGroupBox, QGridLayout
)
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtCore import Qt, QRectF

DATA_DIR = 'data'
IMAGES_DIR = os.path.join(DATA_DIR, 'images')
ENTRIES_FILE = os.path.join(DATA_DIR, 'entries.json')

os.makedirs(IMAGES_DIR, exist_ok=True)


def clamp(val, a, b):
    return max(a, min(b, val))


class Entry:
    def __init__(self, id_, name, image_path, x=0, y=0):
        self.id = id_
        self.name = name
        self.image_path = image_path
        self.x = x  # -100..100
        self.y = y  # -100..100

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'image_path': self.image_path,
            'x': self.x,
            'y': self.y
        }

    @staticmethod
    def from_dict(d):
        return Entry(d['id'], d['name'], d['image_path'], d.get('x', 0), d.get('y', 0))


class EntryDialog(QDialog):
    def __init__(self, parent=None, entry: Entry=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle('Entry Details')
        self.setup_ui()

    def setup_ui(self):
        form = QFormLayout(self)
        self.name_edit = QLineEdit(self)
        self.x_spin = QSpinBox(self)
        self.x_spin.setRange(-100, 100)
        self.y_spin = QSpinBox(self)
        self.y_spin.setRange(-100, 100)

        if self.entry:
            self.name_edit.setText(self.entry.name)
            self.x_spin.setValue(self.entry.x)
            self.y_spin.setValue(self.entry.y)

        form.addRow('Name:', self.name_edit)
        form.addRow('X (-100..100):', self.x_spin)
        form.addRow('Y (-100..100):', self.y_spin)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton('Save')
        cancel_btn = QPushButton('Cancel')
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        form.addRow(btn_layout)

    def get_values(self):
        return self.name_edit.text(), self.x_spin.value(), self.y_spin.value()


class AxisSettingsWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__('Axis Settings')
        self.setup_ui()

    def setup_ui(self):
        layout = QGridLayout(self)
        self.x_axis_name = QLineEdit('X Axis')
        self.x_left_label = QLineEdit('Left')
        self.x_right_label = QLineEdit('Right')
        self.y_axis_name = QLineEdit('Y Axis')
        self.y_top_label = QLineEdit('Top')
        self.y_bottom_label = QLineEdit('Bottom')

        layout.addWidget(QLabel('X axis name:'), 0, 0)
        layout.addWidget(self.x_axis_name, 0, 1)
        layout.addWidget(QLabel('Left side label:'), 1, 0)
        layout.addWidget(self.x_left_label, 1, 1)
        layout.addWidget(QLabel('Right side label:'), 2, 0)
        layout.addWidget(self.x_right_label, 2, 1)

        layout.addWidget(QLabel('Y axis name:'), 3, 0)
        layout.addWidget(self.y_axis_name, 3, 1)
        layout.addWidget(QLabel('Top label:'), 4, 0)
        layout.addWidget(self.y_top_label, 4, 1)
        layout.addWidget(QLabel('Bottom label:'), 5, 0)
        layout.addWidget(self.y_bottom_label, 5, 1)


class DraggablePixmapItem(QGraphicsPixmapItem):
    def __init__(self, entry: Entry, pixmap: QPixmap):
        super().__init__(pixmap)
        self.entry = entry
        self.setFlags(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable | QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        view = self.scene().views()[0]
        if hasattr(view, 'widget'):
            widget = view.widget
            widget.update_entry_from_item(self)


class QuadrantView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget = parent
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.margin = 40
        self.items_map = {}
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.draw_axes()
        self.refresh_items_positions()

    def draw_axes(self):
        self.scene.clear()
        w = self.viewport().width()
        h = self.viewport().height()
        center_x = w / 2
        center_y = h / 2
        self.scene.setSceneRect(0, 0, w, h)
        self.scene.addLine(center_x, 0, center_x, h)
        self.scene.addLine(0, center_y, w, center_y)

        asw = self.widget.axis_settings
        self.scene.addText(asw.x_axis_name.text()).setPos(center_x - 30, h - 30)
        self.scene.addText(asw.x_left_label.text()).setPos(5, center_y - 10)
        self.scene.addText(asw.x_right_label.text()).setPos(w - 80, center_y - 10)
        self.scene.addText(asw.y_axis_name.text()).setPos(5, 5)
        self.scene.addText(asw.y_top_label.text()).setPos(center_x + 10, 5)
        self.scene.addText(asw.y_bottom_label.text()).setPos(center_x + 10, h - 40)

    def map_value_to_pos(self, x_val, y_val):
        w = self.viewport().width()
        h = self.viewport().height()
        center_x = w / 2
        center_y = h / 2
        x = center_x + (x_val / 100.0) * (center_x - self.margin)
        y = center_y - (y_val / 100.0) * (center_y - self.margin)
        return x, y

    def map_pos_to_value(self, x, y):
        w = self.viewport().width()
        h = self.viewport().height()
        center_x = w / 2
        center_y = h / 2
        x_val = ((x - center_x) / (center_x - self.margin)) * 100.0
        y_val = ((center_y - y) / (center_y - self.margin)) * 100.0
        x_val = clamp(int(round(x_val)), -100, 100)
        y_val = clamp(int(round(y_val)), -100, 100)
        return x_val, y_val

    def add_or_update_item(self, entry: Entry):
        pix = QPixmap(entry.image_path)
        pix = pix.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        if entry.id in self.items_map:
            item = self.items_map[entry.id]
            item.setPixmap(pix)
        else:
            item = DraggablePixmapItem(entry, pix)
            self.scene.addItem(item)
            self.items_map[entry.id] = item
        x, y = self.map_value_to_pos(entry.x, entry.y)
        item.setPos(x - pix.width() / 2, y - pix.height() / 2)

    def remove_item(self, entry_id):
        if entry_id in self.items_map:
            it = self.items_map.pop(entry_id)
            self.scene.removeItem(it)

    def refresh_items_positions(self):
        for entry_id, item in list(self.items_map.items()):
            entry = item.entry
            x, y = self.map_value_to_pos(entry.x, entry.y)
            item.setPos(x - item.pixmap().width() / 2, y - item.pixmap().height() / 2)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Quadrant Ranking')
        self.entries = {}
        self.next_id = 1
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        left = QWidget()
        left_layout = QVBoxLayout(left)

        add_btn = QPushButton('Add Entry')
        add_btn.clicked.connect(self.add_entry)
        left_layout.addWidget(add_btn)

        self.entries_list = QListWidget()
        self.entries_list.itemDoubleClicked.connect(self.open_entry_dialog_from_list)
        left_layout.addWidget(self.entries_list)

        edit_btn = QPushButton('Edit Selected')
        edit_btn.clicked.connect(self.edit_selected)
        del_btn = QPushButton('Delete Selected')
        del_btn.clicked.connect(self.delete_selected)
        left_layout.addWidget(edit_btn)
        left_layout.addWidget(del_btn)

        self.axis_settings = AxisSettingsWidget(self)
        left_layout.addWidget(self.axis_settings)

        save_btn = QPushButton('Save Now')
        save_btn.clicked.connect(self.save_data)
        left_layout.addWidget(save_btn)
        left_layout.addStretch()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.quad_view = QuadrantView(self)
        right_layout.addWidget(self.quad_view)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([300, 600])

        layout.addWidget(splitter)
        self.setLayout(layout)

    def add_entry(self):
        fn, _ = QFileDialog.getOpenFileName(self, 'Select image', '', 'Images (*.png *.jpg *.jpeg *.bmp *.gif)')
        if not fn:
            return
        base = os.path.basename(fn)
        dest = os.path.join(IMAGES_DIR, f"{self.next_id}_{base}")
        try:
            shutil.copyfile(fn, dest)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to copy image: {e}')
            return
        entry_name = os.path.splitext(base)[0]
        entry = Entry(self.next_id, entry_name, dest, x=0, y=0)
        self.entries[entry.id] = entry
        self.next_id += 1
        self.add_entry_to_list(entry)
        self.quad_view.add_or_update_item(entry)
        self.save_data()

    def add_entry_to_list(self, entry: Entry):
        item = QListWidgetItem(f"{entry.name} (x={entry.x}, y={entry.y})")
        item.setData(Qt.ItemDataRole.UserRole, entry.id)
        pix = QPixmap(entry.image_path).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        item.setIcon(pix)
        self.entries_list.addItem(item)

    def refresh_list(self):
        self.entries_list.clear()
        for entry in self.entries.values():
            self.add_entry_to_list(entry)

    def find_selected_entry_id(self):
        it = self.entries_list.currentItem()
        if not it:
            return None
        return it.data(Qt.ItemDataRole.UserRole)

    def edit_selected(self):
        eid = self.find_selected_entry_id()
        if eid is None:
            QMessageBox.information(self, 'Info', 'Select an entry first')
            return
        entry = self.entries[eid]
        dlg = EntryDialog(self, entry)
        if dlg.exec():
            name, x, y = dlg.get_values()
            entry.name = name
            entry.x = x
            entry.y = y
            self.quad_view.add_or_update_item(entry)
            self.refresh_list()
            self.save_data()

    def delete_selected(self):
        eid = self.find_selected_entry_id()
        if eid is None:
            QMessageBox.information(self, 'Info', 'Select an entry first')
            return
        reply = QMessageBox.question(self, 'Delete', 'Delete selected entry?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            entry = self.entries.pop(eid, None)
            if entry:
                try:
                    os.remove(entry.image_path)
                except Exception:
                    pass
                self.quad_view.remove_item(eid)
                self.refresh_list()
                self.save_data()

    def open_entry_dialog_from_list(self, list_item: QListWidgetItem):
        eid = list_item.data(Qt.ItemDataRole.UserRole)
        entry = self.entries[eid]
        dlg = EntryDialog(self, entry)
        if dlg.exec():
            name, x, y = dlg.get_values()
            entry.name = name
            entry.x = x
            entry.y = y
            self.quad_view.add_or_update_item(entry)
            self.refresh_list()
            self.save_data()

    def update_entry_from_item(self, item: DraggablePixmapItem):
        pos = item.pos()
        center_x = pos.x() + item.pixmap().width() / 2
        center_y = pos.y() + item.pixmap().height() / 2
        x_val, y_val = self.quad_view.map_pos_to_value(center_x, center_y)
        entry = item.entry
        entry.x = x_val
        entry.y = y_val
        self.refresh_list()
        self.save_data()

    def save_data(self):
        payload = {
            'next_id': self.next_id,
            'entries': [e.to_dict() for e in self.entries.values()],
            'axis': {
                'x_name': self.axis_settings.x_axis_name.text(),
                'x_left': self.axis_settings.x_left_label.text(),
                'x_right': self.axis_settings.x_right_label.text(),
                'y_name': self.axis_settings.y_axis_name.text(),
                'y_top': self.axis_settings.y_top_label.text(),
                'y_bottom': self.axis_settings.y_bottom_label.text()
            }
        }
        try:
            with open(ENTRIES_FILE, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save data: {e}')

    def load_data(self):
        if not os.path.exists(ENTRIES_FILE):
            return
        try:
            with open(ENTRIES_FILE, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            self.next_id = payload.get('next_id', 1)
            for d in payload.get('entries', []):
                e = Entry.from_dict(d)
                if not os.path.exists(e.image_path):
                    continue
                self.entries[e.id] = e
            axis = payload.get('axis', {})
            if axis:
                self.axis_settings.x_axis_name.setText(axis.get('x_name', 'X Axis'))
                self.axis_settings.x_left_label.setText(axis.get('x_left', 'Left'))
                self.axis_settings.x_right_label.setText(axis.get('x_right', 'Right'))
                self.axis_settings.y_axis_name.setText(axis.get('y_name', 'Y Axis'))
                self.axis_settings.y_top_label.setText(axis.get('y_top', 'Top'))
                self.axis_settings.y_bottom_label.setText(axis.get('y_bottom', 'Bottom'))
            self.refresh_list()
            for e in self.entries.values():
                self.quad_view.add_or_update_item(e)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load data: {e}')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1000, 700)
    w.show()
    sys.exit(app.exec_())