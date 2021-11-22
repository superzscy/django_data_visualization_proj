import re

file_size_units = {"B": 1, "KB": 1024, "MB": 1024*1024}


def parse_file_size_int_to_str(num, suffix="B"):
    for unit in ["", "K", "M"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def parse_file_size_str_to_int(size_str):
    size_str = size_str.upper()
    if not re.match(r' ', size_str):
        size_str = re.sub(r'([KM]?B)', r' \1', size_str)
    number, unit = [string.strip() for string in size_str.split()]
    return int(float(number) * file_size_units[unit])
