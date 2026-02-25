"""
GMD关卡编辑器 - PyQt6 图形界面
支持可视化编辑Geometry Dash关卡plist文件
采用现代化 MVC 架构,支持撤销/重做功能
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeView, QTextEdit, QLineEdit, QComboBox, QPushButton,
    QDockWidget, QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QLabel, QSplitter, QGroupBox, QFormLayout
)
from PyQt6.QtCore import (
    Qt, QSettings, pyqtSignal, QModelIndex, QAbstractItemModel
)
from PyQt6.QtGui import (
    QStandardItemModel, QStandardItem, QAction, QKeySequence,
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QUndoStack, QUndoCommand
)
from utils.gmd_parser import GMDParser


# ==================== 数据模型 ====================
class DataTreeModel(QStandardItemModel):
    """GMD数据树形模型"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalHeaderLabels(['键/索引', '类型', '值'])
        self.data_dict: Optional[Dict[str, Any]] = None
        self.is_gmd2 = False

    def load_data(self, data: Dict[str, Any], is_gmd2: bool = False):
        """加载数据到模型"""
        self.clear()
        self.setHorizontalHeaderLabels(['键/索引', '类型', '值'])
        self.data_dict = data
        self.is_gmd2 = is_gmd2

        if is_gmd2:
            # GMD2格式有多个部分
            if 'level_data' in data:
                self._populate_tree(self.invisibleRootItem(), 'level_data', data['level_data'])
            if 'metadata' in data:
                self._populate_tree(self.invisibleRootItem(), 'metadata', data['metadata'])
        else:
            # 普通GMD/LVL格式
            self._populate_tree(self.invisibleRootItem(), 'root', data)

    def _populate_tree(self, parent: QStandardItem, key: str, value: Any):
        """递归填充树形视图"""
        key_item = QStandardItem(str(key))
        type_item = QStandardItem()
        value_item = QStandardItem()

        if isinstance(value, dict):
            type_item.setText('dict')
            value_item.setText(f'{len(value)} 项')
            parent.appendRow([key_item, type_item, value_item])
            for k, v in value.items():
                self._populate_tree(key_item, k, v)
        elif isinstance(value, list):
            type_item.setText('list')
            value_item.setText(f'{len(value)} 项')
            parent.appendRow([key_item, type_item, value_item])
            for i, v in enumerate(value):
                self._populate_tree(key_item, f'[{i}]', v)
        else:
            # 叶子节点
            type_name = type(value).__name__
            type_item.setText(type_name)
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + '...'
            value_item.setText(value_str)
            parent.appendRow([key_item, type_item, value_item])

    def get_item_path(self, index: QModelIndex) -> List[str]:
        """获取项的完整路径"""
        path = []
        current = index
        while current.isValid():
            key_item = self.itemFromIndex(self.index(current.row(), 0, current.parent()))
            if key_item:
                path.insert(0, key_item.text())
            current = current.parent()
        return path

    def get_value_by_path(self, path: List[str]) -> Any:
        """根据路径获取值"""
        if not self.data_dict or not path:
            return None

        current = self.data_dict
        for part in path:
            if part == 'root':
                continue

            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    return None
            elif isinstance(current, list):
                # 提取索引 [0], [1] 等
                if part.startswith('[') and part.endswith(']'):
                    try:
                        index = int(part[1:-1])
                        current = current[index]
                    except (ValueError, IndexError):
                        return None
                else:
                    return None
            else:
                return None

        return current

    def set_value_by_path(self, path: List[str], value: Any) -> bool:
        """根据路径设置值"""
        if not self.data_dict or not path or len(path) < 2:
            return False

        current = self.data_dict
        for i, part in enumerate(path[:-1]):
            if part == 'root':
                continue

            if isinstance(current, dict):
                if part not in current:
                    return False
                if i == len(path) - 2:
                    # 最后一层的父节点
                    break
                current = current[part]
            elif isinstance(current, list):
                if part.startswith('[') and part.endswith(']'):
                    try:
                        index = int(part[1:-1])
                        if i == len(path) - 2:
                            break
                        current = current[index]
                    except (ValueError, IndexError):
                        return False
                else:
                    return False

        # 设置最终值
        last_key = path[-1]
        if isinstance(current, dict) and last_key in current:
            current[last_key] = value
            return True
        elif isinstance(current, list) and last_key.startswith('[') and last_key.endswith(']'):
            try:
                index = int(last_key[1:-1])
                current[index] = value
                return True
            except (ValueError, IndexError):
                return False

        return False


# ==================== K4 语法高亮 ====================
class K4SyntaxHighlighter(QSyntaxHighlighter):
    """k4 数据语法高亮器"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 定义格式
        self.separator_format = QTextCharFormat()
        self.separator_format.setForeground(QColor("#FF6B6B"))
        self.separator_format.setFontWeight(QFont.Weight.Bold)

        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#4ECDC4"))

        self.key_format = QTextCharFormat()
        self.key_format.setForeground(QColor("#95E1D3"))

    def highlightBlock(self, text: str):
        """高亮显示文本块"""
        # 高亮分隔符 | 和 ;
        for i, char in enumerate(text):
            if char in ('|', ';'):
                self.setFormat(i, 1, self.separator_format)

        # 高亮数字
        import re
        for match in re.finditer(r'\b\d+\.?\d*\b', text):
            self.setFormat(match.start(), match.end() - match.start(), self.number_format)


# ==================== K4 编辑器 ====================
class K4EditorWidget(QWidget):
    """k4 专用编辑器组件"""

    value_changed = pyqtSignal(str)  # 值改变信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_encoded_value = None
        self.is_decoded = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()
        self.toggle_button = QPushButton("显示原始编码")
        self.toggle_button.clicked.connect(self._toggle_view)
        self.toggle_button.setEnabled(False)

        self.format_button = QPushButton("格式化")
        self.format_button.clicked.connect(self._format_k4)
        self.format_button.setEnabled(False)

        toolbar.addWidget(self.toggle_button)
        toolbar.addWidget(self.format_button)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 编辑器
        self.text_edit = QTextEdit()
        self.text_edit.setFont(QFont('Consolas', 10))
        self.text_edit.textChanged.connect(self._on_text_changed)

        # 应用语法高亮
        self.highlighter = K4SyntaxHighlighter(self.text_edit.document())

        layout.addWidget(self.text_edit)

    def load_k4_value(self, encoded_value: str):
        """加载 k4 值并自动解码"""
        self.original_encoded_value = encoded_value

        try:
            # 自动解码
            decoded = GMDParser.decode_k4(encoded_value)
            formatted = self._format_k4_data(decoded)

            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText(formatted)
            self.text_edit.blockSignals(False)

            self.is_decoded = True
            self.toggle_button.setEnabled(True)
            self.toggle_button.setText("显示原始编码")
            self.format_button.setEnabled(True)
        except Exception as e:
            # 解码失败,显示原始值
            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText(encoded_value)
            self.text_edit.blockSignals(False)

            self.is_decoded = False
            self.toggle_button.setEnabled(False)
            self.format_button.setEnabled(False)
            QMessageBox.warning(self, "解码失败", f"无法解码 k4 字段:\n{str(e)}")

    def get_encoded_value(self) -> str:
        """获取编码后的 k4 值"""
        if self.is_decoded:
            # 反格式化并重新编码
            text = self.text_edit.toPlainText()
            unformatted = self._unformat_k4_data(text)
            return GMDParser.encode_k4(unformatted)
        else:
            return self.text_edit.toPlainText()

    def _toggle_view(self):
        """切换显示原始/解码视图"""
        if self.is_decoded:
            # 切换到显示原始编码
            self.text_edit.blockSignals(True)
            self.text_edit.setPlainText(self.original_encoded_value)
            self.text_edit.blockSignals(False)

            self.is_decoded = False
            self.toggle_button.setText("显示解码内容")
            self.format_button.setEnabled(False)
        else:
            # 切换到显示解码内容
            try:
                decoded = GMDParser.decode_k4(self.original_encoded_value)
                formatted = self._format_k4_data(decoded)

                self.text_edit.blockSignals(True)
                self.text_edit.setPlainText(formatted)
                self.text_edit.blockSignals(False)

                self.is_decoded = True
                self.toggle_button.setText("显示原始编码")
                self.format_button.setEnabled(True)
            except Exception as e:
                QMessageBox.warning(self, "解码失败", f"无法解码 k4 字段:\n{str(e)}")

    def _format_k4(self):
        """格式化 k4 数据"""
        if not self.is_decoded:
            return

        text = self.text_edit.toPlainText()
        unformatted = self._unformat_k4_data(text)
        formatted = self._format_k4_data(unformatted)

        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(formatted)
        self.text_edit.blockSignals(False)

    def _format_k4_data(self, data: str) -> str:
        """格式化 k4 数据 (按 | 和 ; 换行)"""
        formatted = data.replace('|', '|\n')
        formatted = formatted.replace(';', ';\n')
        return formatted

    def _unformat_k4_data(self, formatted_data: str) -> str:
        """反格式化 k4 数据 (移除换行)"""
        return formatted_data.replace('\n', '')

    def _on_text_changed(self):
        """文本改变时发出信号"""
        if self.is_decoded:
            try:
                encoded = self.get_encoded_value()
                self.value_changed.emit(encoded)
            except Exception:
                pass


# ==================== 弹出编辑器对话框 ====================
class PopupEditorDialog(QWidget):
    """独立的弹出编辑器窗口"""

    value_accepted = pyqtSignal(str)  # 接受值信号

    def __init__(self, key: str, value_type: str, value: str, is_k4: bool = False, parent=None):
        super().__init__(parent, Qt.WindowType.Window)  # 独立窗口
        self.key = key
        self.value_type = value_type
        self.is_k4 = is_k4

        self.setWindowTitle(f"编辑: {key} ({value_type})")
        self.setGeometry(200, 200, 900, 700)

        self._init_ui(value)

    def _init_ui(self, value: str):
        layout = QVBoxLayout(self)

        # 标题信息
        info_layout = QHBoxLayout()
        info_label = QLabel(f"<b>键:</b> {self.key} &nbsp;&nbsp; <b>类型:</b> {self.value_type}")
        info_layout.addWidget(info_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # 编辑器区域
        if self.is_k4:
            # k4 专用编辑器
            self.editor = K4EditorWidget()
            self.editor.load_k4_value(value)
        else:
            # 普通文本编辑器
            self.editor = QTextEdit()
            self.editor.setFont(QFont('Consolas', 10))
            self.editor.setPlainText(value)

        layout.addWidget(self.editor)

        # 按钮区
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.close)
        button_layout.addWidget(cancel_button)

        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self._accept_value)
        ok_button.setDefault(True)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)

    def _accept_value(self):
        """接受值并关闭"""
        if self.is_k4:
            try:
                value = self.editor.get_encoded_value()
                self.value_accepted.emit(value)
                self.close()
            except Exception as e:
                QMessageBox.critical(self, "编码失败", f"无法编码 k4 字段:\n{str(e)}")
        else:
            value = self.editor.toPlainText()
            self.value_accepted.emit(value)
            self.close()


# ==================== 属性编辑器 ====================
class PropertyEditorWidget(QWidget):
    """属性编辑面板"""

    value_changed = pyqtSignal(str, str, str)  # key, type, value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path: List[str] = []
        self.current_key = ""
        self.current_type = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 路径显示
        path_group = QGroupBox("当前路径")
        path_layout = QVBoxLayout()
        self.path_label = QLabel("未选择")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("padding: 5px;")
        path_layout.addWidget(self.path_label)
        path_group.setLayout(path_layout)
        layout.addWidget(path_group)

        # 编辑区域
        edit_group = QGroupBox("属性编辑")
        form_layout = QFormLayout()

        self.key_edit = QLineEdit()
        self.key_edit.setReadOnly(True)
        form_layout.addRow("键:", self.key_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(['str', 'int', 'float', 'bool', 'dict', 'list'])
        self.type_combo.setEnabled(False)
        form_layout.addRow("类型:", self.type_combo)

        edit_group.setLayout(form_layout)
        layout.addWidget(edit_group)

        # 值编辑区
        value_group = QGroupBox("值")
        value_layout = QVBoxLayout()

        # 普通值编辑器
        self.value_edit = QTextEdit()
        self.value_edit.setMinimumHeight(300)
        value_layout.addWidget(self.value_edit)

        # k4 专用编辑器
        self.k4_editor = K4EditorWidget()
        self.k4_editor.hide()
        self.k4_editor.value_changed.connect(self._on_k4_value_changed)
        value_layout.addWidget(self.k4_editor)

        value_group.setLayout(value_layout)
        layout.addWidget(value_group)

        # 按钮
        button_layout = QHBoxLayout()

        self.popup_button = QPushButton("弹出编辑器")
        self.popup_button.clicked.connect(self._open_popup_editor)
        button_layout.addWidget(self.popup_button)

        button_layout.addStretch()

        self.apply_button = QPushButton("应用更改")
        self.apply_button.clicked.connect(self._apply_changes)
        button_layout.addWidget(self.apply_button)

        layout.addLayout(button_layout)
        layout.addStretch()

    def load_item(self, path: List[str], key: str, value_type: str, value: str):
        """加载项数据"""
        self.current_path = path
        self.current_key = key
        self.current_type = value_type

        # 更新显示
        self.path_label.setText(' / '.join(path))
        self.key_edit.setText(key)
        self.type_combo.setCurrentText(value_type)

        # 根据是否是 k4 字段切换编辑器
        if key == 'k4' and value_type == 'str':
            self.value_edit.hide()
            self.k4_editor.show()
            self.k4_editor.load_k4_value(value)
        else:
            self.k4_editor.hide()
            self.value_edit.show()
            self.value_edit.setPlainText(value)

    def clear(self):
        """清空编辑器"""
        self.current_path = []
        self.current_key = ""
        self.current_type = ""
        self.path_label.setText("未选择")
        self.key_edit.clear()
        self.value_edit.clear()
        self.k4_editor.hide()
        self.value_edit.show()

    def _on_k4_value_changed(self, encoded_value: str):
        """k4 值改变"""
        # 暂时不自动应用,等待用户点击"应用更改"
        pass

    def _open_popup_editor(self):
        """打开弹出编辑器"""
        if not self.current_path:
            QMessageBox.warning(self, "警告", "请先选择要编辑的项")
            return

        # 获取当前值
        if self.current_key == 'k4' and self.k4_editor.isVisible():
            value = self.k4_editor.original_encoded_value or ""
            is_k4 = True
        else:
            value = self.value_edit.toPlainText()
            is_k4 = False

        # 创建弹出编辑器
        popup = PopupEditorDialog(
            self.current_key,
            self.current_type,
            value,
            is_k4,
            self
        )

        # 连接信号
        popup.value_accepted.connect(self._on_popup_value_accepted)

        # 显示窗口
        popup.show()

    def _on_popup_value_accepted(self, value: str):
        """弹出编辑器返回值"""
        # 更新当前编辑器的值
        if self.current_key == 'k4' and self.k4_editor.isVisible():
            self.k4_editor.original_encoded_value = value
            self.k4_editor.load_k4_value(value)
        else:
            self.value_edit.setPlainText(value)

        # 自动应用更改
        self._apply_changes()

    def _apply_changes(self):
        """应用更改"""
        if not self.current_path:
            QMessageBox.warning(self, "警告", "请先选择要编辑的项")
            return

        # 获取新值
        if self.current_key == 'k4' and self.k4_editor.isVisible():
            try:
                new_value = self.k4_editor.get_encoded_value()
            except Exception as e:
                QMessageBox.critical(self, "编码失败", f"无法编码 k4 字段:\n{str(e)}")
                return
        else:
            new_value = self.value_edit.toPlainText()

        # 发出信号
        self.value_changed.emit(self.current_key, self.current_type, new_value)


# ==================== 撤销/重做命令 ====================
class EditValueCommand(QUndoCommand):
    """编辑值命令"""

    def __init__(self, model: DataTreeModel, path: List[str],
                 old_value: Any, new_value: Any, description: str):
        super().__init__(description)
        self.model = model
        self.path = path
        self.old_value = old_value
        self.new_value = new_value

    def undo(self):
        self.model.set_value_by_path(self.path, self.old_value)
        # 重新加载模型以更新视图
        self.model.load_data(self.model.data_dict, self.model.is_gmd2)

    def redo(self):
        self.model.set_value_by_path(self.path, self.new_value)
        # 重新加载模型以更新视图
        self.model.load_data(self.model.data_dict, self.model.is_gmd2)


class AddItemCommand(QUndoCommand):
    """添加项命令"""

    def __init__(self, model: DataTreeModel, description: str):
        super().__init__(description)
        self.model = model
        # TODO: 实现添加项逻辑

    def undo(self):
        pass

    def redo(self):
        pass


class DeleteItemCommand(QUndoCommand):
    """删除项命令"""

    def __init__(self, model: DataTreeModel, description: str):
        super().__init__(description)
        self.model = model
        # TODO: 实现删除项逻辑

    def undo(self):
        pass

    def redo(self):
        pass


# ==================== 主窗口 ====================
class GMDMainWindow(QMainWindow):
    """GMD编辑器主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Geometry Dash 关卡编辑器 - PyQt6")
        self.setGeometry(100, 100, 1400, 900)

        # 数据
        self.current_file: Optional[str] = None
        self.data_model = DataTreeModel(self)

        # 撤销/重做栈
        self.undo_stack = QUndoStack(self)

        # 设置
        self.settings = QSettings("GDTools", "GMDEditor")

        # 初始化UI
        self._init_ui()
        self._create_menus()
        self._create_toolbar()
        self._create_statusbar()

        # 恢复窗口状态
        self._restore_state()

    def _init_ui(self):
        """初始化UI"""
        # 中央部件 - 树形视图
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.data_model)
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setColumnWidth(0, 300)
        self.tree_view.setColumnWidth(1, 80)
        self.tree_view.selectionModel().currentChanged.connect(self._on_tree_selection_changed)

        self.setCentralWidget(self.tree_view)

        # 属性编辑器 Dock
        self.property_dock = QDockWidget("属性编辑器", self)
        self.property_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.property_editor = PropertyEditorWidget()
        self.property_editor.value_changed.connect(self._on_value_changed)
        self.property_dock.setWidget(self.property_editor)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.property_dock)

    def _create_menus(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        open_action = QAction("打开(&O)", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        save_action = QAction("保存(&S)", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction("另存为(&A)", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self._save_as_file)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑(&E)")

        undo_action = self.undo_stack.createUndoAction(self, "撤销(&U)")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(undo_action)

        redo_action = self.undo_stack.createRedoAction(self, "重做(&R)")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        refresh_action = QAction("刷新视图(&F)", self)
        refresh_action.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh_action.triggered.connect(self._refresh_view)
        edit_menu.addAction(refresh_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")
        view_menu.addAction(self.property_dock.toggleViewAction())

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = QAction("打开文件", self)
        open_action.triggered.connect(self._open_file)
        toolbar.addAction(open_action)

        save_action = QAction("保存", self)
        save_action.triggered.connect(self._save_file)
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        undo_action = self.undo_stack.createUndoAction(self, "撤销")
        toolbar.addAction(undo_action)

        redo_action = self.undo_stack.createRedoAction(self, "重做")
        toolbar.addAction(redo_action)

        toolbar.addSeparator()

        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self._refresh_view)
        toolbar.addAction(refresh_action)

    def _create_statusbar(self):
        """创建状态栏"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("就绪")

    def _open_file(self):
        """打开文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开 GMD 文件",
            "",
            "GMD文件 (*.gmd *.lvl *.gmd2);;所有文件 (*.*)"
        )

        if not file_path:
            return

        try:
            self.statusbar.showMessage(f"正在加载: {file_path}")
            QApplication.processEvents()

            # 解析文件
            data = GMDParser.read_gmd_file(file_path)
            is_gmd2 = file_path.endswith('.gmd2')

            # 加载到模型
            self.data_model.load_data(data, is_gmd2)

            # 展开根节点
            self.tree_view.expandToDepth(0)

            self.current_file = file_path
            self.statusbar.showMessage(f"已加载: {Path(file_path).name}")

            # 清空撤销栈
            self.undo_stack.clear()

            QMessageBox.information(self, "成功", f"成功加载文件:\n{Path(file_path).name}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法加载文件:\n{str(e)}")
            self.statusbar.showMessage("加载失败")

    def _save_file(self):
        """保存文件"""
        if not self.current_file:
            self._save_as_file()
            return

        if not self.data_model.data_dict:
            QMessageBox.warning(self, "警告", "没有数据可保存")
            return

        try:
            GMDParser.save_gmd_file(self.current_file, self.data_model.data_dict)
            self.statusbar.showMessage(f"已保存: {Path(self.current_file).name}")
            QMessageBox.information(self, "成功", "文件已保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败:\n{str(e)}")

    def _save_as_file(self):
        """另存为"""
        if not self.data_model.data_dict:
            QMessageBox.warning(self, "警告", "没有数据可保存")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "另存为",
            "",
            "GMD文件 (*.gmd);;LVL文件 (*.lvl);;GMD2文件 (*.gmd2)"
        )

        if not file_path:
            return

        try:
            GMDParser.save_gmd_file(file_path, self.data_model.data_dict)
            self.current_file = file_path
            self.statusbar.showMessage(f"已保存: {Path(file_path).name}")
            QMessageBox.information(self, "成功", "文件已保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败:\n{str(e)}")

    def _refresh_view(self):
        """刷新视图"""
        if self.data_model.data_dict:
            self.data_model.load_data(self.data_model.data_dict, self.data_model.is_gmd2)
            self.tree_view.expandToDepth(0)
            self.statusbar.showMessage("视图已刷新")

    def _on_tree_selection_changed(self, current: QModelIndex, previous: QModelIndex):
        """树形视图选择改变"""
        if not current.isValid():
            self.property_editor.clear()
            return

        # 获取选中项信息
        path = self.data_model.get_item_path(current)
        key_item = self.data_model.itemFromIndex(self.data_model.index(current.row(), 0, current.parent()))
        type_item = self.data_model.itemFromIndex(self.data_model.index(current.row(), 1, current.parent()))
        value_item = self.data_model.itemFromIndex(self.data_model.index(current.row(), 2, current.parent()))

        if not all([key_item, type_item, value_item]):
            return

        key = key_item.text()
        value_type = type_item.text()

        # 获取实际值
        actual_value = self.data_model.get_value_by_path(path)
        value_str = str(actual_value) if actual_value is not None else ""

        # 加载到属性编辑器
        self.property_editor.load_item(path, key, value_type, value_str)

    def _on_value_changed(self, key: str, value_type: str, new_value_str: str):
        """值改变"""
        path = self.property_editor.current_path
        if not path:
            return

        # 获取旧值
        old_value = self.data_model.get_value_by_path(path)

        # 转换新值类型
        try:
            if value_type == 'int':
                new_value = int(new_value_str)
            elif value_type == 'float':
                new_value = float(new_value_str)
            elif value_type == 'bool':
                new_value = new_value_str.lower() in ('true', '1', 'yes')
            else:
                new_value = new_value_str
        except ValueError:
            QMessageBox.warning(self, "类型错误", f"无法将值转换为 {value_type} 类型")
            return

        # 创建撤销命令
        command = EditValueCommand(
            self.data_model,
            path,
            old_value,
            new_value,
            f"编辑 {key}"
        )
        self.undo_stack.push(command)

        self.statusbar.showMessage(f"已更新: {' / '.join(path)}")

    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 GMD 编辑器",
            "<h2>Geometry Dash 关卡编辑器</h2>"
            "<p>版本: 2.0 (PyQt6)</p>"
            "<p>支持编辑 .gmd, .lvl, .gmd2 格式的关卡文件</p>"
            "<br>"
            "<p>特性:</p>"
            "<ul>"
            "<li>现代化的可停靠面板界面</li>"
            "<li>k4 字段自动编解码和语法高亮</li>"
            "<li>撤销/重做支持 (Ctrl+Z/Ctrl+Y)</li>"
            "<li>窗口布局自动保存</li>"
            "</ul>"
            "<br>"
            "<p>基于 GMD-API 开发</p>"
        )

    def _restore_state(self):
        """恢复窗口状态"""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

    def closeEvent(self, event):
        """关闭事件"""
        # 保存窗口状态
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

        event.accept()


# ==================== 主函数 ====================
def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setApplicationName("GMD Editor")
    app.setOrganizationName("GDTools")

    # 设置样式
    app.setStyle("Fusion")

    window = GMDMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
