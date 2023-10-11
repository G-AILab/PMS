from flask_app.util.db.influxDB_util.client import InfluxDBClient
from flask_app.util.common.time_trans import *
import redis
from flask_app.config.default import Config
from loguru import logger

ip = Config.REDIS_HOST
port = Config.REDIS_PORT

r = redis.Redis(host=ip, port=port, db=0, decode_responses=True)

class InfluxDB(object):
    def __init__(self, host, port, username, password, db):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.db = db
        self.client = InfluxDBClient(host=host, port=port, username=username, password=password, database=db, headers={'Accept': 'application/json'}, gzip=True)

    def query(self, sample_step, start_time, end_time, selected_tags,**kwargs):
        """
              根据条件查询数据库
              ---------
             Args:
                 sample_step: 步长
                 start_time: 起始时间（"2021-03-01 00:00:00" 格式）
                 end_time: 结束时间（"2021-03-01 00:00:00" 格式）
                 selected_tags: 所选择的点名列表
             ----------
             Returns:
                 result: 查询结果
             ----------
                     """
        client = self.client
        start_time_utc = DT.utcfromtimestamp(float(Changestamp(start_time)))
        s_utc_str = ChangestrUTC(start_time_utc)
        end_time_utc = DT.utcfromtimestamp(float(Changestamp(end_time)))
        e_utc_str = ChangestrUTC(end_time_utc)
        sample_step = sample_step
        tags = []
        if len(selected_tags):
            for tag in selected_tags:
                tags.append(tag)
        else:
            tags = r.get('all_points').split(',')
        logger.info(f'length of tags: {len(tags)}')
        tags_str = "\",\"".join(tags)
        query_str = 'SELECT \"{}\", "Time" FROM "sis_data" WHERE time >= \'{}\' and time <= \'{}\' and "Time" % {} = 0' .format(tags_str, s_utc_str,e_utc_str, str(sample_step))
        result = client.query(query_str,**kwargs)
        return result

    # def query_all_avg(self, sample_step, start_time, end_time, tags, **kwargs):
    #     """
    #     查询均值
    #     :param sample_step: 时间步长, 单 位: 秒
    #     :type sample_step: int
    #     :type start_time: datetime.datetime
    #     :param tags: 指定选取的点名列表
    #     """
    #     s_utc_str, e_utc_str = self.__get_utc_trans(start_time, end_time)
    #     fields = list()
    #     for tag in tags:
    #         fields.append(f'MEAN(\"{tag}\") AS \"{tag}\"')
    #     tags_str = ','.join(fields)
    #     query_str = f'SELECT {tags_str} FROM "sis_data" WHERE time >= \'{s_utc_str}\' and time <= \'{e_utc_str}\' GROUP BY time({sample_step}s)'
    #     logger.info(f'查询均值SQL:{query_str}')
    #     return self.client.query(query_str, **kwargs)
    
    # def query_all_interpol(self, sample_step, start_time, end_time, tags, **kwargs):
    #     """ 查询插值 """
    #     s_utc_str, e_utc_str = self.__get_utc_trans(start_time, end_time)
    #     fields = list()
    #     for tag in tags:
    #         fields.append(f'FIRST(\"{tag}\") AS \"{tag}\"')
    #     tags_str = ','.join(fields)
    #     query_str = f'SELECT {tags_str} FROM "sis_data" WHERE time >= \'{s_utc_str}\' and time <= \'{e_utc_str}\' GROUP BY time({sample_step}s)'
    #     logger.info(f'查询插值SQL:{query_str}')
    #     return self.client.query(query_str, **kwargs)

    def query_by_func(self, sample_step, start_time, end_time, tags, func, **kwargs):
        """指定 聚合函数 在指定时间范围内进行聚合(GROUP BY)查询

        Args:
            start_time / end_time (datetime.datetime)
            sample_step (int): 指定聚合函数的聚合时间 即步长 以秒(s)作为单位
            tags (list): 指定需要查询的字段
            func (str): 指定选取的聚合函数 如 FIRST LAST MEAN 等
        """
        s_utc_str, e_utc_str = self.__get_utc_trans(start_time, end_time)
        fields = list()
        for tag in tags:
            fields.append(f'{func}(\"{tag}\") AS \"{tag}\"')
        tags_str = ','.join(fields)
        # fill采用previous策略, 当前值缺失时采用前一个历史值作为当前值
        query_str = f'SELECT {tags_str} FROM "sis_data" WHERE time > \'{s_utc_str}\' and time <= \'{e_utc_str}\' GROUP BY time({sample_step}s) fill(previous)'
        logger.info(f'查询SQL:{query_str}')
        return self.client.query(query_str, **kwargs)
    
    def normal_query(self, start_time, end_time, tags, **kwargs):
        """常规查询, 不做聚合等处理, 而是对指定字段在指定时间范围内的全部记录进行查询

        Args:
            start_time / end_time (datetime.datetime)
            tags (list): 指定需要查询的字段
        """
        s_utc_str, e_utc_str = self.__get_utc_trans(start_time, end_time)
        tags_str = '\",\"'.join(tags)
        query_str = f'SELECT "{tags_str}" FROM "sis_data" WHERE time >= \'{s_utc_str}\' and time <= \'{e_utc_str}\''
        logger.info(f'查询SQL:{query_str}')
        return self.client.query(query_str, **kwargs)
    
    def __get_utc_trans(self, start_time, end_time):
        """将本地时间对象转换为UTC时间字符串

        Args:
            start_time / end_time (datetime.datetime)

        Returns:
            s_utc_str, e_utc_str: 转换完成后的UTC时间字符串
        """
        start_time_utc = DT.utcfromtimestamp(float(Changestamp(start_time)))
        s_utc_str = ChangestrUTC(start_time_utc)
        end_time_utc = DT.utcfromtimestamp(float(Changestamp(end_time)))
        e_utc_str = ChangestrUTC(end_time_utc)
        return s_utc_str, e_utc_str
    
    def query_all_fields(self, **kwargs):
        """ 查询influxdb test数据库sis_data表当中的全部字段名称 """
        query_str = 'SHOW field keys FROM sis_data'
        result = self.client.query(query_str, **kwargs)
        point_name_list = list()
        for res in result.get_points():
            # res = {'fieldKey': '字段名', 'fieldType': '字段数据类型'}，不包含time字段
            point_name_list.append(res['fieldKey'])
        return point_name_list
