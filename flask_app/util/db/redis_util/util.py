from flask import current_app
import redis
from flask_app.util.singleton import Singleton
class Redis(object):
    def __init__(self, host, port, db):
        self.host = host
        self.port = port
        self.db = db
        self.redis_pool = redis.ConnectionPool(host=host, port=port, db=db,max_connections=96, decode_responses=True)
        self.redis_client = redis.Redis(connection_pool=self.redis_pool)

    """
        手动切换数据库
        ---------
       Args:
           db: 要切换的到的数据库id
       ----------
       Returns:
       ----------
               """
    def change_redis(self, db):
        self.db = db
        self.redis_client = redis.Redis(connection_pool=self.redis_pool)


    def write(self, key, value, expire=None):
        """
           写入键值对
           """
        # 判断是否有过期时间，没有就设置默认值
        if expire:
            expire_in_seconds = expire
        else:
            expire_in_seconds = current_app.config['REDIS_EXPIRE']
        r = self.redis_client
        r.set(key, value, ex=expire_in_seconds)

    def read(self, key):
        """
           读取键值对内容
           """
        r = self.redis_client
        value = r.get(key)
        return value

    def hset(self, name, key, value):
        """
        写入hash表
        """
        r = self.redis_client
        value = r.hset(name, key, value,mapping=None)
        return value

    def hmset(self, key, *value):
        """
        读取指定hash表的所有给定字段的值
        """
        r = self.redis_client
        value = r.hmset(key, *value)
        return value
    
    def mget(self, *key_list):
        r = self.redis_client
        res = r.mget(*key_list)
        return res
        

    def hget(self, name, key):
        """
         读取指定hash表的键值
         """
        r = self.redis_client
        value = r.hget(name, key)
        return value
        # return value.decode('utf-8') if value else value

    def hgetall(self, name):
        """
        获取指定hash表所有的值
        """
        r = self.redis_client
        return r.hgetall(name)

    def delete(self, *names):
        """
               删除一个或者多个
               """
        r = self.redis_client
        r.delete(*names)

    def hdel(self, name, key):
        """
          删除指定hash表的键值
          """
        r = self.redis_client
        r.hdel(name, key)


    def expire(self, name, expire=None):
        """
               设置过期时间
               """
        if expire:
            expire_in_seconds = expire
        else:
            expire_in_seconds = current_app.config['REDIS_EXPIRE']
        r = self.redis_client
        r.expire(name, expire_in_seconds)
    
    def persist(self, key):
        """
        去掉某个key的过期时间，使其长期保存
        """
        self.redis_client.persist(key)

    def publish(self, channel, msg):
        """
               定义发布方法
               """
        r = self.redis_client
        r.publish(channel, msg)
        return True


    def subscribe(self,channel):
        """
               定义订阅方法
               """
        r = self.redis_client
        pub = r.pubsub()
        pub.subscribe(channel)
        pub.parse_response()
        return pub

    def scan_keys(self, key: str, max_count=1000):
        """
        模糊查询数据库键值
        ---------
       Args:
           key: 要查询的key值(时间戳)
           max_count: 最多返回数量，默认1000
       ----------
       Returns:
           value_list: 此时间戳下的所有模型预测值集合
       ----------
               """
        r = self.redis_client
        res = r.scan(match='*'+key +'*', count=max_count)
        keys = res[1]
        value_list = []
        for key in keys:
            value = r.get(key)
            value_list.append(value)
        return value_list

    def get_all_ts(self):
        """
        获取所有的键值
        """
        r = self.redis_client
        return sorted(r.keys())


    def get_max_ts(self):
        """
        该函数由于性能过差, 应用read('latest')替代
        获取键值中的最大时间戳
        """
        r = self.redis_client
        return max(r.keys())

    def get_current_db(self):
        """
        获取当前的数据库id
        """
        return self.db

    def get_realtime_value_by_ts(self, ts, *point_names) -> list:
        '''
        获取指定时间戳下多个点名的实时数据
        '''
        r = self.redis_client
        return r.mget(*['{}@{}'.format(ts, point_name) for point_name in point_names])
    
    def get_realtime_value_by_points(self, point_name, *timestamps) -> list:
        '''
        获取指定点多个时间戳的实时数据
        '''
        r = self.redis_client
        return r.mget(*['{}@{}'.format(ts, point_name) for ts in timestamps])
