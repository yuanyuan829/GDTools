"""
GMD编辑器核心业务逻辑
提供GMD数据处理的辅助功能
"""

from typing import Any, Dict, List, Optional


class GMDEditor:
    """GMD编辑器辅助类"""

    @staticmethod
    def validate_data(data: Dict[str, Any]) -> bool:
        """
        验证GMD数据是否有效

        Args:
            data: GMD数据字典

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(data, dict):
            return False
        return True

    @staticmethod
    def get_data_summary(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取GMD数据摘要信息

        Args:
            data: GMD数据字典

        Returns:
            包含摘要信息的字典
        """
        summary = {
            'total_keys': 0,
            'has_level_data': False,
            'has_metadata': False,
        }

        if not data:
            return summary

        summary['total_keys'] = len(data)

        # 检查常见的关键字段
        if 'level_data' in data:
            summary['has_level_data'] = True
        if 'metadata' in data:
            summary['has_metadata'] = True

        # 检查 k4 字段（关卡数据）
        if 'k4' in data:
            summary['has_k4_data'] = True

        return summary

    @staticmethod
    def format_value_for_display(value: Any, max_length: int = 50) -> str:
        """
        格式化值用于显示

        Args:
            value: 要格式化的值
            max_length: 最大显示长度

        Returns:
            格式化后的字符串
        """
        value_str = str(value)
        if len(value_str) > max_length:
            return value_str[:max_length] + "..."
        return value_str

    @staticmethod
    def get_value_type(value: Any) -> str:
        """
        获取值的类型名称

        Args:
            value: 要检查的值

        Returns:
            类型名称字符串
        """
        if isinstance(value, bool):
            return 'bool'
        elif isinstance(value, int):
            return 'int'
        elif isinstance(value, float):
            return 'float'
        elif isinstance(value, str):
            return 'str'
        elif isinstance(value, dict):
            return 'dict'
        elif isinstance(value, list):
            return 'list'
        else:
            return type(value).__name__

    @staticmethod
    def convert_value(value_str: str, value_type: str) -> Any:
        """
        将字符串值转换为指定类型

        Args:
            value_str: 字符串值
            value_type: 目标类型

        Returns:
            转换后的值

        Raises:
            ValueError: 如果转换失败
        """
        try:
            if value_type == 'str':
                return value_str
            elif value_type == 'int':
                return int(value_str)
            elif value_type == 'float':
                return float(value_str)
            elif value_type == 'bool':
                return value_str.lower() in ('true', '1', 'yes')
            elif value_type == 'dict':
                import json
                return json.loads(value_str)
            elif value_type == 'list':
                import json
                return json.loads(value_str)
            else:
                return value_str
        except Exception as e:
            raise ValueError(f"无法将 '{value_str}' 转换为 {value_type}: {e}")

    @staticmethod
    def search_in_data(data: Dict[str, Any], search_term: str) -> List[str]:
        """
        在数据中搜索包含指定关键词的路径

        Args:
            data: 要搜索的数据
            search_term: 搜索关键词

        Returns:
            匹配的路径列表
        """
        results = []

        def search_recursive(current_data: Any, path: str):
            if isinstance(current_data, dict):
                for key, value in current_data.items():
                    new_path = f"{path}/{key}" if path else key
                    if search_term.lower() in key.lower():
                        results.append(new_path)
                    search_recursive(value, new_path)
            elif isinstance(current_data, list):
                for i, item in enumerate(current_data):
                    new_path = f"{path}[{i}]"
                    search_recursive(item, new_path)
            else:
                if search_term.lower() in str(current_data).lower():
                    results.append(path)

        search_recursive(data, "")
        return results
