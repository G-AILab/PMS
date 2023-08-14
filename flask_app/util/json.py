import json

import numpy as np

class PowermodelJSONizer(json.JSONEncoder):
    def default(self, obj):
        # 对 numpy bool_ 类型进行 json encode ， 否则会报错
        return super().encode(bool(obj)) \
            if isinstance(obj, np.bool_) \
            else super().default(obj)
