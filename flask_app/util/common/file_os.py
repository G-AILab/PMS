import pandas as pd
import os
import shutil


from werkzeug.utils import secure_filename
from flask_app.config.default import Config


def save_pickle(result, path, selected_tags):
    """
    根据查路径将询得到的数据存储为pickle文件
    Args:
      path: 存储路径
      selected_tags: 数组,所选点名
    """
    path = path
    data = result._raw['series'][0]['values']
    columns = result._raw['series'][0]['columns']
    for index in range(len(columns)):
        if columns[index].startswith('first_'):
            columns[index] = columns[index].strip('first_')
    selected_keys = []
    keys_index = {}
    temp = []
    for key in selected_tags:
        if key in columns:
             keys_index[columns.index(key)] = key
             selected_keys.append(key)
             
    if len(selected_keys):
        for item in data:
            for index in range(len(item)):
                if index in keys_index.keys():
                    temp.append(item[index])
            item.clear()
            for key in temp:
                item.append(key)
            temp.clear()
        df = pd.DataFrame(data, columns=selected_keys)
    else:
        df = pd.DataFrame(data, columns=columns)
    df.to_pickle(path)
    # print('write success')

def save_pickle_raw(result, path):
    """
    根据查路径将询得到的数据存储为pickle文件
    """
    path = path
    data = result._raw['series'][0]['values']
    columns = result._raw['series'][0]['columns']
    for index in range(len(columns)):
        if columns[index].startswith('first_'):
            columns[index] = columns[index].strip('first_')
    df = pd.DataFrame(data, columns=columns)
    df.to_pickle(path)
    # print('write success')


def del_dir_file(filepath):
    """
    删除某一目录下的所有文件或文件夹
    :param filepath: 路径
    :return:
    """
    del_list = os.listdir(filepath)
    for f in del_list:
        file_path = os.path.join(filepath, f)
        if os.path.isfile(file_path):
            os.remove(file_path)
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)


def del_file(filepath):
    """
    删除某一路径下的文件
    :param filepath: 路径
    :return:
    """
    file_path = os.path.join(filepath)
    if os.path.isfile(file_path):
        os.remove(file_path)
    else:
        print("请输入正确的路径名")


def allowed_upload(filename):
    """
    根据后缀名判断该文件是否允许上传
    ----------
    Args:
        filename: 完整文件名
    ----------
    Returns:
        是否合法，经过安全处理的文件名，该文件的后缀名
    """
    filename = secure_filename(filename)
    try:
        extension = filename.rsplit('.', 1)[1]
    except IndexError:
        extension = ""
    allowed = '.' in filename and extension in Config.ALLOWED_EXTENSIONS
    return allowed, filename, extension

def allowed_upload_csv(filename, allowed_extensions=['csv']):
    """
    根据后缀名判断该文件是csv文件允许上传
    ----------
    Args:
        filename: 完整文件名
    ----------
    Returns:
        是否合法，经过安全处理的文件名，该文件的后缀名
    """
    # filename = secure_filename(filename)
    try:
        extension = filename.rsplit('.', 1)[1]
    except IndexError:
        extension = ""
    allowed = '.' in filename and extension in allowed_extensions
    return allowed, filename, extension


def tail_file(file_path: str, tail_n: int) -> list:
    '''
    获取文件末尾的字符串
    '''
    step_size = 1024

    with open(file_path, 'rb') as f:
        f.seek(0, 2)
        file_size = f.tell()
        next_step = min(file_size, step_size)

        f.seek(-next_step, 2)
        s = f.readlines()
        while len(s) < tail_n:
            next_step = min(file_size, next_step + step_size)
            f.seek(-next_step, 2)
            s = f.readlines()
            if next_step >= file_size:
                break
        
        res = s[-tail_n:]
    
    encoded = list(map(lambda x: x.decode('utf-8').strip('\n'), res))
    return encoded


def get_FileSize(filePath):
    """
    获取文件大小,单位为MB
    ----------
    Args:
        filePath: 完整文件地址
    ----------
    Returns:
        文件大小:整数 MB
    """
    file_stats = os.stat(filePath)
    fsize = file_stats.st_size / (1024 * 1024)
    return round(fsize)
