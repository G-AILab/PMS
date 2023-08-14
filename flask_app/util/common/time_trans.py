import time
import datetime
from datetime import datetime as DT

import pytz


def pywindt_to_timestamp(str_pywdt: str):
    """
    将pywintypes.datetime的字符串转换为time.timestamp
    """
    t_str = str_pywdt.replace('+00:00', '')
    return str_to_timestamp(t_str)


def pywindt_to_timestr(str_pywdt):
    return str_pywdt.replace('+00:00', '')


# datetime时间转为字符串
def Changestr(datetime1):
    str = datetime1.strftime('%Y-%m-%d %H:%M:%S')
    return str

# datetime时间转为UTC字符串
def ChangestrUTC(datetime1):
    str = datetime1.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return str


# 字符串时间转为时间戳
def str_to_timestamp(str1):
    unix_time = time.mktime(time.strptime(str1, '%Y-%m-%d %H:%M:%S'))
    return unix_time


# datetime时间转为时间戳
def Changestamp(dt1):
    Unixtime = time.mktime(time.strptime(dt1.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S'))
    return Unixtime


# 时间戳转为datetime时间
def Changedatetime(timestamp):
    dt = datetime.datetime.fromtimestamp(timestamp)
    dt = dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt

# uinx时间戳转换为本地时间
def Localtime(datetime1):
    Localtime = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(datetime1))
    return Localtime


# 字符串时间转换函数
def Normaltime(datetime1):
    Normaltime = datetime.datetime.strptime(datetime1,'%Y-%m-%d %H:%M:%S')
    return Normaltime

#UTC时间转变为本地时间
def utc_to_local(utc_time_str, utc_format='%Y-%m-%dT%H:%M:%SZ', local_format="%Y-%m-%d %H:%M:%S"):
    local_tz = pytz.timezone('Asia/Shanghai')
    utc_dt = datetime.datetime.strptime(utc_time_str, utc_format)
    local_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(local_tz)
    time_str = local_dt.strftime(local_format)
    return datetime.datetime.fromtimestamp(int(time.mktime(time.strptime(time_str, local_format))))



# if __name__ == '__main__':
#     # t = pywindt_to_timestamp('2021-03-01 00:00:00+00:00')
#     # print(t)
#     # print(Changestr(Changedatetime(t)))
#     # time_stamp = 1614528000
#     # x = DT.utcfromtimestamp(time_stamp).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
#     # print(x)
#     # x = utc_to_local(x)
#     # print(x)
#     # print(Normaltime("2021-03-01 00:00:00"))
#     # print(Changestamp(Normaltime("2021-03-01 00:00:00")))
#     x = '2021-12-31T16:00:36Z'
#     x = utc_to_local(x)
#     print(x)