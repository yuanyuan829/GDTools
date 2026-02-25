"""
GMD文件解析器
支持.gmd, .lvl, .gmd2格式的Geometry Dash关卡文件
"""

import plistlib
import zlib
import gzip
import zipfile
import json
from pathlib import Path
from typing import Dict, Any, Optional
import base64


class GMDParser:
    """GMD文件解析器类"""

    @staticmethod
    def decode_k4(k4_string: str) -> str:
        """
        解码k4字段 (Base64解码 + GZIP解压)

        Args:
            k4_string: 经过Base64编码的GZIP压缩数据

        Returns:
            解码后的原始关卡字符串
        """
        try:
            # 1. 修复Base64 padding
            # Base64字符串长度必须是4的倍数,不足的用=补齐
            missing_padding = len(k4_string) % 4
            if missing_padding:
                k4_string += '=' * (4 - missing_padding)

            # 2. Base64解码 (使用URL安全的base64解码,因为GD使用 - 和 _ 替代 + 和 /)
            compressed_data = base64.urlsafe_b64decode(k4_string)

            # 3. GZIP解压
            decompressed_data = gzip.decompress(compressed_data)

            # 4. 转换为字符串
            return decompressed_data.decode('utf-8', errors='ignore')
        except Exception as e:
            raise ValueError(f"k4解码失败: {e}")

    @staticmethod
    def encode_k4(level_string: str) -> str:
        """
        编码k4字段 (GZIP压缩 + Base64编码)

        Args:
            level_string: 原始关卡数据字符串

        Returns:
            编码后的k4字符串
        """
        try:
            # 1. 转换为字节
            data = level_string.encode('utf-8')

            # 2. GZIP压缩 (mtime=0 确保可重复性，compresslevel=6 匹配GD格式)
            compressed_data = gzip.compress(data, mtime=0, compresslevel=6)

            # 3. Base64编码 (使用URL安全的base64编码,因为GD使用 - 和 _ 替代 + 和 /)
            encoded_string = base64.urlsafe_b64encode(compressed_data).decode('ascii')

            # 4. 保留Base64填充符(与原始格式一致)
            return encoded_string
        except Exception as e:
            raise ValueError(f"k4编码失败: {e}")

    @staticmethod
    def read_gmd_file(file_path: str) -> Dict[str, Any]:
        """
        读取GMD文件并返回解析后的数据

        Args:
            file_path: 文件路径

        Returns:
            解析后的字典数据
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        if extension == '.gmd':
            return GMDParser._read_gmd(path)
        elif extension == '.lvl':
            return GMDParser._read_lvl(path)
        elif extension == '.gmd2':
            return GMDParser._read_gmd2(path)
        else:
            raise ValueError(f"不支持的文件格式: {extension}")

    @staticmethod
    def _read_gmd(file_path: Path) -> Dict[str, Any]:
        """读取.gmd文件(纯plist格式)"""
        with open(file_path, 'rb') as f:
            data = f.read()

        # 先尝试转换GD特有的plist格式
        try:
            # 将GD的简写标签转换为标准plist标签
            gd_plist_text = data.decode('utf-8')
            standard_plist = GMDParser._convert_gd_plist_to_standard(gd_plist_text)
            plist_data = plistlib.loads(standard_plist.encode('utf-8'))
            return plist_data
        except Exception as e:
            # 如果转换失败，尝试直接解析
            try:
                plist_data = plistlib.loads(data)
                return plist_data
            except:
                raise ValueError(f"无法解析GMD文件: {e}")

    @staticmethod
    def _read_lvl(file_path: Path) -> Dict[str, Any]:
        """读取.lvl文件(GZip压缩的plist)"""
        with open(file_path, 'rb') as f:
            compressed_data = f.read()

        # 解压缩数据
        try:
            decompressed_data = zlib.decompress(compressed_data)
        except:
            # 尝试使用gzip
            decompressed_data = gzip.decompress(compressed_data)

        # 解析plist
        plist_data = plistlib.loads(decompressed_data)
        return plist_data

    @staticmethod
    def _read_gmd2(file_path: Path) -> Dict[str, Any]:
        """读取.gmd2文件(zip格式,包含level.data和level.meta)"""
        result = {
            'level_data': None,
            'metadata': None,
            'song_file': None
        }

        with zipfile.ZipFile(file_path, 'r') as zip_file:
            # 读取level.data
            if 'level.data' in zip_file.namelist():
                level_data = zip_file.read('level.data')
                result['level_data'] = plistlib.loads(level_data)

            # 读取level.meta
            if 'level.meta' in zip_file.namelist():
                meta_data = zip_file.read('level.meta')
                result['metadata'] = json.loads(meta_data.decode('utf-8'))

            # 检查是否有歌曲文件
            for name in zip_file.namelist():
                if name.endswith('.mp3'):
                    result['song_file'] = name

        return result

    @staticmethod
    def _parse_plist_text(text: str) -> Dict[str, Any]:
        """解析文本格式的plist"""
        # 简单的XML plist解析
        try:
            return plistlib.loads(text.encode('utf-8'))
        except:
            # 如果失败,返回原始文本
            return {'raw_data': text}

    @staticmethod
    def _convert_gd_plist_to_standard(gd_plist: str) -> str:
        """
        将Geometry Dash的简化plist格式转换为标准plist格式
        GD格式使用: <k>, <i>, <s>, <r>, <t/>, <d>, <a>
        标准格式: <key>, <integer>, <string>, <real>, <true/>, <dict>, <array>
        """
        import re

        # 替换映射
        replacements = [
            # 开始标签
            (r'<k>', '<key>'),
            (r'<i>', '<integer>'),
            (r'<s>', '<string>'),
            (r'<r>', '<real>'),
            (r'<d>', '<dict>'),
            (r'<a>', '<array>'),
            # 结束标签
            (r'</k>', '</key>'),
            (r'</i>', '</integer>'),
            (r'</s>', '</string>'),
            (r'</r>', '</real>'),
            (r'</d>', '</dict>'),
            (r'</a>', '</array>'),
            # 自闭合标签
            (r'<t\s*/>', '<true/>'),
            (r'<f\s*/>', '<false/>'),
        ]

        result = gd_plist
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result)

        return result

    @staticmethod
    def _convert_standard_to_gd_plist(standard_plist: str) -> str:
        """
        将标准plist格式转换为Geometry Dash的简化格式
        """
        import re

        # 反向替换映射
        replacements = [
            # 开始标签
            (r'<key>', '<k>'),
            (r'<integer>', '<i>'),
            (r'<string>', '<s>'),
            (r'<real>', '<r>'),
            (r'<dict>', '<d>'),
            (r'<array>', '<a>'),
            # 结束标签
            (r'</key>', '</k>'),
            (r'</integer>', '</i>'),
            (r'</string>', '</s>'),
            (r'</real>', '</r>'),
            (r'</dict>', '</d>'),
            (r'</array>', '</a>'),
            # 自闭合标签
            (r'<true\s*/>', '<t />'),
            (r'<false\s*/>', '<f />'),
        ]

        result = standard_plist
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result)

        # 确保plist标签包含gjver属性（GD必需）
        result = re.sub(
            r'<plist version="1\.0">',
            '<plist version="1.0" gjver="2.0">',
            result
        )

        # 移除XML声明中的多余信息，使其更紧凑
        result = re.sub(r'<\?xml.*?\?>\s*<!DOCTYPE.*?>\s*', '<?xml version="1.0"?>', result, flags=re.DOTALL)

        # 移除换行和缩进，使其成为单行（GD格式通常是压缩的）
        result = re.sub(r'>\s+<', '><', result)
        result = re.sub(r'\n\s*', '', result)

        return result

    @staticmethod
    def save_gmd_file(file_path: str, data: Dict[str, Any]) -> None:
        """
        保存GMD文件

        Args:
            file_path: 文件路径
            data: 要保存的数据
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        if extension == '.gmd':
            GMDParser._save_gmd(path, data)
        elif extension == '.lvl':
            GMDParser._save_lvl(path, data)
        elif extension == '.gmd2':
            GMDParser._save_gmd2(path, data)
        else:
            raise ValueError(f"不支持的文件格式: {extension}")

    @staticmethod
    def _save_gmd(file_path: Path, data: Dict[str, Any]) -> None:
        """保存为.gmd文件 - 手动构建XML以保持GD格式和顺序"""

        def value_to_gd_xml(value, indent_level=0):
            """将Python值转换为GD XML格式"""
            if isinstance(value, bool):
                return '<t />' if value else '<f />'
            elif isinstance(value, int):
                return f'<i>{value}</i>'
            elif isinstance(value, float):
                # 如果浮点数实际上是整数值，就不加小数点
                if value == int(value):
                    return f'<r>{int(value)}</r>'
                else:
                    return f'<r>{value}</r>'
            elif isinstance(value, str):
                # 转义特殊字符
                escaped = value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                return f'<s>{escaped}</s>'
            elif isinstance(value, dict):
                # 内层字典使用<d>标签（GD简化格式）
                items = []
                for k, v in value.items():
                    items.append(f'<k>{k}</k>')
                    items.append(value_to_gd_xml(v, indent_level + 1))
                return '<d>' + ''.join(items) + '</d>'
            elif isinstance(value, list):
                items = []
                for item in value:
                    items.append(value_to_gd_xml(item, indent_level + 1))
                return '<a>' + ''.join(items) + '</a>'
            else:
                return f'<s>{str(value)}</s>'

        # 构建根字典（使用<dict>标签）
        xml_parts = ['<?xml version="1.0"?><plist version="1.0" gjver="2.0"><dict>']

        for key, value in data.items():
            xml_parts.append(f'<k>{key}</k>')
            xml_parts.append(value_to_gd_xml(value))

        xml_parts.append('</dict></plist>')

        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(''.join(xml_parts))

    @staticmethod
    def _save_lvl(file_path: Path, data: Dict[str, Any]) -> None:
        """保存为.lvl文件(GZip压缩)"""
        plist_data = plistlib.dumps(data, fmt=plistlib.FMT_XML)
        compressed_data = zlib.compress(plist_data)

        with open(file_path, 'wb') as f:
            f.write(compressed_data)

    @staticmethod
    def _save_gmd2(file_path: Path, data: Dict[str, Any]) -> None:
        """保存为.gmd2文件(zip格式)"""
        with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 保存level.data
            if 'level_data' in data:
                level_plist = plistlib.dumps(data['level_data'], fmt=plistlib.FMT_XML)
                zip_file.writestr('level.data', level_plist)

            # 保存level.meta
            if 'metadata' in data:
                meta_json = json.dumps(data['metadata'], indent=2)
                zip_file.writestr('level.meta', meta_json)

            # 如果有歌曲文件路径,添加歌曲
            if 'song_file_path' in data and Path(data['song_file_path']).exists():
                song_path = Path(data['song_file_path'])
                zip_file.write(song_path, song_path.name)
