import os
import os.path as osp
import threading

import pandas as pd
from flask_app import _get_config


class ExExcelReader:
    def __init__(self, directory):
        self.directory = directory
        self.full_file_names = None
        self.point_names_buffer = dict()
        self.all_file_names_lock = threading.Lock()
        # self.point_lock = threading.Lock()

    def get_all_file_names(self) -> list:
        self.all_file_names_lock.acquire()
        if not self.full_file_names:
            self.full_file_names = list(filter(lambda x: x.endswith('.xlsx') or x.endswith('.xls'), os.listdir(self.directory)))
        self.all_file_names_lock.release()
        return list(map(lambda x: x.split('.')[0], self.full_file_names))
    
    def get_point_names(self, file_name):
        if file_name in self.point_names_buffer:
            return True, self.point_names_buffer[file_name]
        
        full_file_name = osp.join(self.directory, '{}{}'.format(file_name, '.xlsx'))
        if not osp.exists(full_file_name):
            full_file_name = osp.join(self.directory, '{}{}'.format(file_name, '.xls'))
            if not osp.exists(full_file_name):
                return False, f"File '{full_file_name}' not found"

        points = list()
        ex_df = pd.read_excel(full_file_name, header=None, names=['id', 'name', 'describe'])
        for i, row in ex_df.iterrows():
            tmp_point = {
                'id': row['id'],
                'name': row['name'],
                'describe': row['describe']
            }
            points.append(tmp_point)
        
        self.point_names_buffer[file_name] = points
        return True, points


ex_reader = ExExcelReader(_get_config.EXTERN_EXCEL_DIR)
