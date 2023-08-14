import multiprocessing
from flask_app.apschedule_tasks import flask_aps, create_aps_app
from flask_app.apschedule_tasks.realtime_evaluation import realtime_eval_task
from flask_app.apschedule_tasks.get_server_usage import get_remote_server_stats
from flask_app.apschedule_tasks.point_check.point_check import init_point_check_task_main, start_point_limits_read_loop,init_pool, point_check_task, update_oper_step, update_point_limits, point_judge_pool
from flask_app.apschedule_tasks.check_model_processes import check_processes_task
from flask_app.apschedule_tasks.point_check.point_check import oper_guide_task
from rpyc.utils.server import ThreadedServer
from api import PointCheckService
from multiprocessing.pool import Pool





if __name__ == "__main__":
    app = create_aps_app()
    flask_aps.init_app(app)
    
    init_point_check_task_main()
    update_oper_step()
    
    flask_aps.start()
    s = ThreadedServer(PointCheckService, port=18871,protocol_config={
                                     'allow_public_attrs': True, 'sync_request_timeout': 10}) # 启动服务
    s.start()
