import sys
from flask_app import create_app, get_websocket_app, initialize
from flask_app.common.init_origin_point_names_to_redis import init_origin_point_names
from flask_app.common.reset_model_status import reset_model_status

from loguru import logger



if __name__ == '__main__':
    initialize()

    reset_model_status()
    init_origin_point_names()
    app = create_app()
    socket_io = get_websocket_app(app)

    logger.info({
        "start at": 18888,
        "config": app.config
    })

    if sys.platform != "win32":
        from gunicorn.app.pasterapp import serve
        serve(app=app, global_conf={
            '__file__': ""
        }, config="./gunicorn.conf.py", host="0.0.0.0", port="47256")
    else:
        app.run(host="0.0.0.0", port=4399)
