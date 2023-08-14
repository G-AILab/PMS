def to_bool(bool_str):
    '''
    将字符串('True'/'False'/'true'/'false')转换为bool类型
    若无法匹配上述字符串则返回其本身
    ----------
    Args:
        bool_str: 字符串
    Returns:
        True/False/bool_str
    '''
    if bool_str == 'True' or bool_str == 'true':
        return True
    if bool_str == 'False' or bool_str == 'false':
        return False
    return bool_str
