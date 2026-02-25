"""
图片颜色提取工具
从图片中提取所有颜色（不超过512种）并生成方块位置数据，输出到output/color.txt文件
"""

import sys
from pathlib import Path
from PIL import Image
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QFileDialog,
    QMessageBox, QSpinBox, QLineEdit, QGroupBox, QStatusBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from utils.color_extractor import ColorExtractor


class ColorExtractorGUI(QWidget):
    """颜色提取器GUI类"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("图片颜色提取工具")
        self.setGeometry(100, 100, 800, 600)

        # 当前图片
        self.current_image_path = None
        self.current_image = None
        self.color_count = 0

        # 创建界面
        self._create_widgets()

    def _create_widgets(self):
        """创建界面组件"""
        # 主布局
        main_layout = QVBoxLayout()

        # 顶部控制区
        control_layout = QHBoxLayout()

        # 选择图片按钮
        self.select_btn = QPushButton("选择图片")
        self.select_btn.clicked.connect(self.select_image)
        control_layout.addWidget(self.select_btn)

        # 提取颜色按钮
        self.extract_btn = QPushButton("提取颜色")
        self.extract_btn.clicked.connect(self.extract_colors)
        control_layout.addWidget(self.extract_btn)

        control_layout.addStretch()
        main_layout.addLayout(control_layout)

        # ID设置区
        id_layout = QHBoxLayout()

        # 起始ID
        id_layout.addWidget(QLabel("起始ID:"))
        self.start_id_spinbox = QSpinBox()
        self.start_id_spinbox.setRange(1, 999)
        self.start_id_spinbox.setValue(999)
        self.start_id_spinbox.valueChanged.connect(self._update_id_range)
        id_layout.addWidget(self.start_id_spinbox)

        id_layout.addSpacing(20)

        # 预计ID范围
        id_layout.addWidget(QLabel("预计ID范围:"))
        self.id_range_edit = QLineEdit()
        self.id_range_edit.setReadOnly(True)
        self.id_range_edit.setPlaceholderText("请先选择图片")
        self.id_range_edit.setMaximumWidth(150)
        id_layout.addWidget(self.id_range_edit)

        id_layout.addStretch()
        main_layout.addLayout(id_layout)

        # 图片预览区
        preview_group = QGroupBox("图片预览")
        preview_layout = QVBoxLayout()

        self.preview_label = QLabel("请选择一张图片")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(400)
        self.preview_label.setStyleSheet("QLabel { background-color: #f0f0f0; }")
        preview_layout.addWidget(self.preview_label)

        preview_group.setLayout(preview_layout)
        main_layout.addWidget(preview_group)

        # 信息显示区
        info_group = QGroupBox("提取信息")
        info_layout = QVBoxLayout()

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(150)
        info_layout.addWidget(self.info_text)

        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)

    def select_image(self):
        """选择图片文件"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片文件",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*.*)"
        )

        if filename:
            try:
                self.current_image_path = filename
                self.current_image = Image.open(filename)

                # 显示预览
                self._show_preview()

                # 快速提取颜色数量
                extract_result = ColorExtractor.extract_colors_from_image(filename)
                if extract_result['success']:
                    self.color_count = extract_result['color_count']
                    self._update_id_range()

                    self.status_bar.showMessage(f"已加载: {Path(filename).name}")
                    self._log_info(f"已加载图片: {filename}")
                    self._log_info(f"图片尺寸: {self.current_image.size[0]}x{self.current_image.size[1]}")
                    self._log_info(f"检测到 {self.color_count} 种颜色")
                else:
                    # 处理颜色过多的情况
                    if 'color_count' in extract_result:
                        self.color_count = extract_result['color_count']
                        self._update_id_range()
                        QMessageBox.warning(
                            self,
                            "警告",
                            f"图片中有 {self.color_count} 种颜色，超过了512种的限制！\n请使用颜色更少的图片。"
                        )
                        self.status_bar.showMessage(f"颜色过多: {self.color_count} > 512")
                    else:
                        QMessageBox.critical(self, "错误", f"无法分析图片:\n{extract_result.get('error', '未知错误')}")
                        self.status_bar.showMessage("分析失败")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法加载图片:\n{str(e)}")
                self.status_bar.showMessage("加载失败")

    def _show_preview(self):
        """显示图片预览"""
        if not self.current_image:
            return

        # 计算预览尺寸（保持宽高比）
        max_width = 700
        max_height = 400
        img_width, img_height = self.current_image.size

        ratio = min(max_width / img_width, max_height / img_height)
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)

        # 创建预览图片
        preview_img = self.current_image.copy()
        preview_img.thumbnail((new_width, new_height), Image.Resampling.LANCZOS)

        # 转换为QPixmap并显示
        preview_img_rgb = preview_img.convert('RGB')
        preview_img_rgb.save('temp_preview.png')
        pixmap = QPixmap('temp_preview.png')
        self.preview_label.setPixmap(pixmap)

        # 删除临时文件
        try:
            Path('temp_preview.png').unlink()
        except:
            pass

    def _update_id_range(self):
        """更新预计ID范围显示"""
        if self.color_count == 0:
            self.id_range_edit.clear()
            self.id_range_edit.setPlaceholderText("请先选择图片")
            return

        start_id = self.start_id_spinbox.value()
        end_id = start_id - self.color_count + 1

        if end_id < 1:
            self.id_range_edit.setText(f"无效 (需要 {self.color_count} 个ID)")
            self.id_range_edit.setStyleSheet("QLineEdit { color: red; }")
        else:
            self.id_range_edit.setText(f"{end_id}-{start_id}")
            self.id_range_edit.setStyleSheet("")

    def extract_colors(self):
        """提取图片中的颜色并生成方块位置数据"""
        if not self.current_image_path:
            QMessageBox.warning(self, "警告", "请先选择一张图片")
            return

        try:
            start_id = self.start_id_spinbox.value()

            self.status_bar.showMessage("正在提取颜色...")
            QApplication.processEvents()  # 更新界面

            # 使用 ColorExtractor 处理图片
            output_path = Path(__file__).parent / "output" / "color.txt"
            result = ColorExtractor.process_image(
                self.current_image_path,
                str(output_path),
                start_id=start_id
            )

            if not result['success']:
                if 'color_count' in result and result['color_count'] >= start_id:
                    QMessageBox.critical(
                        self,
                        "起始ID不足",
                        f"起始ID {start_id} 必须大于颜色数量 {result['color_count']}！\n"
                        f"请将起始ID设置为至少 {result['color_count'] + 1}"
                    )
                    self.status_bar.showMessage(f"失败: 起始ID不足")
                elif 'color_count' in result and result['color_count'] > 512:
                    QMessageBox.critical(
                        self,
                        "颜色过多",
                        f"图片中有 {result['color_count']} 种颜色，超过了512种的限制！\n请使用颜色更少的图片。"
                    )
                    self.status_bar.showMessage(f"失败: 颜色过多 ({result['color_count']} > 512)")
                else:
                    QMessageBox.critical(self, "错误", f"提取失败:\n{result.get('error', '未知错误')}")
                    self.status_bar.showMessage("提取失败")
                return

            # 显示成功信息
            self._log_info(f"\n提取到 {result['color_count']} 种不同的颜色")
            if result['transparent_count'] > 0:
                self._log_info(f"跳过 {result['transparent_count']} 个透明像素")

            self._log_info(f"图片尺寸: {result['width']}x{result['height']}")
            self._log_info(f"总像素数: {result['width'] * result['height']}")
            self._log_info(f"使用的Color ID范围: {result['end_id']}-{result['start_id']}")
            self._log_info(f"成功生成 {result['color_count']} 种颜色定义")
            self._log_info(f"成功生成 {result['block_count']} 个方块位置")
            self._log_info(f"已保存到: {result['output_file']}")

            self.status_bar.showMessage(
                f"提取成功: {result['color_count']} 种颜色, {result['block_count']} 个方块, "
                f"ID范围: {result['end_id']}-{result['start_id']}"
            )

            QMessageBox.information(
                self,
                "成功",
                f"成功提取 {result['color_count']} 种颜色！\n"
                f"生成 {result['block_count']} 个方块位置\n"
                f"使用Color ID: {result['end_id']}-{result['start_id']}\n"
                f"结果已保存到 output/color.txt 文件"
            )

        except Exception as e:
            QMessageBox.critical(self, "错误", f"提取颜色时出错:\n{str(e)}")
            self.status_bar.showMessage("提取失败")
            import traceback
            traceback.print_exc()

    def _log_info(self, message: str):
        """在信息区显示日志"""
        self.info_text.append(message)


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = ColorExtractorGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
