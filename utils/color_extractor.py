"""
颜色提取核心业务逻辑
从图片中提取颜色并生成GD关卡方块位置数据
"""

from PIL import Image
from pathlib import Path
from typing import Set, Tuple, List, Dict


class ColorExtractor:
    """颜色提取器核心类"""

    # 固定的文件头部
    HEADER_PREFIX = """kS38,1_40_2_125_3_255_11_255_12_255_13_255_4_-1_6_1000_7_1.000000_15_1.000000_18_0_8_1|
1_0_2_102_3_255_11_255_12_255_13_255_4_-1_6_1001_7_1.000000_15_1.000000_18_0_8_1|
1_0_2_102_3_255_11_255_12_255_13_255_4_-1_6_1009_7_1.000000_15_1.000000_18_0_8_1|
1_255_2_255_3_255_11_255_12_255_13_255_4_-1_6_1002_5_1_7_1.000000_15_1.000000_18_0_8_1|
1_40_2_125_3_255_11_255_12_255_13_255_4_-1_6_1013_7_1.000000_15_1.000000_18_0_8_1|
1_40_2_125_3_255_11_255_12_255_13_255_4_-1_6_1014_7_1.000000_15_1.000000_18_0_8_1|
1_255_2_255_3_0_11_255_12_255_13_255_4_-1_6_1005_5_1_7_1.000000_15_1.000000_18_0_8_1|
1_0_2_200_3_255_11_255_12_255_13_255_4_-1_6_1006_5_1_7_1.000000_15_1.000000_18_0_8_1|
1_255_2_255_3_255_11_255_12_255_13_255_4_-1_6_1004_7_1.000000_15_1.000000_18_0_8_1|"""

    # 固定的颜色定义后缀
    COLOR_SUFFIX = ",kA13,0.000000,kA15,0,kA16,0,kA14,,kA6,0,kA7,0,kA25,0,kA17,0,kA18,0,kS39,4,kA2,0,kA3,0,kA8,0,kA4,0,kA9,0,kA10,0,kA22,1,kA23,0,kA24,0,kA27,1,kA40,1,kA41,1,kA42,1,kA28,0,kA29,0,kA31,1,kA32,1,kA36,0,kA43,0,kA44,0,kA45,1,kA46,0,kA33,1,kA34,1,kA35,0,kA37,1,kA38,1,kA39,1,kA19,0,kA26,0,kA20,0,kA21,0,kA11,0;"

    @staticmethod
    def extract_colors_from_image(image_path: str) -> Dict:
        """
        从图片中提取颜色信息

        Args:
            image_path: 图片文件路径

        Returns:
            包含提取结果的字典:
            {
                'success': bool,
                'colors': List[Tuple[int, int, int]],
                'color_count': int,
                'transparent_count': int,
                'width': int,
                'height': int,
                'error': str (如果失败)
            }
        """
        try:
            img = Image.open(image_path).convert('RGBA')
            width, height = img.size
            pixels = img.getdata()

            # 提取唯一颜色（过滤透明像素）
            unique_colors: Set[Tuple[int, int, int]] = set()
            transparent_count = 0

            for pixel in pixels:
                r, g, b, a = pixel
                # 只保留完全不透明的像素（alpha = 255）
                if a == 255:
                    unique_colors.add((r, g, b))
                else:
                    transparent_count += 1

            color_count = len(unique_colors)

            # 检查是否超过512种
            if color_count > 512:
                return {
                    'success': False,
                    'error': f'图片中有 {color_count} 种颜色，超过了512种的限制',
                    'color_count': color_count
                }

            # 转换为列表并排序（为了输出一致性）
            colors_list = sorted(list(unique_colors))

            return {
                'success': True,
                'colors': colors_list,
                'color_count': color_count,
                'transparent_count': transparent_count,
                'width': width,
                'height': height,
                'image': img  # 返回图片对象供后续使用
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def generate_color_id_mapping(colors: List[Tuple[int, int, int]], start_id: int = 999) -> Dict[Tuple[int, int, int], int]:
        """
        生成颜色到Color ID的映射表
        Color ID 从指定的start_id倒数，提取完后反转

        Args:
            colors: 颜色列表
            start_id: 起始ID，默认999，必须 <= 999 且 > 颜色数量

        Returns:
            颜色到ID的映射字典
        """
        color_count = len(colors)

        # 计算结束ID（从start_id倒数）
        end_id = start_id - color_count + 1

        # 生成倒序的ID列表
        ids_descending = list(range(start_id, end_id - 1, -1))

        # 反转得到最终的ID列表
        ids_final = list(reversed(ids_descending))

        # 创建映射表
        color_to_id = {}
        for i, color in enumerate(colors):
            color_to_id[color] = ids_final[i]

        return color_to_id

    @staticmethod
    def generate_color_data(colors: List[Tuple[int, int, int]],
                          color_to_id: Dict[Tuple[int, int, int], int]) -> List[str]:
        """
        生成颜色定义数据
        """
        result = []
        for color in colors:
            r, g, b = color
            color_id = color_to_id[color]

            # 格式: 1_Red_2_Green_3_Blue_11_255_12_255_13_255_4_-1_6_Color id_7_Opacity_15_1.000000_18_0_8_1|
            line = (
                f"1_{r}_2_{g}_3_{b}_"
                f"11_255_12_255_13_255_"
                f"4_-1_"
                f"6_{color_id}_"
                f"7_1.000000_"
                f"15_1.000000_"
                f"18_0_"
                f"8_1|"
            )
            result.append(line)

        return result

    @staticmethod
    def format_number(value: float) -> str:
        """
        格式化数字：整数输出为整数，小数输出为6位小数格式
        """
        if value == int(value):
            return str(int(value))
        else:
            return f"{value:.6f}"

    @staticmethod
    def generate_block_data(img: Image.Image, width: int, height: int,
                          color_to_id: Dict[Tuple[int, int, int], int]) -> List[str]:
        """
        生成方块位置数据
        从图片左下角开始，向右XPos增加7.5，向上YPos增加7.5
        按YPos倒序排列（最上面的先输出）
        Color Sequence按YPos顺序分配（从上到下），相同颜色使用同一个Color Sequence
        跳过透明像素
        """
        # 存储所有方块数据：(row, col, x_pos, y_pos, color_rgb)
        blocks = []

        # 遍历图片的每个像素
        for row in range(height):
            for col in range(width):
                # 获取像素颜色（RGBA格式）
                pixel = img.getpixel((col, row))
                r, g, b, a = pixel

                # 跳过透明像素
                if a != 255:
                    continue

                # 只保留RGB部分
                color_rgb = (r, g, b)

                # 计算位置（从左下角开始）
                # 图片坐标系：左上角为(0,0)，向右X增加，向下Y增加
                # 目标坐标系：左下角为(0,0)，向右X增加，向上Y增加
                x_pos = col * 7.5
                y_pos = (height - 1 - row) * 7.5

                blocks.append((row, col, x_pos, y_pos, color_rgb))

        # 按YPos倒序排列（YPos大的在前，即从上到下）
        # 注意：YPos大的对应row小的
        blocks.sort(key=lambda b: (-b[3], b[2]))  # 先按YPos降序，再按XPos升序

        # 为每种颜色分配固定的Color Sequence
        # 按照从上到下遇到颜色的顺序分配序列号
        color_to_sequence: Dict[Tuple[int, int, int], int] = {}
        next_sequence = 1

        for row, col, x_pos, y_pos, color in blocks:
            if color not in color_to_sequence:
                color_to_sequence[color] = next_sequence
                next_sequence += 1

        # 生成方块数据行
        result = []
        for row, col, x_pos, y_pos, color in blocks:
            # 获取Color ID
            color_id = color_to_id[color]

            # 获取该颜色的固定序列号
            color_sequence = color_to_sequence[color]

            # 格式: 1,917,2,XPos,3,YPos,155,Color Sequence,21,Color id;
            x_pos_str = ColorExtractor.format_number(x_pos)
            y_pos_str = ColorExtractor.format_number(y_pos)
            line = f"1,917,2,{x_pos_str},3,{y_pos_str},155,{color_sequence},21,{color_id};"
            result.append(line)

        return result

    @staticmethod
    def write_to_file(file_path: Path, color_data: List[str], block_data: List[str]):
        """将颜色数据和方块数据写入文件"""
        # 确保输出目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            # 写入固定前缀
            f.write(ColorExtractor.HEADER_PREFIX + '\n')

            # 写入颜色定义部分
            for line in color_data:
                f.write(line + '\n')

            # 写入固定后缀
            f.write(ColorExtractor.COLOR_SUFFIX + '\n')

            # 写入方块位置部分
            for line in block_data:
                f.write(line + '\n')

    @staticmethod
    def process_image(image_path: str, output_path: str, start_id: int = 999) -> Dict:
        """
        处理图片并生成输出文件

        Args:
            image_path: 输入图片路径
            output_path: 输出文件路径
            start_id: 起始Color ID，默认999

        Returns:
            处理结果字典
        """
        # 提取颜色
        extract_result = ColorExtractor.extract_colors_from_image(image_path)

        if not extract_result['success']:
            return extract_result

        colors_list = extract_result['colors']
        color_count = extract_result['color_count']
        img = extract_result['image']
        width = extract_result['width']
        height = extract_result['height']

        # 验证起始ID是否合法
        if start_id > 999:
            return {
                'success': False,
                'error': f'起始ID {start_id} 超过最大值999'
            }

        if start_id <= color_count:
            return {
                'success': False,
                'error': f'起始ID {start_id} 必须大于颜色数量 {color_count}',
                'color_count': color_count
            }

        # 生成颜色ID映射表
        color_to_id = ColorExtractor.generate_color_id_mapping(colors_list, start_id)

        # 生成颜色定义数据
        color_data = ColorExtractor.generate_color_data(colors_list, color_to_id)

        # 生成方块位置数据
        block_data = ColorExtractor.generate_block_data(img, width, height, color_to_id)

        # 输出到文件
        output_file = Path(output_path)
        ColorExtractor.write_to_file(output_file, color_data, block_data)

        return {
            'success': True,
            'color_count': color_count,
            'block_count': len(block_data),
            'transparent_count': extract_result['transparent_count'],
            'width': width,
            'height': height,
            'output_file': str(output_file),
            'start_id': start_id,
            'end_id': start_id - color_count + 1
        }
