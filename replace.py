# -*- coding: utf-8 -*-
import re

def replace_number(match):
    """
    正则表达式替换函数：替换匹配到的数字

    参数:
        match: 正则匹配对象

    返回:
        替换后的字符串
    """
    num = int(match.group())

    # 4XX → 11XX (400除外)
    if 401 <= num <= 499:
        return str(num + 700)

    # 6XX → 12XX (600除外)
    elif 601 <= num <= 699:
        return str(num + 600)

    else:
        return match.group()


def replace_value(value):
    # 使用正则表达式查找并替换所有符合条件的数字
    # \b\d{3}\b 匹配三位数字（单词边界）
    result = re.sub(r'\b\d{3}\b', replace_number, value)

    # 交换"四位数.三位数"为"三位数.四位数"
    # 匹配模式：四位数.三位数
    def swap_numbers(match):
        four_digit = match.group(1)  # 四位数
        three_digit = match.group(2)  # 三位数
        return f"{three_digit}.{four_digit}"

    # 查找并交换所有"四位数.三位数"格式
    result = re.sub(r'(\d{4})\.(\d{3})\b', swap_numbers, result)

    return result


def process_data(data_text):

    # 按分号分割成多行
    lines = data_text.strip().split(';')
    processed_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 用逗号分割
        parts = line.split(',')

        # 检查是否符合处理条件
        if len(parts) >= 2 and parts[0] == '1':
            # 1,901 或 1,1346：替换第18位
            if parts[1] in ['901', '1346'] and len(parts) >= 18:
                parts[17] = replace_value(parts[17])

            # 1,1816：替换第8位
            elif parts[1] == '1816' and len(parts) >= 8:
                parts[7] = replace_value(parts[7])

            # 1,1888 或 1,3802：替换第12位
            elif parts[1] in ['1888', '3802'] and len(parts) >= 12:
                parts[11] = replace_value(parts[11])

        # 重新组合这一行
        processed_lines.append(','.join(parts))

    # 用分号连接所有行，每行末尾添加分号
    return ';\n'.join(processed_lines) + ';'


def main():
    # 从文件读取数据
    try:
        with open('data.txt', 'r', encoding='utf-8') as f:
            data = f.read()

        # 处理数据
        processed_data = process_data(data)

        # 写入新文件
        with open('data_new.txt', 'w', encoding='utf-8') as f:
            f.write(processed_data)

        print("数据处理完成！")
        print("输入文件: data.txt")
        print("输出文件: data_new.txt")

    except FileNotFoundError:
        print("错误：找不到 data.txt 文件")
    except Exception as e:
        print(f"错误：{e}")


if __name__ == '__main__':
    main()
