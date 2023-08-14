from pydoc import describe
from flask import Blueprint, g, make_response, request, current_app
from flask_app import redis as r, influx, db, flask_app
from flask_app.api import handle_error
from flask_app.common.before_request import check_page, get_request_data, check_unit
from flask_app.common.result import false_return, true_return
from flask_app.models.inter_variable import InterVariable
from flask_app.models.origin_point_dec import PointType, write_origin_points_to_redis, OriginPointDesc
from flask_app.models.origin_point_system_config import OriginPointSystemConfig
from flask_app.models.system_config import SystemConfig
from flask_app.util.common.time_trans import *
from flask_app.util.common.file_os import *
from flask_app.util.rpc.point_desc import point_check_eval
from flask_app.util.str_util import to_bool
from iapws import iapws97
from iapws import IAPWS97
from loguru import logger
import traceback
import re
import arrow
import multiprocessing
import pandas as pd
import signal
import chardet
import numpy as np
import io
import os
from loguru import logger

inter_variable_blueprint = Blueprint("inter_variable_blueprint", __name__, url_prefix='/inter')

measurement = 'sis_data'

#------------------------------------------自定义函数------------------------------------------------------------------
def Sfunline(A,B):#折线函数
    C= len(B)
    n=int(C/2)
    m=int(C/2-1)
    a=np.zeros(m)
    b=np.zeros(m)
    X=np.zeros(n)
    Y=np.zeros(n)
    if A<=B[0] or A>=B[-2]:
        optimal = B[1] if A<B[0] else B[-1]
    else :
        for i in range (n):
            X[i]=B[i*2]
            Y[i]=B[i*2+1]
        for i in range( m ) :
            a[i] =(Y[i+1] -Y[i]) / (X[i+1] -X[i])
            b[i] =Y[i]-X[i]*a[i]
        for i in range ( m ):
            if A>=X[i] and A<X[i+1]:
                optimal = A*a[i]+b[i]
    return (optimal)

def PackRE(pointname,bite):#打包点解析，点名，第几位
    strPackname= bin(int(CDATA[pointname]))
    # print(Currentdata[pointname], pointname,strPackname)
    Packbite=len(strPackname)-1-bite
    if len(strPackname)<=bite:
        Packdata=0
    else :
        Packdata =strPackname[Packbite]
    return (Packdata)    

def get_his(pointname: str, timen: list):
    '''
    从redis中获取过去一段时间某个点的值
    ----------
    Args:
        pointname: 点名
        timen: 长度为1时timen[0]表示指定时间点(过去第timen[0]秒)；长度为2时表示[结束时间偏移(较小值)，开始时间偏移(较大值)]
    Returns:
        res: 若timen长度为2则返回list，为1则返回float
    '''
    latest_ts = r.read('latest')
    if len(timen) == 1:
        target_ts = int(latest_ts) - timen[0]
        # res = redis.hget(str(target_ts), pointname)
        res = r.read('{}@{}'.format(target_ts, pointname))
        res = float(res) if res else None
        return (res)

    elif len(timen) == 2:
        start_ts = int(latest_ts) - timen[1]
        end_ts = int(latest_ts) - timen[0]
        key_list = ['{}@{}'.format(ts, pointname) for ts in range(end_ts - 1, start_ts - 1, -1)]
        p_res = r.mget(*key_list)
        # with redis.redis_client.pipeline() as p:
        #     for timestamp in range(end_ts - 1, start_ts - 1, -1):
        #         # p.hmget(max_key-i, *model_handler.use_cols)
        #         p.hmget(str(timestamp), pointname)
        #     p_res = p.execute()
        res = list()
        for pv in p_res:
            if pv is not None:
                res.append(float(pv))
        return (res)

def AVG(pointname, LDtime):
    '''
    求点名历史均值
    '''
    his_data = get_his(pointname, [0, LDtime])
    AVG = np.average(his_data) if len(his_data) > 0 else np.nan
    return (AVG)

dict_RS={}
def RS(in1,in2,in3):#in1置位点号，in2复位点号，in3输出保持时间秒/RS触发器标签
    if type(in2) == str:
        time3 = 600 if in3 == '' or in3 == 'nan' or in3 == 0 else in3
        a="DCS"+str(in1)+str(in2)+str(time3)
        out = dict_RS[a] if a in dict_RS.keys() else [0,0]
        if CDATA[in1] == 0 and CDATA[in2] == 0 :#置位为0，复位为0，输出保持
            if out[1] < time3:
                out[0] = out[0]
                out[1] += 1
            else:#输出强制为0
                out[0] = 0
        if CDATA[in2] == 1:#复位为1，输出为0
            out =[0,0]
        if CDATA[in1] == 1 and CDATA[in2] == 0:#置位为1，复位为0，输出为1
            out[0] = 1
    else :
        a = in3
        out = dict_RS[in3] if in3 in dict_RS.keys() else [0,0]
        if in1 == 0 and in2 == 0:#置位为0，复位为0，输出保持
            out = out
        if in2 == 1:#复位为1，输出为0
            out[0] = 0
        if in1 == 1 and in2 == 0:#置位为1，复位为0，输出为1
            out[0] = 1
    dict_RS.update({a:out})
    return(out[0])
#------------------------------------------自定义函数------------------------------------------------------------------

@inter_variable_blueprint.before_request
@handle_error
def before_request():
    success, msg = check_unit()
    if not success:
        return false_return(msg)
    if request.method == 'GET' or request.method == 'DELETE':
        g.data = request.args
    else:
        content_type = request.headers.get('Content-Type')
        if (content_type == 'application/json'):
            g.data = request.get_json()


@inter_variable_blueprint.route('/variable', methods=['GET'])
@handle_error
def query_inter_variable():
    has_id, data = get_request_data(request, ['vid'])
    if has_id:
        inter_variable = InterVariable.get_by_id(data['vid'])
        if inter_variable:
            origin_point = OriginPointDesc.get_by_name(inter_variable.var_name, int(g.unit))
            result = inter_variable.to_json()
            if origin_point:
                result["systems"] = origin_point.to_json().get("systems", [])
            return true_return("查询成功", result)
        else:
            return false_return("查询失败,中间变量不存在")

    has_var_name, data = get_request_data(request, ['var_name'])
    if has_var_name:
        inter_variable = InterVariable.get_by_name(data['var_name'], g.unit)
        if inter_variable:
            origin_point = OriginPointDesc.get_by_name(inter_variable.var_name, int(g.unit))
            result = inter_variable.to_json()
            if origin_point:
                result["systems"] = origin_point.to_json().get("systems", [])
            return true_return("查询成功", result)
        else:
            return false_return("查询失败,中间变量不存在")

    return false_return('查询失败，参数缺少vid 或者 var_name')


@inter_variable_blueprint.route('/variable', methods=['POST'])
@handle_error
def add_inter_variable():
    success, data = get_request_data(request, ['var_name', 'var_value', 'remark'])
    if not success:
        return false_return(data)
    var_name = data['var_name']
    var_value = data['var_value']
    remark = data['remark']
    if point_check_eval(var_value) is not None:
        vid, msg = InterVariable.create(var_name, var_value, remark, -1, g.unit)
        if vid:
            write_origin_points_to_redis(origin_point=False, inter_variable=True)
            from flask_app.util.process_manager import fill_interval_process
            now_timestamp = int(time.time())
            start_timestamp = int(Changestamp(Normaltime('2022-02-01 00:00:00')))
            # end_timestamp = int(Changestamp(Normaltime('2022-02-05 00:00:00')))
            start_timestamp = max(now_timestamp - 60*60*24*180, start_timestamp)
            end_timestamp = now_timestamp
            start_time = Normaltime(Localtime(start_timestamp))
            end_time = Normaltime(Localtime(end_timestamp))
            InterVariable.update(vid, g.unit, {'status':0})
            ctx = multiprocessing.get_context('spawn')
            db.get_engine(app=current_app).dispose()
            p = ctx.Process(target=fill_his_data, args=(vid, start_time, end_time, var_name, var_value, g.unit, fill_interval_process))
            p.start()
            return true_return('创建成功,开始自动填充历史数据')
        else:
            return false_return(msg)
    else:
        return false_return(msg="中间变量eval出错,请检查公式是否规范")

#导入模板，批量创建
@inter_variable_blueprint.route('/upload_file', methods=['POST'])
@handle_error
def upload_file():
    try:
        tags_file = request.files['inter_variable_file']
        if tags_file:
            allowed, filename, extension = allowed_upload_csv(tags_file.filename)
            if not allowed:
                error_message = "文件后缀名必须是.csv"
                return false_return(msg=error_message)
            
            file = chardet.detect(tags_file.read())
            encoding = file['encoding']
            
            tags_file.seek(0)
            data = pd.read_csv(tags_file, encoding=encoding)
            data = data.where(data.notnull(), None)
            
            var_name_list = data['中间变量名'].tolist()
            var_value_list = data['计算方式'].tolist()
            remark_list = data['描述'].tolist()
            system_list = data['对应系统名'].tolist()
            # 查出整个unit的全部系统用于判断数据中的系统名是否存在
            # 由于系统表(system_config)基本不发生变化，因此可只连一次数据库判断
            sys_total = SystemConfig.get_all_id_and_names_in_unit(g.unit)
            
            # key => (system)name, value => cid  注意：应确保每个系统name对应唯一 一个cid，才能根据该方法进行索引
            sys_name_list = [(row.name, row.cid) for row in sys_total]
            sys_name_list = dict(sys_name_list)
            # ctx = multiprocessing.get_context('spawn')
            db.get_engine(app=current_app).dispose()
            p = multiprocessing.Process(target=add_inter_vavriables, args=(var_name_list, var_value_list, remark_list, system_list, sys_name_list, g.unit))
            p.start()
            return true_return(msg="正在批量创建中间变量")
        else:
            return false_return(msg='上传的中间变量文件不能为空')
    except UnicodeDecodeError as e:
        traceback.print_exc()
        return false_return(msg='编码格式错误')
    except Exception as e:
        traceback.print_exc()
        return false_return(msg='csv文件中缺少相应列或计算方式有误或其他问题')

# 非多进程批量创建不合适
# def batch_create_inter_variables_by_file(request_file, unit, encoding='utf-8'):
#     request_file.seek(0)
#     data = pd.read_csv(request_file, encoding=encoding)
#     # NaN数据缺失部分替换为None
#     data = data.where(data.notnull(), None)
    
#     # 查出整个unit的全部系统用于判断数据中的系统名是否存在
#     # 由于系统表(system_config)基本不发生变化，因此可用一次性判断
#     # 只连一次数据库，后面可以考虑用redis来维护一个哈希，此处暂时用dict哈希代替
#     sys_total = SystemConfig.get_all_id_and_names_in_unit(unit)
    
#     # key => name, value => cid  注意：应确保每个系统name对应唯一 一个cid，才能根据该方法进行索引
#     sys_name_list = [(row.name, row.cid) for row in sys_total]
#     sys_name_list = dict(sys_name_list)
    
#     # 逐行读取判断，上传的系统若存在则批量插入
#     origin_points, inter_vars, confs = [], [], []
#     for row in data.itertuples(index=False):
#         sys_list = getattr(row, '对应系统名').split(' ')
#         var_name = getattr(row, '中间变量名')
#         var_value = getattr(row, '计算方式')
#         remark = getattr(row, '描述')
#         try:
#             # 检测计算方式是否正确，错误则抛出异常
#             point_check_eval(var_value)
            
#             # 筛选出存在的系统进行插入
#             sys_list_filter = []
#             for sys in sys_list:
#                 if sys in sys_name_list.keys():
#                     sys_list_filter.append(sys_name_list.get(sys))
            
#             if not len(sys_list_filter):
#                 continue
#             else:
#                 for cid in sys_list_filter:
#                     confs.append(OriginPointSystemConfig(origin_point=var_name, system_config=cid).to_dict())
                
#             inter_vars.append(InterVariable(var_name=var_name, var_value=var_value, remark=remark).to_dict())
#             origin_points.append(OriginPointDesc(tag_name=var_name, describe=remark, unit=unit, point_type=PointType.INTERVARIABLE).to_dict())
#         except Exception as e:
#             traceback.print_exc()
#             # return false_return(f'变量: {var_name} 的计算方式有误，请修改后重新上传文件')
#             continue
#     upsert_all(OriginPointDesc, origin_points)
#     upsert_all(InterVariable, inter_vars)
#     upsert_all(OriginPointSystemConfig, confs)


@inter_variable_blueprint.route('/variable', methods=['PUT'])
@handle_error
def update_inter_variable():
    success, data = get_request_data(request, ['vid', 'var_name', 'var_value', 'remark'])
    if not success:
        return false_return(data)

    if point_check_eval(data['var_value']) is not None:
    # var_name = data['var_name']
    # var_value = data['var_value']
    # points = re.findall("'([^']+)'", var_value)
    # latest = redis.read('latest')
    # CDATA = MID = {}
    # for point in points:
    #     key = str(latest) + '@' + str(point)
    #     if redis.read(key) is None:
    #         return false_return(msg="公式中存在未找到的点名:"+point)
    #     else:
    #         CDATA[point] = MID[point] = redis.read(key)
    # try:
    #     res = eval(var_value)
    # except KeyError as e:
    #     logger.warning('point: {} "{}" exec error! {} not found'.format(var_name, var_value, e))
    #     return false_return(msg="公式中存在未找到的点名:"+var_name)
    # except Exception as e:
    #     logger.warning('point: {} "{}" exec error! e: {}'.format(var_name, var_value, e))
    #     import traceback
    #     print(traceback.format_exc())

    #     return false_return(msg="中间变量eval出错,请检查公式是否规范")
        result, msg = InterVariable.update(data['vid'], g.unit, data)
        if result:
            write_origin_points_to_redis(origin_point=False, inter_variable=True)
            return true_return('更新成功')
        else:
            return false_return(msg)
    else:
        return false_return(msg="中间变量eval出错,请检查公式是否规范")
        
    

@inter_variable_blueprint.route('/variable', methods=['DELETE'])
@handle_error
def delete_inter_variable():
    success, data = get_request_data(request, ['vid'])
    if not success:
        return false_return(data)
    result, msg = InterVariable.delete(data['vid'], g.unit)
    write_origin_points_to_redis(origin_point=False, inter_variable=True)
    if result:
        return true_return('删除成功')
    else:
        return false_return(msg)


@inter_variable_blueprint.route('/variables', methods=['GET'])
@handle_error
def query_inter_variables():
    
    eval_value = bool(request.args.get('eval_value', False))
    have_page, page, size = check_page(request)
    if have_page:
        inter_variables, total = InterVariable.get_by_page(g.unit, page, size)
    else:
        inter_variables, total = InterVariable.get_unit_all(g.unit)
    data = InterVariable.add_origin_points_info_to_inter_variable(inter_variables, eval_value=eval_value)
    result = {
        "total": total,
        "data": data
    }
    return true_return("查询成功", result)


@inter_variable_blueprint.route('/systems_belong', methods=['POST'])
@handle_error
def add_inter_variable_to_system():
    success, data = get_request_data(request, ['vid', 'systems'], ['systems'])
    if not success:
        return false_return(data)

    vid = data['vid']
    systems = data['systems']
    inter_variable = InterVariable.get_by_id(vid)
    if inter_variable is None:
        return false_return("中间变量不存在")

    msg = OriginPointDesc.add_systems(inter_variable.var_name, systems, int(g.unit))
    return true_return(msg)


@inter_variable_blueprint.route('/systems_belong', methods=['DELETE'])
@handle_error
def remove_inter_variable_to_system():
    success, data = get_request_data(request, ['vid', 'system'])
    if not success:
        return false_return(data)

    vid = data['vid']
    system = data['system']
    inter_variable = InterVariable.get_by_id(vid)
    if inter_variable is None:
        return false_return("中间变量不存在")

    msg = OriginPointDesc.delete_systems(inter_variable.var_name, system, int(g.unit))
    return true_return(msg)


@inter_variable_blueprint.route('/multi_search', methods=['GET'])
def multi_search():
    """
    多条件查询点名信息
    ----------
    Args:
        var_name: 中间变量名
        value: 中间变量描述
        remark: 中间变量remark
        system: 系统名
        system_alias: 系统别名
    ----------
    Returns:
        inter_variables: 点描述对象（列表）
    """
    eval_value = bool(request.args.get('eval_value', False))
    _, page, size = check_page(request)

    var_name = g.data.get('var_name')
    var_value = g.data.get("value")
    var_remark = g.data.get("remark")
    system = g.data.get('system')
    system_alias = g.data.get('system_alias')
    inter_variables = InterVariable.multi_search(var_name, var_value, var_remark, system, system_alias, int(g.unit), page, size, eval_value=eval_value)
    return true_return('筛选成功', inter_variables)


@inter_variable_blueprint.route('/variable_fill', methods=['POST'])
@handle_error
def fill_his_data():
    from flask_app.util.process_manager import fill_interval_process
    success, data = get_request_data(request, ['vid','start_time', 'end_time'])
    if not success:
        return false_return(data)
    vid = data['vid']
    inter_variable = InterVariable.get_by_id(vid)
    var_name = inter_variable.var_name
    var_value = inter_variable.var_value
    start_time = Normaltime(data['start_time'])
    end_time = Normaltime(data['end_time'])
    if point_check_eval(var_value) is not None:
        InterVariable.update(vid, g.unit, {'status':0})
        InterVariable.update(vid, g.unit, {'process':0.00})
        ctx = multiprocessing.get_context('spawn')
        db.get_engine(app=current_app).dispose()
        p = ctx.Process(target=fill_his_data, args=(vid, start_time, end_time, var_name, var_value, g.unit, fill_interval_process))
        p.start()
        return true_return(msg="正在填充历史数据")
    else:
        return false_return(msg="中间变量eval出错,请检查公式是否规范")
   
    
@inter_variable_blueprint.route('/stop_fill', methods=['DELETE'])
@handle_error
def stop_fill_data():
    try:
        from flask_app.util.process_manager import fill_interval_process
        vid = g.data.get('vid')
        if vid in fill_interval_process:
            logger.info(str(vid))
            target_pid = fill_interval_process[vid]
            fill_interval_process.pop(vid)
            os.kill(target_pid, signal.SIGKILL)
        return true_return("停止填充成功")
    except Exception as e:
        logger.warning(str(e))
        return false_return("该中间变量不存在")


@inter_variable_blueprint.route('/download', methods=['GET'])
@handle_error
def download_file():
    """
    根据条件筛选数据并按照模板格式返回
    """
    # _, page, size = check_page(request)
    var_name = g.data.get('var_name', None)
    var_value = g.data.get('var_value', None)
    remark = g.data.get('remark', None)
    sys_name = g.data.get('system', None)
    sys_alias = g.data.get('system_alias', None)
    all_unit = g.data.get("all_unit", False)
    
    all_unit = to_bool(all_unit)
    
    return_vars, size =  InterVariable.search_all_no_page(var_name, var_value, remark, sys_name, 
                                                       sys_alias, g.unit, all_unit=all_unit)

    if size:
        out = io.BytesIO()
        filename = str(datetime.date.today()) + 'inter_variable_file' + '.csv'
        return_vars = format_data(return_vars)
        return_vars = pd.DataFrame(return_vars)
        return_vars.to_csv(out, index=False)
        
        out.seek(0)
        # return send_file(out, mimetype='text/csv', as_attachment=True, attachment_filename=filename)
        
        response = make_response(out.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Content-Disposition'] = 'attachment; filename=' + filename
        return response
    else:
        return false_return("no data", None)


def format_data(vars: list) -> dict:
    return_vars = {
        "中间变量名": [],
        "计算方式": [],
        "描述": [],
        "对应系统名": []
    }
    for var in vars:
        return_vars['中间变量名'].append(var.var_name)
        return_vars['计算方式'].append(var.var_value)
        return_vars['描述'].append(var.remark)
        return_vars['对应系统名'].append(var.systems)
    
    return return_vars


def fill_data_process(start_timestamp, end_timestamp, var_name:str, var_value:str):
    points = re.findall("'([^']+)'", var_value)
    if len(points):
        print(points)
        results = list()
        sample_step = 1
        chunk_size = 60
        start_time = Normaltime(Localtime(start_timestamp))
        end_time = Normaltime(Localtime(end_timestamp))
        chunk_count = 0
        for res in influx.query(sample_step, start_time, end_time, points, chunked=True, chunk_size=chunk_size):
            chunk_count += len(list(res.get_points()))
            values = res._raw['series'][0]['values']
            results.extend(values)
            if chunk_count == 60:
                columns = res._raw['series'][0]['columns']
        result = pd.DataFrame(results, columns=columns, dtype=np.float32)
        result = result.fillna(method='ffill')
        result = result.fillna(method='bfill')
        CDATA ={}
        MID = {}
        json_body = []
        for index,row in result.iterrows():
            CDATA = MID = row
            try:
                x = DT.utcfromtimestamp(float(start_timestamp+index)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                res= eval(var_value)
                # print(start_timestamp+index, res)
                body = {
                        "measurement": measurement,
                        "time": x,
                        "fields": {var_name:res}
                        }
                json_body.append(body)
            except KeyError as e:
                logger.warning('point: {} "{}" exec error! {} not found'.format(var_name, var_value, e))
            except Exception as e:
                logger.warning('point: {} "{}" exec error! e: {}'.format(var_name, var_value, e))
        influx.client.write_points(json_body)      
    else:
        json_body = []
        for i in range(start_timestamp, end_timestamp):
            try:
                x = DT.utcfromtimestamp(float(i)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                res= eval(var_value)
                body = {
                    "measurement": measurement,
                    "time": x,
                    "fields": {var_name:res}
                    }
                json_body.append(body)
            except KeyError as e:
                logger.warning('point: {} "{}" exec error! {} not found'.format(var_name, var_value, e))
            except Exception as e:
                logger.warning('point: {} "{}" exec error! e: {}'.format(var_name, var_value, e))
        influx.client.write_points(json_body)
        

def fill_his_data(vid, start_time, end_time, var_name:str, var_value:str, unit, processes):
    """
        填充中间变量历史数据
        ---------
        Args:
            start_time: 起始时间（"2021-03-01 00:00:00" 格式）
            end_time: 结束时间（"2021-03-01 00:00:00" 格式）
            vid: 中间点名id
            var_name: 中间变量点名
            var_value: 中间变量计算公式
            processes: 进程字典
        ----------
        Returns:
        ----------
                """
    data = {
        "name": var_name
    }
    try:
        pid = os.getpid()
        processes[vid] = pid
        
        start_timestamp = int(Changestamp(start_time))
        end_timestamp = int(Changestamp(end_time))
        total = end_timestamp - start_timestamp
        # pool_size = 10
        # pool = multiprocessing.Pool(pool_size)
        while start_timestamp < end_timestamp:
            #每8个小时创建一个进程
            temp_timastamp = start_timestamp + 28800
            if temp_timastamp >  end_timestamp:
                temp_timastamp = end_timestamp
            # pool.apply_async(fill_data_process, (start_timestamp, temp_timastamp, var_name, var_value), error_callback=lambda x: print(x))
            fill_data_process(start_timestamp, temp_timastamp, var_name, var_value)
            start_timestamp = temp_timastamp
            cur_process = round((end_timestamp - start_timestamp) / total * 100 , 2)
            InterVariable.update(vid, unit, {'process': 100.00 - cur_process})
            logger.info(str(100.00 - cur_process))
        # pool.close()
        # pool.join()
        InterVariable.update(vid, unit, {'status':1})
        InterVariable.update(vid, unit, {'process': 100.00})
        data['status'] = '成功'
        data['msg'] = '填充中间点历史数据成功'
        logger.warning(f"{data}")
    except Exception as e:
        InterVariable.update(vid, unit, {'status':2})
        data['status'] = '失败'
        data['msg'] = '填充中间点历史数据失败'
        logger.warning(f"{data}")
        logger.warning(f"{e}")
        traceback.print_exc()
    if vid in processes:
        processes.pop(vid)


def add_inter_vavriables(var_name_list, var_value_list, remark_list, system_list, sys_name_list, unit):
    """
        多进程批量创建填充中间变量历史数据
        ---------
        Args:
            var_name_list: 中间变量点名列表
            var_value_list: 中间变量计算公式列表
            remark_list: 中间变量描述列表
            unit: 机组号
        ----------
        Returns:
        ----------
    """
    now_timestamp = int(time.time())
    start_timestamp = int(Changestamp(Normaltime('2022-01-01 00:00:00')))
    start_timestamp = max(now_timestamp - 60*60*24*365, start_timestamp)
    end_timestamp = now_timestamp
    start_time = Normaltime(Localtime(start_timestamp))
    end_time = Normaltime(Localtime(end_timestamp))
    start_timestamp = int(Changestamp(start_time))
    end_timestamp = int(Changestamp(end_time))
    total = end_timestamp - start_timestamp
    pool_size = 10
    for i in range(len(var_name_list)):
        try:
            # 建一个进程池
            # pool = multiprocessing.Pool(pool_size)
            if point_check_eval(var_value_list[i]) is not None:
                vid, msg = InterVariable.create(var_name_list[i], var_value_list[i], remark_list[i], -1, unit)
                if vid:
                    # 每条记录的对应系统可能有多个
                    systems = str(system_list[i]).split(' ')
                    sys_list_filter, confs = [], []
                    for sys in systems:
                        if sys in sys_name_list.keys():
                            sys_list_filter.append(sys_name_list.get(sys))
                    
                    for cid in sys_list_filter:
                        confs.append(OriginPointSystemConfig(origin_point=var_name_list[i], system_config=cid).to_dict())
                    if len(confs):
                        OriginPointSystemConfig.upsert_all(records=confs)
                    
                    write_origin_points_to_redis(origin_point=False, inter_variable=True)
                    InterVariable.update(vid, unit, {'status':0})
                    while start_timestamp < end_timestamp:
                        #每8个小时创建一个进程
                        temp_timastamp = start_timestamp + 28800
                        if temp_timastamp >  end_timestamp:
                            temp_timastamp = end_timestamp
                        # pool.apply_async(fill_data_process, (start_timestamp, temp_timastamp, var_name_list[i], var_value_list[i]), error_callback=lambda x: print(x))
                        fill_data_process(start_timestamp, temp_timastamp, var_name_list[i], var_value_list[i])
                        start_timestamp = temp_timastamp
                        cur_process = round((end_timestamp - start_timestamp) / total * 100 , 2)
                        InterVariable.update(vid, unit, {'process': 100.00 - cur_process})
                    # pool.close()
                    # pool.join()
                    InterVariable.update(vid, unit, {'status':1})
                    InterVariable.update(vid, unit, {'process': 100.00})
            else:
                continue
        except Exception as e:
            print('error!!!!!')
            traceback.print_exc()
            continue
    
    


