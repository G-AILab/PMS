import chardet
import os
import time

def get_file_encoding(filename):
    try:
        with open(filename, 'rb') as f:
            data = f.read(5000)
            info = chardet.detect(data)
            probability = info.get('confidence')
            encoding = str(info.get('encoding'))
            if probability > 0.8 and encoding.upper() in ('UTF-8','GB2312','GBK'):
                return encoding
            else:
                print(f"can't get file:{filename} encoding, return GB2312.File info:{info}")
                return 'GB2312'
    except Exception as e:
        print("[ERROR] exception is ", e)
        return "GB2312"

def store_request_file(file, filename, prefix="", suffix="", extension='csv'):
    from flask_app.config.default import Config
    from flask_app import flask_app
    ts = int(time.time())
    x = time.localtime(ts)
    t = time.strftime('%Y-%m-%dT%H:%M:%S', x)
    filename_part = filename.replace(f".{extension}","")
    if suffix:
        local_filename = f"{prefix} _{filename_part}_{suffix}_{t}.{extension}"
    else:
        local_filename = f"{prefix} _{filename_part}_{t}.{extension}"
    local_file_path = os.path.join(flask_app.root_path, Config.UPLOAD_FOLDER, local_filename)
    file.save(local_file_path)
    return local_file_path