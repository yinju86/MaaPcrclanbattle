def to_share(data):
    result = []
    for entry in data:
        # 提取每个部分
        decimal_part = entry[0]  # 三位数字
        single_digit = entry[1]  # 一位数字
        bool_list = entry[2]     # 6个布尔值
        # 将布尔值列表转化为二进制字符串
        binary_part = ''.join(['1' if b else '0' for b in bool_list])
        # 拼接十进制部分和二进制部分
        combined_number = f"{decimal_part}{single_digit}{int(binary_part, 2):02d}"
        # 补齐6位数字
        result.append(combined_number.zfill(6))
    result=six_digit_to_base62(result)
    return result

def from_share(data):
    data=base62_to_six_digit(data)
    result = []
    for entry in data:
        # 拆分六位数字，前3位是十进制，第四位是一位数字，后两位是二进制
        decimal_part = entry[:3]
        single_digit = entry[3]
        binary_part = f"{int(entry[4:]):06b}"
        # 将二进制部分转化为布尔列表
        bool_list = [b == '1' for b in binary_part]
        # 组合成原始结构
        result.append((decimal_part, single_digit, bool_list))
    return result

# 62进制字符集
charset = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

# 十进制转62进制
def to_base62(num):
    if num == 0:
        return '0'
    base62 = []
    while num > 0:
        base62.append(charset[num % 62])
        num //= 62
    return ''.join(reversed(base62))

# 将六位数字转为一个连续的62进制字符
def six_digit_to_base62(data):
    result = []
    for entry in data:
        # 将六位数字转为整数
        decimal_number = int(entry)
        # 转为62进制
        base62_str = to_base62(decimal_number)
        # 保证3个字符，不足的用 '0' 补齐
        result.append(base62_str.zfill(3))
    # 返回拼接后的字符串
    return ''.join(result)

# 62进制转十进制
def from_base62(base62_str):
    num = 0
    for char in base62_str:
        num = num * 62 + charset.index(char)
    return num

# 将连续的62进制字符还原为六位数字
def base62_to_six_digit(encoded_str):
    result = []
    # 每3个字符为一组
    for i in range(0, len(encoded_str), 3):
        # 取出每三个字符
        base62_chunk = encoded_str[i:i+3]
        # 将62进制字符转为整数
        decimal_number = from_base62(base62_chunk)
        # 转为六位数字，不足的用 '0' 补齐
        result.append(str(decimal_number).zfill(6))
    return result
