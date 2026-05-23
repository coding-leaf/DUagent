import logging


def get_logger(name: str) -> logging.Logger:
    """返回标准库 logger，输入模块名，输出可被测试和部署统一接管的日志对象。"""
    return logging.getLogger(name)
