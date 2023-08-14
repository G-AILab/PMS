from flask import current_app
from flask_app.common.result import false_return
from functools import wraps
import traceback
from loguru import logger


def handle_error(func):
    @wraps(func)
    def decorator(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(traceback.format_exc())
            return false_return(None, traceback.format_exc())
            # if current_app.config['DEBUG']:
            #     return false_return(None, traceback.format_exc())
            # else:
            #     return false_return(None, "发生错误")
    return decorator
