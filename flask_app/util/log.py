import logging
import logging.handlers
from decimal import Decimal
import math
import os
import threading
import time
import sys
from typing import Any, Dict, Optional
import logging
from .singleton import Singleton
import json

class PowerModelFormatter(logging.Formatter):
    def get_extra_fields(self, record):
        # The list contains all the attributes listed in
        # http://docs.python.org/library/logging.html#logrecord-attributes
        skip_list = (
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'id', 'levelname', 'levelno', 'lineno', 'module',
            'msecs', 'msecs', 'message', 'msg', 'name', 'pathname', 'process',
            'processName', 'relativeCreated', 'thread', 'threadName', 'extra',
            'auth_token', 'password', 'stack_info')

        easy_types = (str, bool, dict, int, list, type(None))

        fields = {}

        for key, value in record.__dict__.items():
            if key not in skip_list:
                if isinstance(value, easy_types):
                    fields[key] = value
                elif isinstance(value, float):
                    fields[key] = None if math.isnan(value) else value
                else:
                    fields[key] = str(value)

        return fields

    def format(self, record):
        s = super(PowerModelFormatter, self).format(record)
        extras = json.dumps(self.get_extra_fields(record), ensure_ascii=False)
        if extras != '{}':
            s = f'{s} extras: {extras}'
        return s

class LoggerPool(metaclass=Singleton):
    def __init__(self):
        self.pool: Dict[str, logging.Logger] =  dict()

    def get(self, name: Optional[str]=None, file_location:str='') -> logging.Logger:
        if name is None:
            name = 'root'
            consoleHandler = logging.StreamHandler()
            formatter = PowerModelFormatter(
                    '%(asctime)s - %(name)s - p%(process)s {%(pathname)s:%(lineno)d} - %(levelname)s - %(message)s')
            consoleHandler.setFormatter(formatter)
            self.pool[name].addHandler(consoleHandler)

        if name not in self.pool:
            logger = logging.getLogger(name)
            if file_location != '':
                formatter = PowerModelFormatter(
                    '%(asctime)s - %(name)s - p%(process)s {%(pathname)s:%(lineno)d} - %(levelname)s - %(message)s')
                file_handler  = logging.handlers.RotatingFileHandler(file_location, mode='a+',  maxBytes=1024 * 1024, backupCount=3, encoding='utf-8')
                file_handler.setFormatter(formatter)
                file_handler.setLevel(logging.DEBUG)
                logger.addHandler(file_handler)
            logger.setLevel(logging.DEBUG)
            self.pool[name] = logger
        return self.pool[name]
    def set_level(self, name: Optional[str] , level: Optional[int]):
        if name not in self.pool:
            raise ValueError('name not in logger pool')
        else:
            self.pool[name].setLevel(level)
        
logger = LoggerPool().get('root')




class ModelLogger(LoggerPool):
    def get(self, mid : int, version: int, streaming=False, out_file=False, name='run')-> logging.Logger:
        model_logger = LoggerPool.get(self, f"model.run.M{mid}.V{version}")
        
        model_logger.propagate = False
        
        if not model_logger.hasHandlers() and out_file:
            model_logger.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - p%(process)s {%(pathname)s:%(lineno)d} - %(levelname)s - %(message)s')
            file_handler  = logging.handlers.RotatingFileHandler(f"/workspace/hd_ws/models/M{mid}/v{version}/logs/{name}.log", mode='a+',  maxBytes=1024 * 1024, backupCount=3)
            file_handler.setFormatter(formatter)
            model_logger.addHandler(file_handler)
            
            if streaming is True:
                consoleHandler = logging.StreamHandler()
                consoleHandler.setFormatter(formatter)
                model_logger.addHandler(consoleHandler)
        return model_logger
    
# logstash elasticsearch kibana  ELK
class PointCheckLoggerPool(LoggerPool):
    def get(self, pname: str, file_name: str = 'run.log')-> logging.Logger:
        return LoggerPool.get(self , 'root')
        point_logger = LoggerPool.get(self, f"point.{pname}")
        logger_path = f'/workspace/power_model_system/logs/{pname}/'
        if not os.path.exists(logger_path):
            os.makedirs(logger_path)
        point_logger.propagate = False
        
        if not point_logger.hasHandlers():
            point_logger.setLevel(logging.CRITICAL)
            formatter = logging.Formatter('%(asctime)s - %(name)s - p%(process)s {%(pathname)s:%(lineno)d} - %(levelname)s - %(message)s')
            file_handler  = logging.handlers.RotatingFileHandler(os.path.join(logger_path,file_name) , mode='a+', maxBytes=1024 * 1024, backupCount=3)
            file_handler.setFormatter(formatter)
            point_logger.addHandler(file_handler)
            
        return point_logger