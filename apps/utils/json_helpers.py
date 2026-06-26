import json


def safe_json_loads(value):
    """安全地将 JSONField 值转换为 Python 对象。
    
    Django 的 JSONField 在某些情况下（如 SQLite 存储、数据迁移前后）
    可能返回原始字符串而非解析后的 dict。此函数确保无论哪种情况都能返回 dict。
    """
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return {}
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}
