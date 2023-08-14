from flask_app.config import get_config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from flask_app.models.model import Model
from flask_app.common.constants import ModelStatus
from loguru import logger
import pymysql

def reset_model_status():
    _get_config = get_config()
    engine = create_engine(_get_config.SQLALCHEMY_DATABASE_URI)
    tablename = Model.__tablename__
    with engine.connect() as conn:
        result = conn.execute(text(f"UPDATE {tablename} SET status={ModelStatus.SET_UP_ERROR} WHERE status={ModelStatus.SETTING_UP}"))
        result = conn.execute(text(f"UPDATE {tablename} SET status={ModelStatus.SET_UP_DONE} WHERE status={ModelStatus.SELECTING}"))
        result = conn.execute(text(f"UPDATE {tablename} SET status={ModelStatus.SELECTING_DONE} WHERE status={ModelStatus.TRAINING} or status={ModelStatus.TRAINING_WAIT}"))
        result = conn.execute(text(f"UPDATE {tablename} SET status={ModelStatus.TRAINING_DONE}  WHERE status={ModelStatus.OPTIMIZING_WAIT} or status={ModelStatus.OPTIMIZING}"))
    logger.info(f"reset model status")
    