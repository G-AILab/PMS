import json
import math

import numpy as np
from flask_app import redis, result_redis
from iapws import iapws97
from iapws import IAPWS97
from . import glovar
from .glovar import *
import datetime
import arrow


coef = list()

# latest = redis.read('latest')
dict_RS={}
def RS(in1,in2,in3):#in1置位点号，in2复位点号，in3输出保持时间秒/RS触发器标签
    if type(in2) == str:
        time3 = 600 if in3 == '' or in3 == 'nan' or in3 == 0 else in3
        a="DCS"+str(in1)+str(in2)+str(time3)
        out = dict_RS[a] if a in dict_RS.keys() else [0,0]
        if glovar.CDATA[in1] == 0 and glovar.CDATA[in2] == 0 :#置位为0，复位为0，输出保持
            if out[1] < time3:
                out[0] = out[0]
                out[1] += 1
            else:#输出强制为0
                out[0] = 0
        if glovar.CDATA[in2] == 1:#复位为1，输出为0
            out =[0,0]
        if glovar.CDATA[in1] == 1 and glovar.CDATA[in2] == 0:#置位为1，复位为0，输出为1
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


def variance(point_name, duration):
    duration_values = get_his(point_name, [0,duration])
    duration_variance = np.var(duration_values)  # type: ignore
    return duration_variance


def yc(point_name, yc_type='regression'):
    # 在redis中获取回归模型预测结果
    key = '{}-{}-{}'.format(point_name,yc_type, 'latest')
    res = result_redis.read(key)
    if res is None:
        raise KeyError(point_name)
    return  json.loads(res)['pred']['value']
        


def PackRE(pointname,bite):
    '''
    打包点解析，点名，第几位
    '''
    strPackname= bin(int(glovar.CDATA[pointname]))
    # glovar.PRINt(glovar.CDATA[pointname], pointname,strPackname)
    Packbite=len(strPackname)-1-bite
    if len(strPackname)<=bite:
        Packdata=0
    else :
        Packdata =strPackname[Packbite]
    return (Packdata) 


def Sfunline(A,B):
    '''
    折线函数
    '''
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


def AVG(pointname, LDtime):
    '''
    求点名历史均值
    '''
    his_data = get_his(pointname, [0, LDtime])
    AVG = np.average(his_data) if len(his_data) > 0 else np.nan
    return (AVG)


def Frequency(pointname,A):#求固定时间的频率
    Frequency_num = 0
    list_hisF=get_his(pointname,[0,A])
    AVG=np.average(list_hisF) if len(list_hisF) > 0 else np.nan
    for i in range (A-1):
        if list_hisF[i]>AVG and list_hisF[i+1]<AVG:
            Frequency_num+=1
            i=min(i+5,A)        
    return (Frequency_num)
    

def FILTER(pointname, A): #滤波
    B = get_his(pointname, [0, A])
    B = [x for x in B if x != None]
    avg = (np.sum(B) - np.max(B) - np.min(B)) / (len(B) - 2)
    return B[0] * 0.5 + avg * 0.5


def FILTER1(pointname, A): #滤波
    B = get_his(pointname, [0, A])
    return ( np.average([x for x in B if x != None]))


def Flugel(G, P01, Pz1, P0, Pz, T0, Tz1):#弗留格尔公示，G额度流量,P01进汽压力,Pz1排汽压力,P0额定工况进汽压力,Pz额定工况排汽压力,T0额定排汽温度,Tz1排汽温度
    G1 = G * (math.sqrt((P01 * P01 - Pz1 * Pz1)/(P0 * P0 - Pz * Pz)) * math.sqrt((T0 + 273.15)/(Tz1 + 273.15)))     
    return (G1)


def get_his(pointname: str, timen: list, ts:bool=False):
    '''
    从redis中获取过去一段时间某个点的值
    ----------
    Args:
        pointname: 点名
        timen: 长度为1时timen[0]表示指定时间点(过去第timen[0]秒)；长度为2时表示[结束时间偏移(较小值)，开始时间偏移(较大值)]
    Returns:
        res: 若timen长度为2则返回list，为1则返回float
    '''
    latest_ts = redis.read('latest')
    if len(timen) == 1:
        target_ts = int(latest_ts) - timen[0]
        # res = redis.hget(str(target_ts), pointname)
        res = redis.read('{}@{}'.format(target_ts, pointname))
        res = float(res) if res else None
        return (res)

    elif len(timen) == 2:
        start_ts = int(latest_ts) - timen[1]
        end_ts = int(latest_ts) - timen[0]
        key_list = ['{}@{}'.format(ts, pointname) for ts in range(end_ts - 1, start_ts - 1, -1)]
        p_res = redis.redis_client.mget(*key_list)
        # with redis.redis_client.pipeline() as p:
        #     for timestamp in range(end_ts - 1, start_ts - 1, -1):
        #         # p.hmget(max_key-i, *model_handler.use_cols)
        #         p.hmget(str(timestamp), pointname)
        #     p_res = p.execute()
        res = list()
        for pv in p_res:
            if pv is not None:
                res.append(float(pv))
        if ts:
            return res, latest_ts
        return (res)


def BODONG(pointname, TIMELEN, D):
    # global glovar.CDATA, Dhistime
    fd = 10
    aa = np.zeros(int(TIMELEN))
    MAX = np.zeros(fd)
    MIN = np.zeros(fd)
    AVG = np.zeros(fd)
    VAR = np.zeros(fd)
    bb = [[0 for i in range(int(TIMELEN/fd))] for i in range (fd)]  # 定义一个二维数组    
    aa=get_his(pointname,[0,TIMELEN])
    for k in range (fd):
        for i in range (int(TIMELEN/glovar.Dhistime/fd)):
            bb[k][i]=aa[i+k*int(TIMELEN/fd)]
        MAX[k]=max(bb[k][:]) 
        MIN[k]=min(bb[k][:])
        AVG[k]=sum(bb[k][:])/int(TIMELEN/fd)
        VAR[k]=np.var(bb[k][:])
               
    MAXmax=max(MAX)
    AVGmax=max(AVG)
    MINmin=min(MIN)
    AVGmin=min(AVG)
        
    if MAXmax > AVGmax+D:
        flag = 1
    if MINmin < AVGmin-D:
        flag = -1
    if MAXmax > AVGmax+D and MINmin < AVGmin-D :
        flag =2
    if MAXmax <= AVGmax+D and MINmin >= AVGmin-D :
        flag =0        
    return (flag)


def modV1(a,in1,in2,in3,in4,in5,in6):#1开度指令、2门前压力、3门后压力,4温度，5初始流量
    try:
        if a in glovar.dict_MODOUT.keys():
            out = glovar.dict_MODOUT[a]
        else:
            out =np.zeros(3)
            out[1]=in4+273.15
            if in6==0:
                out[2]=in5/math.sqrt(in2-in3)/in1
            else:
                out[2]=in6
        out[0]=out[2]*in1*math.sqrt(max(in2-in3,0))*math.sqrt(out[1]/(in4+273.15))
        glovar.dict_MODOUT.update({a:out})    #out0流量，out1初始温度，out[2]导通系数，
        return (out)
    except TypeError as e:
        logger.debug('modV1({}) TypeError'.format(a))
        return glovar.dict_MODOUT[a] if a in glovar.dict_MODOUT else None


def modV(a,in1,in2,in3,in4,in5):#1开度指令、2同支路串联阀门等效开度、3并联阀门导纳、4门前压力、5门后压力
    # global deltat,coef#0空缺0,1行程时间、2最大导纳、3是否有串联阀门（0无、1有）、4层流紊流转换压力、5是否允许倒流（0允许，1不允许）    
    #out1开度，out2导纳，out3同支路阀门总等效开度，out4串并联阀门支路总导纳,out5总流量，out6总线导，out7开度（0-100），
    if a in glovar.dict_MODOUT.keys():
        out = glovar.dict_MODOUT[a]
    else:
        out =np.zeros(8)
    step=1/coef[1]
    step_sum=abs(in1-out[1])
    for vvvvvv in range (5):
        if step_sum<step:
            step=step_sum
        if out[1]<in1:
            out[1]=out[1]+step
        if out[1]>in1:
            out[1]=out[1]-step
    out[1]=max(min(out[1],100),0)#开度
    out[2]=out[1]*coef[2]#导纳
    if coef[3]==1:#有串联阀门
        out[3]=out[1]*in2#总开度
        out[4]=out[2]*in2+in3
    if coef[3]==0:#无串联阀门
        out[3]=out[1]
        out[4]=out[2]+in3
    deltap = in4-in5
    cond = out[4]
    if deltap<0 :
        deltap= in5-in4#将差压转换为正
        if coef[5]==0:
            cond = -out[4]#导纳
        if coef[5]==1:#差压小于0，不允许倒流
            cond = 0#导纳
    if deltap < coef[4]:#差压小于紊流压力大于0
        out[5] = cond*deltap/coef[4]        
        out[6] = out[4]/coef[4]
    if deltap >=coef[4]:#差压大于紊流压力
        out[5] = cond*math.sqrt(deltap)
        out[6] = out[4]/math.sqrt(deltap)
        #out[5] = ((out[1]+-step)*coef[2]+in3)*math.sqrt(in4-in5)
    glovar.dict_MODOUT.update({a:out})
    #out1开度，out2导纳，out3同支路阀门总等效开度，out4串并联阀门支路总导纳,out5总流量，out6总线导，out7开度（0-100），
    return(out)


def modP(a,in1,in2,in3,in4,in5,in6,in7,in8,in9,in10,in11,in12,in13,in14,in15,in16,in17,in18,in19,in20,in21):
    #1-10进入节点导纳、压力、、、、11-20流出节点导纳压力、、 21微小流量
    # global deltat,coef#1空缺0,2微小流量系数（-1）    
    if a in glovar.dict_MODOUT.keys():
        out = glovar.dict_MODOUT[a]
    else:
        out =np.zeros(1)
    alpha=0.001/1
    B1_in=in1
    P1_in=in2
    B2_in=in3
    P2_in=in4
    B3_in=in5
    P3_in=in6
    B4_in=in7
    P4_in=in8
    B5_in=in9
    P5_in=in10
    B1_out=in11
    P1_out=in12
    B2_out=in13
    P2_out=in14
    B3_out=in15
    P3_out=in16
    B4_out=in17
    P4_out=in18
    B5_out=in19
    P5_out=in20
    INBP  = B1_in*P1_in   + B2_in*P2_in   + B3_in*P3_in   + B4_in*P4_in   + B5_in*P5_in
    OUTBP = B1_out*P1_out + B2_out*P2_out + B3_out*P3_out + B4_out*P4_out + B5_out*P5_out
    WEXT= in21*coef[1]
    sumB=B1_in+B2_in+B3_in+B4_in+B5_in+B1_out+B2_out+B3_out+B4_out+B5_out
    out[0]=(alpha*out[0]+INBP+OUTBP+WEXT)/(alpha+sumB)
    glovar.dict_MODOUT.update({a:out})
    return(out)


def modBP(a,in1,in2,in3,in4,in5):#1入口静压、2转速0-1、3性能降低率0-1、4进出口阀门总开度、5出口压力
    # global deltat,coef#1空缺0,1最高扬程、2额定工作点扬程、3额定工作点流量、   
    #out0流量，out0扬程，out2线导，out3下游节点压力,out4上游节点压力
    if a in glovar.dict_MODOUT.keys():
        out = glovar.dict_MODOUT[a]
    else:
        out =np.zeros(5)
    pmax0=coef[0]
    pa = coef[1]
    wa = coef[2]
    k = (pmax0-pa)/(wa*wa)    
    spd = in2
    mdeg = in3
    out[1]=pmax0*spd*spd*(1-mdeg)    
    opv = in4
    cond = opv/math.sqrt(k)   
    pin = in1
    plh = out[1]
    pout= in5
    deltaP1 = pin+plh-pout
    deltaP = max(deltaP1,0)
    out[0] = cond*math.sqrt(deltaP)
    if deltaP==0:
        out[2] = 0
    else:
        out[2] = abs(out[0]/deltaP)
    out[3] = pin +plh
    out[4] = pout - plh
    glovar.dict_MODOUT.update({a:out})
    #out1开度，out2导纳，out3同支路阀门总等效开度，out4串并联阀门支路总导纳,out5总流量，out6总线导，out7开度（0-100），
    return(out)


def modZLBP(a,in1,in2,in3,in4,in5):#1入口静压、2转速0-1、3性能降低率0-1、4进出口阀门总开度、5出口压力
    # global deltat,coef#1空缺0,1最高扬程、2额定工作点扬程、3额定工作点流量、   
    #out0流量，out0扬程，out2线导，out3下游节点压力,out4上游节点压力
    if a in glovar.dict_MODOUT.keys():
        out = glovar.dict_MODOUT[a]
    else:
        out =np.zeros(5)
    pmax0=coef[0]
    pa = coef[1]
    wa = coef[2]
    k = (pmax0-pa)/(wa*wa)    
    spd = in2
    mdeg = in3
    out[1]=pmax0*spd*spd*(1-mdeg)    
    opv = in4
    cond = opv/math.sqrt(k)   
    pin = in1
    plh = out[1]
    pout= in5
    deltaP1 = pin+plh-pout
    deltaP = max(deltaP1,0)
    out[0] = cond*deltaP/0.15
    if deltaP==0:
        out[2] = 0
    else:
        out[2] = abs(out[0]/deltaP)
    out[3] = pin +plh
    out[4] = pout - plh
    glovar.dict_MODOUT.update({a:out})
    #out1开度，out2导纳，out3同支路阀门总等效开度，out4串并联阀门支路总导纳,out5总流量，out6总线导，out7开度（0-100），
    return(out)


#水箱模型
def modTANK(a,in1,in2,in3,in4,in5):#1进入流量、2留出流量、3初始水位,4温度，5复位信号,
    # global coef#1质量水位转换系数,   
    #out0水箱质量，out1水箱水位，
    if a in glovar.dict_MODOUT.keys() and in5==0:
        out = glovar.dict_MODOUT[a]
    else:
        out =np.zeros(2)
        out[0]=in3/1000/coef[0]
        out[1]=in3
    TANK_M=in1-in2
    out[0]=out[0]+TANK_M/3600
    out[1]=out[0]*coef[0]
    glovar.dict_MODOUT.update({a:out})    
    return(out)


def BESTScore1(pointname,LARGE_SYS,sub_SYS,KIND,pre_data,H_data,L_data,HH_data,LL_data):  # 新点，期望值为当前值
    pass


def GUIDE2(pointname,LARGE_SYS,sub_SYS,KIND,pre_data,HH_data,TRIGGER_data):  # 新点，期望值为当前值
    pass


def prewarning3(pointname, LARGE_SYS, sub_SYS, KIND, HH_data, LL_data, TRIGGER_data, BADTIME_data):  # 根据点上下限报警
    pass


def prewarning4(pointname,LARGE_SYS,sub_SYS,KIND,pre_data,H_data,L_data,HH_data,LL_data,TRIGGER_data,BADTIME_data):  # 根据点上下限报警
    pass


def TRANSFER5(pointname,B):  # 传点
    pass


def get_sys_score(sort_list):
    pass


def init_point_check_env():
    '''
    初始化点检查，进行一系列中间量计算等工作
    '''
    global coef

    glovar.CDATA.update({'N3DCS.3TEES213AI': glovar.CDATA['N3DCS.3TEES234AI'] + 20})
    if glovar.CDATA['N3DCS.3FTCD323AI'] > 71 and glovar.time_numb > 2:#超量程更新数据库
        glovar.CDATA.update({'N3DCS.3FTCD323AI': glovar.VmakeupCTR[5] / 1000})#补给水流量
    p = iapws97._PSat_T(float(glovar.CDATA['N3DCS.3TEHD112AI']) + 273.15)
    Hwaterflow = float(glovar.CDATA['N3DCS.3FTFW070X']+glovar.CDATA['N3DCS.3FTFW112AI']+glovar.CDATA['N3DCS.3FTFW113AI']+glovar.CDATA['N3DCS.3FTFW085AI']+glovar.CDATA['N3DCS.3FTFW111AI'])
    steamflow8 = (IAPWS97(T=float(glovar.CDATA['N3DCS.3TEFW066AI'])+273.15,P=float(glovar.CDATA['N3DCS.3PTFW089AI']/1000)).h-IAPWS97(T=float(glovar.CDATA['N3DCS.3TEFW064AI'])+273.15,P=float(glovar.CDATA['N3DCS.3PTFW089AI']/1000)).h)\
        *Hwaterflow/(IAPWS97(T=float(glovar.CDATA['N3DCS.3TEES202AI'])+273.15,P=float(glovar.CDATA['N3DCS.3PTES207AI'])).h-IAPWS97(T=float(glovar.CDATA['N3DCS.3TEHD112AI'])+273.15,P=max(float(glovar.CDATA['N3DCS.3PTES207AI']),p+0.0001)).h)#8抽汽流量
    glovar.CDATA.update({'N3DCS.8STEAMEXT': steamflow8})
    p=iapws97._PSat_T(float(glovar.CDATA['N3DCS.3TEHD120AI'])+273.15)
    steam7=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEES233AI'])+273.15,P=float(glovar.CDATA['N3DCS.3PTES226AI']))
    water7=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEHD120AI'])+273.15,P=max(float(glovar.CDATA['N3DCS.3PTES226AI']),p+0.0001))
    water7out=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEFW064AI'])+273.15,P=float(glovar.CDATA['N3DCS.3PTFW089AI']/1000))
    water7in=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEFW062AI'])+273.15,P=float(glovar.CDATA['N3DCS.3PTFW089AI']/1000))
    steamflow7=((water7out.h-water7in.h)*Hwaterflow - (IAPWS97(T=float(glovar.CDATA['N3DCS.3TEHD112AI'])+273.15,P=max(float(glovar.CDATA['N3DCS.3PTES207AI']),p+0.0001)).h-water7.h)*steamflow8)/(steam7.h-water7.h)#7抽汽流量
    glovar.CDATA.update({'N3DCS.7STEAMEXT':steamflow7})
    p=iapws97._PSat_T(float(glovar.CDATA['N3DCS.3TEHD107AI'])+273.15) #计算饱和压力 #计算饱和温度iapws97._TSat_P(15.5)
    steam6=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEES213AI'])+273.15,P=float(glovar.CDATA['N3DCS.3PTES236AI']))
    water6=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEHD107AI'])+273.15,P=max(float(glovar.CDATA['N3DCS.3PTES236AI']),p+0.0001))
    water6out=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEFW062AI'])+273.15,P=float(glovar.CDATA['N3DCS.3PTFW089AI']/1000))
    water6in  = IAPWS97(T=float(glovar.CDATA['N3DCS.3TEFW059AI'])+273.15,P=float(glovar.CDATA['N3DCS.3PTFW089AI']/1000))
    steamflow6=((water6out.h-water6in.h)*Hwaterflow - (water7.h-water6.h)*(steamflow8+steamflow7))/(steam6.h-water6.h)
    glovar.CDATA.update({'N3DCS.6STEAMEXT':steamflow6})#6抽汽流量

    p=iapws97._PSat_T(float(glovar.CDATA['N3DCS.3TECD344AI'])+273.15) #计算饱和压力 #计算饱和温度iapws97._TSat_P(15.5)
    steamtoDEA5 = IAPWS97(T=float(glovar.CDATA['N3DCS.3TEES220AI'])+273.15,P=float(glovar.CDATA['N3DCS.3OPXA']+glovar.CDATA['N3DCS.3OPXB']+glovar.CDATA['N3DCS.3OPXC'])/3000)
    water5in    = IAPWS97(T=float(glovar.CDATA['N3DCS.3TECD342AI']+10)+273.15,P=float(glovar.CDATA['N3DCS.3PTCD418AI']/1000))
    DEAwater    = IAPWS97(P=max(float(glovar.CDATA['N3DCS.3PTES241AI']/1000),0.1),x=0)#除氧器压力下的饱和水
    steamtoDEAflow = ((DEAwater.h - water5in.h)*float(AVG('N3DCS.3FTCD363AI',30)) -(steamflow6+steamflow7+steamflow8)*(water6.h-DEAwater.h)) /(steamtoDEA5.h - DEAwater.h)
    glovar.CDATA.update({'N3DCS.5STEAMTODEAF':0 if glovar.CDATA['N3DCS.3ZTES022AI']>10 else steamtoDEAflow})
    glovar.CDATA.update({'N3DCS.3STEAMIPEXH':Flugel(841,(glovar.CDATA['N3DCS.3PTES236AI']*1000+101)/0.835,glovar.CDATA['N3DCS.OPX']+80,2183,1020,343.1,glovar.CDATA['N3DCS.3IPEXT1'])})
    Lwaterflow=float(AVG('N3DCS.3FTCD363AI',100)-AVG('GR.DQ_AI05.CH06.PV',100))
    p=iapws97._PSat_T(float(glovar.CDATA['N3DCS.3TEHD139AI'])+273.15)
    steam4=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEES291AI'])+273.15,P=float((glovar.CDATA['N3DCS.3PTES302AI']+100)/1000))
    water4=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEHD139AI'])+273.15,P=max(float((glovar.CDATA['N3DCS.3PTES302AI']+100)/1000),p+0.0001))
    water4out=IAPWS97(T=float(glovar.CDATA['N3DCS.3TECD354AI'])+273.15,P=(float(glovar.CDATA['N3DCS.3PTCD418AI']+100)/1000))
    water4in =IAPWS97(T=float(glovar.CDATA['N3DCS.3TECD356AI'])+273.15,P=(float(glovar.CDATA['N3DCS.3PTCD418AI']+100)/1000))
    steamflow4=max(water4out.h-water4in.h,0)*Lwaterflow/(steam4.h-water4.h)
    glovar.CDATA.update({'N3DCS.4STEAMEXT':steamflow4})

    p=iapws97._PSat_T(float(glovar.CDATA['N3DCS.3TEHD131AI'])+273.15)
    steam3=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEES293AI'])+273.15,P=float((glovar.CDATA['N3DCS.3PTES308AI']+100)/1000))
    water3=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEHD131AI'])+273.15,P=max(p+0.000001,float((glovar.CDATA['N3DCS.3PTES308AI']+100)/1000))) #压力测点稍有偏差（计算疏水温度对应的饱和压力＋10KPA）
    water3out=IAPWS97(T=float(glovar.CDATA['N3DCS.3TECD356AI'])+273.15,P=(float(glovar.CDATA['N3DCS.3PTCD418AI']+100)/1000))
    water3in =IAPWS97(T=float(glovar.CDATA['N3DCS.3TECD358AI'])+273.15,P=(float(glovar.CDATA['N3DCS.3PTCD418AI']+100)/1000))
    steamflow3=max((max(water3out.h-water3in.h,0)*Lwaterflow - (water4.h-water3.h)*steamflow4)/min(steam3.h-water3.h,500),0)    
    glovar.CDATA.update({'N3DCS.3STEAMEXT':steamflow3})

#    glovar.PRINt(water3out.h,water3in.h,Lwaterflow,water4.h,water3.h,steamflow4,steam3.h-water3.h)

    p=iapws97._PSat_T(float(glovar.CDATA['N3DCS.3TEHD147AI'])+273.15)#2号低加疏水温度对应的饱和压力
    t=iapws97._TSat_P(float(glovar.CDATA['N3DCS.3PTES284AI']+101)/1000)
    ps=iapws97._PSat_T(float(glovar.CDATA['N3DCS.3TEES280AI'])+273.15)#抽汽温度对应的饱和压力
    steam2=IAPWS97(T=max(float(glovar.CDATA['N3DCS.3TEES280AI'])+273.15,t),P=min(float(glovar.CDATA['N3DCS.3PTES284AI']+101)/1000,ps-0.000001))
    water2=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEHD147AI'])+273.15,P=max(p+0.000001,float((glovar.CDATA['N3DCS.3PTES284AI']+101)/1000)))
    LTEW = IAPWS97(T=float(glovar.CDATA['N3DCS.3TELE017AI'])+273.15,P=float(glovar.CDATA['N3DCS.3PTLE013AI'])+0.1)
    Hwaterout2 = min(max((water3in.h*Lwaterflow - LTEW.h*glovar.CDATA['N3DCS.3FTLE016AI'])/ (Lwaterflow-glovar.CDATA['N3DCS.3FTLE016AI']),20),1000)

    Hwaterout22 = IAPWS97(h=Hwaterout2,P=glovar.CDATA['N3DCS.3PTCD332AI']/1000)
    Tup = max(glovar.CDATA['N3DCS.3TECD325AI'] - glovar.CDATA['N3DCS.3TECD321AI'],0)
    water2out=IAPWS97(T=max(Hwaterout22.T,glovar.CDATA['N3DCS.3TECD325AI']+Tup+273.15),P=(float(glovar.CDATA['N3DCS.3PTCD418AI']+160)/1000))
    water2in =IAPWS97(T=float(glovar.CDATA['N3DCS.3TECD325AI'])+273.15,P=(float(glovar.CDATA['N3DCS.3PTCD418AI']+160)/1000))
    steamflow2=(max(water2out.h-water2in.h,0)*Lwaterflow - (water3.h-water2.h)*(steamflow4+steamflow3))/(steam2.h-water2.h)
    glovar.CDATA.update({'N3DCS.2STEAMEXT':steamflow2})
    #1抽汽流量
    p=iapws97._PSat_T(float(glovar.CDATA['N3DCS.3TEES283AI'])+273.15)#1号低加疏水温度对应的饱和压力
    steam1=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEES283AI'])+273.15,P=min(p-0.00000001,float(glovar.CDATA['N3DCS.3PTES286AI']+101)/1000))
    water1=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEHD151AI'])+273.15,P=max(p+0.000001,float(glovar.CDATA['N3DCS.3PTES286AI']+101)/1000))
    water1out=IAPWS97(T=float(glovar.CDATA['N3DCS.3TECD325AI'])+273.15,P=(float(glovar.CDATA['N3DCS.3PTCD418AI']+160)/1000))
    water1in =IAPWS97(T=float(glovar.CDATA['N3DCS.3TECD321AI']+glovar.CDATA['N3DCS.3TECD302AI'])/2+273.15,P=(float(glovar.CDATA['N3DCS.3PTCD418AI']+160)/1000))
    steamflow1=(max(water1out.h-water1in.h,0)*Lwaterflow - (water2.h-water1.h)*(steamflow4+steamflow3+glovar.CDATA['N3DCS.2STEAMEXT']))/(steam1.h-water1.h)
    glovar.CDATA.update({'N3DCS.1STEAMEXT':steamflow1})

    REHSTEAMFLOW01=glovar.CDATA['N3DCS.3PTES236AI']*408+4+glovar.CDATA['N3DCS.3FTFS401AI']+glovar.CDATA['N3DCS.3FTCR122AI']+glovar.CDATA['N3DCS.7STEAMEXT']
    REHSTEAMFLOW02 =glovar.CDATA['N3DCS.3CCSMSFLOW']-glovar.CDATA['N3DCS.3FTFS401AI']-glovar.CDATA['N3DCS.3FTCR122AI'] - glovar.CDATA['N3DCS.8STEAMEXT'] - glovar.CDATA['N3DCS.7STEAMEXT']
    REHSTEAMFLOW=max(REHSTEAMFLOW01,REHSTEAMFLOW02)
    LPsteamFLOW1 = REHSTEAMFLOW-glovar.CDATA['N3DCS.3NAAEXFT02AI']-glovar.CDATA['N3DCS.3NAAEXFT03AI']- glovar.CDATA['N3DCS.3FTES262AI']-glovar.CDATA['N3DCS.3FTES263AI']- glovar.CDATA['N3DCS.6STEAMEXT'] -glovar.CDATA['N3DCS.5STEAMTODEAF']
    LPsteamFLOW2= Lwaterflow - glovar.CDATA['N3DCS.3FTES262AI']-glovar.CDATA['N3DCS.3FTES263AI']
    LPsteamFLOW04=glovar.CDATA['N3DCS.3PTES302AI']*1.6102+13.475
    LPsteamFLOW001=[LPsteamFLOW1,LPsteamFLOW2,LPsteamFLOW04]
    STEAMIPEXH=Flugel(841,(glovar.CDATA['N3DCS.3PTES236AI']*1000+101)/0.835,glovar.CDATA['N3DCS.OPX']+80,2183,1020,343.1,glovar.CDATA['N3DCS.3IPEXT1'])
    LPsteamFLOW3=STEAMIPEXH-steamtoDEAflow-glovar.CDATA['N3DCS.3NAAEXFT02AI']-glovar.CDATA['N3DCS.3NAAEXFT03AI']-glovar.CDATA['N3DCS.3FTES262AI']-glovar.CDATA['N3DCS.3FTES263AI']
    LPsteamFLOW= np.max(LPsteamFLOW001)
    LPsteamFLOW= LPsteamFLOW3

    LPoutsteamFLOW01 = REHSTEAMFLOW-glovar.CDATA['N3DCS.3NAAEXFT02AI']-glovar.CDATA['N3DCS.3NAAEXFT03AI']- glovar.CDATA['N3DCS.3FTES262AI']-glovar.CDATA['N3DCS.3FTES263AI']- glovar.CDATA['N3DCS.6STEAMEXT'] -glovar.CDATA['N3DCS.5STEAMTODEAF'] -glovar.CDATA['N3DCS.4STEAMEXT']-glovar.CDATA['N3DCS.3STEAMEXT']-glovar.CDATA['N3DCS.2STEAMEXT']-glovar.CDATA['N3DCS.1STEAMEXT']
    LPoutsteamFLOW02=AVG('N3DCS.3FTCD363AI',30) - glovar.CDATA['N3DCS.3NAAEXFT02AI']-glovar.CDATA['N3DCS.3NAAEXFT03AI'] - glovar.CDATA['N3DCS.3FTES262AI']-glovar.CDATA['N3DCS.3FTES263AI']-glovar.CDATA['N3DCS.4STEAMEXT']-glovar.CDATA['N3DCS.3STEAMEXT']-glovar.CDATA['N3DCS.2STEAMEXT']-glovar.CDATA['N3DCS.1STEAMEXT']
    LPoutsteamFLOW03=((glovar.CDATA['N3DCS.3PTES286AI']+101)+0.7688)/45.161*1000
    LPoutsteamFLOW04=LPsteamFLOW-glovar.CDATA['N3DCS.4STEAMEXT']-glovar.CDATA['N3DCS.3STEAMEXT']-glovar.CDATA['N3DCS.2STEAMEXT']-glovar.CDATA['N3DCS.1STEAMEXT']
    LPoutsteamFLOW0=[LPoutsteamFLOW01,LPoutsteamFLOW02,LPoutsteamFLOW03]
    LPoutsteamFLOW = LPoutsteamFLOW04#原来是2
    glovar.CDATA.update({'N3DCS.LPOUTSTEAMFLOW':LPoutsteamFLOW})

    steamNFQ=IAPWS97(T=float(glovar.CDATA['N3DCS.3TEAS108AI'])+273.15,P=glovar.CDATA['N3DCS.3PTAS106AI'])
    waterNFQ=IAPWS97(T=100+273.15,P=glovar.CDATA['N3DCS.3PTAS106AI'])
    A=glovar.CDATA['N3DCS.3FTBA025AAI']*1000*(glovar.CDATA['N3DCS.3TEBA001AAI']-glovar.CDATA['N3DCS.30HSK21CT101'])*1+glovar.CDATA['N3DCS.3FTBA026AAI']*1000*(glovar.CDATA['N3DCS.3TEBA002AAI']-glovar.CDATA['N3DCS.30HSK22CT101'])
    B=steamNFQ.h-waterNFQ.h
    glovar.CDATA.update({'N3DCS.3FNFQ':A/B/1000})#保留
#    给水系统建模
#     _thread.start_new_thread(c.set_values, (rev, list))
    for numclc in range (50):
        #A汽泵
        #A汽泵转速标要化
        coef = [1.586,1.129,650000]#最大扬程、额定扬程、额定流量
        glovar.BPAF=modBP('BPAF',glovar.CDATA['N3DCS.3PTCD373AI'],glovar.CDATA['N3DCS.3FPTWS1A']/5680,0,1,glovar.PAin)#A前置泵
        coef = [0,-1]
        glovar.PAin=modP('glovar.PAin',glovar.BPAF[2],glovar.BPAF[3],0,2,0,3,0,4,0,5,glovar.BPA[2],glovar.BPA[4],0,2,0,3,0,4,0,5,0.01)#A汽泵主泵入口压力
        coef = [25.54,19.399,650000]
        glovar.BPA=modBP('BPA',glovar.PAin,glovar.CDATA['N3DCS.3FPTWS1A']/5680,0,1,glovar.PAout)#A汽泵主泵
        coef = [0,-1]
        glovar.PAout=modP('glovar.PAout',glovar.BPA[2],glovar.BPA[3],glovar.VBPAh[6],glovar.PABCOUT,0,3,0,4,0,5,glovar.VBPAOUT[6],glovar.PABCOUT,glovar.VBPAclc[6],glovar.CDATA['N3DCS.3PTCD373AI'],0,3,0,4,0,5,1)#A汽泵主泵出口压力
        coef = [0,1,10500,0,0.0002,1]
        glovar.VBPAOUT=modV('VBglovar.PAout',glovar.CDATA['N3DCS.3ZOFW002DI']*100,1,0,glovar.PAout,glovar.PABCOUT)#A汽泵出口门
        coef = [0,1,610,0,0.002,1]
        glovar.VBPAclc=modV('VBPAclc',min(glovar.CDATA['N3DCS.3ZTFW031AI']+8,100),1,0,glovar.PAout,glovar.CDATA['N3DCS.3PTCD373AI'])#A汽泵再循环门
        coef = [0,1,100,0,0.0002,0]
        glovar.VBPAh=modV('VBPAh',0,1,0,glovar.PABCOUT,glovar.PAout)#A暖泵门
        #B汽泵
        #B汽泵转速标要化
        coef = [1.58,1.15,675000]
        glovar.BPBF=modBP('BPBF',glovar.CDATA['N3DCS.3PTCD387AI'],glovar.CDATA['N3DCS.3FPTWS1B']/5680,0,1,glovar.PBin)#B前置泵
        coef = [0,-1]
        glovar.PBin=modP('glovar.PBin',glovar.BPBF[2],glovar.BPBF[3],0,2,0,3,0,4,0,5,glovar.BPB[2],glovar.BPB[4],0,2,0,3,0,4,0,5,0.01)#B汽泵主泵入口压力
        coef = [25.958,19.276,675000]
        glovar.BPB=modBP('BPB',glovar.PBin,glovar.CDATA['N3DCS.3FPTWS1B']/5680,0,1,glovar.PBout)#B汽泵主泵
        coef = [0,-1]
        glovar.PBout=modP('glovar.PBout',glovar.BPB[2],glovar.BPB[3],glovar.VBPBh[6],glovar.PABCOUT,0,3,0,4,0,5,glovar.VBPBOUT[6],glovar.PABCOUT,glovar.VBPBclc[6],glovar.CDATA['N3DCS.3PTCD387AI'],0,3,0,4,0,5,1)#B汽泵主泵出口压力
        coef = [0,1,10500,0,0.0002,1]
        glovar.VBPBOUT=modV('VBglovar.PBout',glovar.CDATA['N3DCS.3ZOFW004DI']*100,1,0,glovar.PBout,glovar.PABCOUT)#B汽泵出口门
        coef = [0,1,610,0,0.002,1]
        glovar.VBPBclc=modV('VBPBclc',glovar.CDATA['N3DCS.3ZTFW033AI']+6,1,0,glovar.PBout,glovar.CDATA['N3DCS.3PTCD387AI'])#B汽泵再循环门
        coef = [0,1,100,0,0.0002,0]
        glovar.VBPBh=modV('VBPBh',0,1,0,glovar.PABCOUT,glovar.PBout) #B暖泵门
        #电泵
        KDM=max(glovar.CDATA['N3DCS.3STFW02PAI']/5150,0)#电泵转速标要化
        coef = [1.58,0.9,450000]
        glovar.BPMF=modBP('BPMF',glovar.CDATA['N3DCS.3PTCD365AI'],KDM,0,1,glovar.PMin)#电泵前置泵
        coef = [0,-1]
        glovar.PMin=modP('glovar.PMin',glovar.BPMF[2],glovar.BPMF[3],0,2,0,3,0,4,0,5,glovar.BPM[2],glovar.BPM[4],0,2,0,3,0,4,0,5,0.01)#电泵主泵入口压力

        coef = [22.5,19,450000]
        glovar.BPM=modBP('BPM',glovar.PMin,KDM,0,1,glovar.PMout)#电泵主泵
        coef = [0,-1]
        glovar.PMout=modP('glovar.PMout',glovar.BPM[2],glovar.BPM[3],0,2,0,3,0,4,0,5,glovar.VBPMOUT[6],glovar.PABCOUT,glovar.VBPMclc[6],glovar.CDATA['N3DCS.3PTCD365AI'],0,3,0,4,0,5,glovar.VBPMclc[6]*0.001)#电泵主泵出口压力
        coef = [0,1,10500,0,0.0002,1]
        glovar.VBPMOUT=modV('VBglovar.PMout',glovar.CDATA['N3DCS.3ZOFW007DI']*100,1,0,glovar.PMout,glovar.PABCOUT)#电泵出口门
        coef = [0,1,610,0,0.002,1]
        glovar.VBPMclc=modV('VBPMclc',glovar.CDATA['N3DCS.3ZTFW035AI'],1,0,glovar.PMout,glovar.CDATA['N3DCS.3PTCD365AI'])#电泵再循环门
        coef = [0,1,500,0,0.2,0]
        glovar.VBPBh=modV('VBPBh',0,1,0,glovar.PABCOUT,glovar.PMout) #电泵暖泵门
        PDd=glovar.PABCOUT-glovar.CDATA['N3DCS.3PTFW542AI']/1000#FW014后的压力
        #给水母管压力
        coef = [0,-1]
        glovar.PABCOUT=modP('glovar.PABCOUT',glovar.VBPAOUT[6],glovar.PAout,glovar.VBPBOUT[6],glovar.PBout,glovar.VBPMOUT[6],glovar.PMout,0,4,0,5,glovar.V_FW014[6],glovar.P_FW014OUT,glovar.V_FA[6],PDd,glovar.V_FB[6],PDd,glovar.V_SA[6],PDd,glovar.V_SB[6],PDd,0.01)
        dp11 = (glovar.CDATA['N3DCS.3FTFW070BAI'] * 1000 / max(glovar.V_FW014[4], 0.0000001)) * (glovar.CDATA['N3DCS.3FTFW070BAI'] * 1000 / max(glovar.V_FW014[4], 0.0000001))
        if numclc<3 and glovar.time_numb<2 :
            glovar.P_FW014OUT = max(glovar.PABCOUT-0.1,0.01)
        else :
            glovar.P_FW014OUT = glovar.PABCOUT-dp11
        coef = [0,1,16800,0,0.0001,1]
#        V_FW014=modV('V_FW014',glovar.CDATA['N3DCS.3ZTFW014AI'],1,0,glovar.PABCOUT,glovar.PABCOUT-0.01)
        glovar.V_FW014=modV('V_FW014',100,1,0,glovar.PABCOUT,glovar.P_FW014OUT)

        coef = [0,1,200,1,0.002,1]
        glovar.V_FA=modV('V_FA',glovar.CDATA['N3DCS.3TVFW521AAO'],glovar.CDATA['N3DCS.3ZOFW017DI'],glovar.CDATA['N3DCS.3TVFW521BAO']*300,glovar.CDATA['N3DCS.3PTFW542AI']/1000,0)
        coef = [0,1,210,1,0.002,1]
        glovar.V_FB=modV('V_FB',glovar.CDATA['N3DCS.3TVFW522AAO'],glovar.CDATA['N3DCS.3ZOFW025DI'],glovar.CDATA['N3DCS.3TVFW522BAO']*270,glovar.CDATA['N3DCS.3PTFW542AI']/1000,0)
        coef = [0,1,300,1,0.002,1]
        glovar.V_SA=modV('V_SA',glovar.CDATA['N3DCS.3ZTFW523AAI'],glovar.CDATA['N3DCS.3ZOFW021DI'],0,glovar.CDATA['N3DCS.3PTFW542AI']/1000,0)
        coef = [0,1,250,1,0.002,1]
        glovar.V_SB=modV('V_SB',glovar.CDATA['N3DCS.3ZTFW524AAI'],glovar.CDATA['N3DCS.3ZOFW029DI'],0,glovar.CDATA['N3DCS.3PTFW542AI']/1000,0)

    glovar.CDATA.update({'N3DCS.3HDCISDT':abs(glovar.CDATA['N3DCS.3HDCIS1']-glovar.CDATA['N3DCS.3HDCIS2'])})#氢冷器出口温差
    glovar.CDATA.update({'Hwaterflow':Hwaterflow})#保留
    glovar.CDATA.update({'F1':glovar.VBPAclc[5]/1000})#保留
    glovar.CDATA.update({'F2':glovar.VBPBclc[5]/1000})#保留
    glovar.CDATA.update({'F3':glovar.VBPMclc[5]/1000})#保留

    #高加疏水，除氧器水位建模
    for i in range (10):
        coef = [0,1,6.0,0,6.5,1]
        V8HPDR=modV('V8HPDR',Sfunline(glovar.CDATA['N3DCS.3ZTHD002AI'],[0,1,10,10,20,20,30,30,40,40,50,50,60,60,101,100]),1,0,(glovar.CDATA['N3DCS.3PTES207AI']),(glovar.CDATA['N3DCS.3PTES226AI']))
        coef = [0,1,6.1,0,2.5,1]
        V7HPDR=modV('V7HPDR',Sfunline(glovar.CDATA['N3DCS.3ZTHD005AI'],[0,1,10,10,20,20,30,30,40,40,50,50,60,60,101,100]),1,0,(glovar.CDATA['N3DCS.3PTES226AI']),(glovar.CDATA['N3DCS.3PTES236AI']))
        coef = [0,1,3,0,0.00002,1]
        V6HPDR=modV('V6HPDR',Sfunline(glovar.CDATA['N3DCS.3ZTHD008AI'],[0,1,10,10,20,20,30,30,40,40,50,50,60,60,101,100]),1,0,(glovar.CDATA['N3DCS.3PTES236AI']),(FILTER('N3DCS.3PTES313AI',10)+FILTER('N3DCS.3PTES241AI',10))/2000)
    if abs(glovar.CDATA['N3DCS.3LTCD341AI'])> 150 :
        reset=0
        glovar.CDATA.update({'N3DCS.3LTCD341AI':glovar.DEAtank[1]*1000-2750})
         #超量程后用计算值替换变送器值
    else:
        reset=1
    coef = [0.02291667]
    glovar.DEAtank = modTANK('DEAtank',AVG('N3DCS.3FTCD363AI',30)+V6HPDR[5]+steamtoDEAflow*0.8,Hwaterflow+glovar.CDATA['N3DCS.3FTFW082S'],2750+glovar.CDATA['N3DCS.3LTCD341AI'],120,0)
    glovar.CDATA.update({'V6HPDR[5]':V6HPDR[5]})#保留
    glovar.CDATA.update({'V7HPDR[5]':V7HPDR[5]})#保留
    glovar.CDATA.update({'V8HPDR[5]':V8HPDR[5]})#保留

    glovar.VHP8 = modV1('VHP8',glovar.CDATA['N3DCS.3ZTHD002AI'],glovar.CDATA['N3DCS.3PTES207AI'],glovar.CDATA['N3DCS.3PTES226AI'],glovar.CDATA['N3DCS.3TEHD112AI'],glovar.CDATA['N3DCS.8STEAMEXT'],1.334)#1开度指令、2门前压力、3门后压力,4温度，5初始流量
    glovar.VHP7 = modV1('VHP7',glovar.CDATA['N3DCS.3ZTHD005AI'],glovar.CDATA['N3DCS.3PTES226AI'],glovar.CDATA['N3DCS.3PTES236AI'],glovar.CDATA['N3DCS.3TEHD120AI'],glovar.CDATA['N3DCS.7STEAMEXT']+glovar.CDATA['N3DCS.8STEAMEXT'],2.41275)
    glovar.VHP6 = modV1('VHP6',glovar.CDATA['N3DCS.3ZTHD008AI'],glovar.CDATA['N3DCS.3PTES236AI'],min(glovar.CDATA['N3DCS.3PTES236AI']-0.1,(FILTER('N3DCS.3PTES313AI',6)+FILTER('N3DCS.3PTES241AI',6))/2000),glovar.CDATA['N3DCS.3TEHD107AI'],glovar.CDATA['N3DCS.8STEAMEXT']+glovar.CDATA['N3DCS.7STEAMEXT']+glovar.CDATA['N3DCS.6STEAMEXT'],3.0)


    #补给水系统建模
    makeup=0
    for makeup in range (50):
        coef = [0,1,1800,0,0.0000002,1]
        glovar.VmakeupIN=modV('VmakeupIN',100,1,0,0.1+glovar.CDATA['N3DCS.3LTCD398AI']/100000,glovar.Pmakeupin)#补给水泵入口门
        coef = [0,-1]
        glovar.Pmakeupin=modP('Pmakeupin',glovar.VmakeupIN[6],0.1+glovar.CDATA['N3DCS.3LTCD398AI']/100000,glovar.VmakeupACLC[6],glovar.Pmakeupout,glovar.VmakeupBCLC[6],glovar.Pmakeupout,0,4,0,5,glovar.BPAmakeup[2],glovar.BPAmakeup[4],glovar.BPBmakeup[2],glovar.BPBmakeup[4],0,3,0,4,0,5,0.01)#补给水泵入口压力
        coef = [0,1,50,0,0.0000002,1]
        glovar.VmakeupACLC=modV('VmakeupACLC',50*glovar.CDATA['N3DCS.3ZACD04PADI'],1,0,glovar.Pmakeupout,glovar.Pmakeupin)#A补给水泵再循环门
        coef = [1.2,0.633,52240]#最大扬程、额定扬程、额定流量
        glovar.BPAmakeup=modBP('BPAmakeup',glovar.Pmakeupin,glovar.CDATA['N3DCS.3ZACD04PADI'],0,1,glovar.Pmakeupout)#A补给水泵
        coef = [0,1,50,0,0.00000002,1]
        glovar.VmakeupBCLC=modV('VmakeupBCLC',50*glovar.CDATA['N3DCS.3ZACD04PBDI'],1,0,glovar.Pmakeupout,glovar.Pmakeupin)#B补给水泵再循环门
        coef = [1.2,0.633,52240]#最大扬程、额定扬程、额定流量
        glovar.BPBmakeup=modBP('BPBmakeup',glovar.Pmakeupin,glovar.CDATA['N3DCS.3ZACD04PBDI'],0,1,glovar.Pmakeupout)#B补给水泵
        coef = [0,-1]
        glovar.Pmakeupout=modP('Pmakeupout',glovar.BPAmakeup[2],glovar.BPAmakeup[3],glovar.BPBmakeup[2],glovar.BPBmakeup[3],0,3,0,4,0,5,glovar.VmakeupACLC[6],glovar.Pmakeupin,glovar.VmakeupBCLC[6],glovar.Pmakeupin,glovar.VmakeupGUP[6],glovar.PmakeupoutUP,0,4,0,5,1)#补给水泵出口压力
        coef = [0,1,1000,0,0.00000002,0]
        glovar.VmakeupGUP=modV('VmakeupGUP',100,1,0,glovar.Pmakeupout,glovar.Pmakeupout-0.06)#上升段管路
        coef = [0,-1]
        glovar.PmakeupoutUP=modP('PmakeupoutUP',glovar.VmakeupGUP[6],glovar.Pmakeupout,0,2,0,3,0,4,0,5,0,1,0,2,glovar.VmakeupCTR[6],glovar.CDATA['N3DCS.3CNDP1']/1000,0,4,0,5,1)
        DN=700
        coef = [0,1,DN,1,0.00000002,1]
        glovar.VmakeupCTR=modV('VmakeupCTR',Sfunline(glovar.CDATA['N3DCS.3ZTCD046AI'],[-5,1,10,8,20,15,30,25,40,35,50,45,60,60,101,100]),1,glovar.CDATA['N3DCS.3ZOCD050DI']*100*DN,glovar.PmakeupoutUP,glovar.CDATA['N3DCS.3CNDP1']/1000)#补给水泵出口门
    if glovar.time_numb ==0:
        reset = 1
    if glovar.time_numb !=0:
        if get_his('N3DCS.3ZOCD260DI',[1])!=get_his('N3DCS.3ZOCD260DI',[0]):
            reset = 1
        else:
            reset = 0
    coef = [0.03727]
    glovar.makeuptank = modTANK('makeuptank',glovar.CDATA['N3DCS.3ZOCD260DI']*117.660,glovar.CDATA['N3DCS.3FTCD323AI'],glovar.CDATA['N3DCS.3LTCD398AI'],20,reset)
#    strname= bin(int(glovar.CDATA['N3DCS.3DBY0070']))#打包点解压

#    #主蒸汽量、总煤量、开发区供汽量、供热抽汽1，供热抽汽2，负荷
    AVG('N3DCS.3CCSMSFLOW',360),AVG('N3DCS.3CCSTTCOALFL',360),AVG('N3DCS.3FTFS401AI',360),AVG('N3DCS.3NAAEXFT03AI',360),AVG('N3DCS.3NAAEXFT02AI',360),AVG('N3DCS.3JTMP010S',360)
    MSTEAMflowGX=max(AVG('N3DCS.3CCSMSFLOW',360)/(AVG('N3DCS.3FTFS401AI',360)/3.7+(AVG('N3DCS.3NAAEXFT03AI',360)+AVG('N3DCS.3NAAEXFT02AI',360))/4.5+AVG('N3DCS.3JTMP010S',360)),0.0001)
    glovar.numbmill=glovar.CDATA['N3DCS.3ZACH11CPDI']+glovar.CDATA['N3DCS.3ZACH12CPDI']+glovar.CDATA['N3DCS.3ZACH13CPDI']+glovar.CDATA['N3DCS.3ZACH14CPDI']
    glovar.CDATA.update({'N3DCS.3MAXLOAD':min(glovar.numbmill*53,165)/max(AVG('N3DCS.3CCSTTCOALFL',100),0.0001)*AVG('N3DCS.3CCSMSFLOW',100)/MSTEAMflowGX- AVG('N3DCS.3FTFS401AI',100)/3.7 - (AVG('N3DCS.3NAAEXFT03AI',100)+AVG('N3DCS.3NAAEXFT02AI',100))/4.5})

    #VCV8404
    for i in range(20):
        coef = [0,1,360,0,0.02,1]
        glovar.VCV8404=modV('VCV8404',glovar.CDATA['N3DCS.3ZTFS404AI'],1,min(max(glovar.CDATA['N3DCS.3ZTFS403AI'],0),100)*60,glovar.CDATA['N3DCS.3CRHP'],glovar.CDATA['N3DCS.3PTFS402AI'])

    #8抽汽流量经验值
    glovar.STEAMEXT8_FLOW=Sfunline(glovar.CDATA['N3DCS.3CCSMSFLOW'],[0,0,200,25,300,30,400,38,560,49,750,75,1060,110,1160,120])
    #7抽汽流量经验值
    glovar.STEAMEXT7_FLOW=Sfunline(glovar.CDATA['N3DCS.3CCSMSFLOW'],[0,0,200,20,300,20,400,28,560,34,750,60,1060,75,1160,90])
    #6抽汽流量经验值
    glovar.STEAMEXT6_FLOW=Sfunline(glovar.CDATA['N3DCS.3CCSMSFLOW'],[0,0,200,15,300,18,400,25,560,33,750,50,1060,60,1160,80])
    #潮位折算水位
    if glovar.CDATA['N3DCS.3ZACW01PADI']==1 and glovar.CDATA['N3DCS.3ZACW01PBDI']==1 :
        glovar.HZCWIN=Sfunline((glovar.CDATA['N4DCS.4LTCW205AI']+glovar.CDATA['N4DCS.4LTCW215AI'])/2,[0,0,0.15,0.1,0.2,0.5,0.4,1,0.6,3,0.75,4,1,4,1000000,5])-2
    else :
        glovar.HZCWIN=Sfunline((glovar.CDATA['N4DCS.4LTCW205AI']+glovar.CDATA['N4DCS.4LTCW215AI'])/2,[0,0,0.15,0,0.2,0.1,0.4,0.4,0.6,3,0.75,4,1,4,100000,5])
    #凝汽器端差
    TERMITDIF = float(glovar.CDATA['N3DCS.3LP1GNT']+glovar.CDATA['N3DCS.3LP1GVT'])/2-(float(glovar.CDATA['N3DCS.3TECW243AI']+glovar.CDATA['N3DCS.3TECW253AI'])/2)
    glovar.CDATA.update({'N3DCS.3TERMITDIF':TERMITDIF})
    #循环水系统建模
    condssA,condssB= 3200,3200
    NORA,NORB=condssA,condssB
    A=50
    for i in range (A):
        #入口门导纳        #出口门导纳
        condin,condinout=1450,2280
        KD1=Sfunline(glovar.CDATA['N3DCS.3ZTCW005AI'],[-5,0,10,8,20,25,30,35,45,50,55,70,60,90,105,105])  #出口门开度
        KD2=Sfunline(glovar.CDATA['N3DCS.3ZTCW006AI'],[-5,0,10,8,20,25,30,35,45,50,55,70,60,90,105,105])
        if i<1:
            P_VCWOUT=0.0001
            glovar.VCWOUT[4]=0.001
        coef = [0,-1]
        dpCW =(glovar.VALOUT[5]+glovar.VBROUT[5])*0.2/glovar.VCWOUT[4]
        glovar.PCWOUT=modP('PCWOUT',glovar.VLDOWN[6],glovar.PLIN,glovar.VRDOWN[6],glovar.PRIN,0,3,0,4,0,5,glovar.VCWOUT[6],0,100,0,0,3,0,4,0,5,0.01)
        if i<3 and glovar.time_numb<2:
            P_VCWOUT = glovar.PCWOUT-0.01
        else :
            P_VCWOUT = glovar.PCWOUT-dpCW
        coef = [0,1,15000,0,0.2,1]#出口总管路
        glovar.VCWOUT=modV('VCWOUT',100,1,0,glovar.PCWOUT,P_VCWOUT)
        #B侧逆洗门
        coef = [0,1,2000,0,0.2,0]
        glovar.VBRREF=modV('VBRREF',glovar.CDATA['N3DCS.3ZOCW042DI']*100,1,0,glovar.PRIN,glovar.PROUT)
        #B侧出口门
        coef = [0,1,condinout,0,0.2,1]
        glovar.VBROUT=modV('VBROUT',KD2,1,0,glovar.PROUT,glovar.PCWOUT)
        #B侧出口压力
        coef = [0,-1]
        glovar.PROUT=modP('PROUT',glovar.VRUP[6],glovar.PRM,glovar.VBRREF[6],glovar.PRIN,0,3,0,4,0,5,glovar.VBROUT[6],glovar.PCWOUT,0,2,0,3,0,4,0,5,0.01)
        #R侧上部
        coef = [0,1,condssB,0,0.2,0]
        glovar.VRUP=modV('VRUP',100,1,0,glovar.PRM,glovar.PROUT)
        #B侧中间压力
        coef = [0,-1]
        glovar.PRM=modP('PRM',glovar.VRDOWN[6],glovar.PRIN,0,2,0,3,0,4,0,5,glovar.VRUP[6],glovar.PROUT,glovar.VABLR[6],glovar.PLM,0,3,0,4,0,5,0.01)
        #B侧下部
        coef = [0,1,condssB,0,0.2,0]
        glovar.VRDOWN=modV('VRDOWN',100,1,0,glovar.PRIN,glovar.PRM)
        #B侧入口压力
        coef = [0,-1]
        glovar.PRIN=modP('PRIN',glovar.VBRIN[6],glovar.PABCWOUT,0,2,0,3,0,4,0,5,glovar.VRDOWN[6],glovar.PRM,glovar.VBRREF[6],glovar.PROUT,0,3,0,4,0,5,0.01)
        #B侧入口门
        coef = [0,1,condin,0,0.2,1]
        glovar.VBRIN=modV('VBRIN',glovar.CDATA['N3DCS.3ZTCW004AI'],1,0,glovar.PABCWOUT,glovar.PRIN)
        #大联络门
        coef = [0,1,condinout*1.9,0,0.2,0]
        glovar.VABLR=modV('VABLR',glovar.CDATA['N3DCS.3ZOCW043DI']*100,1,0,glovar.PLM,glovar.PRM)
        #A侧出口门
        coef = [0,1,condinout,0,0.2,1]
        glovar.VALOUT=modV('VALOUT',KD1,1,0,glovar.PLOUT,glovar.PCWOUT)
        #A侧逆洗门
        coef = [0,1,2000,0,0.2,0]
        glovar.VALREF=modV('VALREF',glovar.CDATA['N3DCS.3ZOCW041DI']*100,1,0,glovar.PLIN,glovar.PLOUT)
        #A侧出口压力
        coef = [0,-1]
        glovar.PLOUT=modP('glovar.PLOUT',glovar.VLUP[6],glovar.PLM,glovar.VALREF[6],glovar.PLIN,0,3,0,4,0,5,glovar.VALOUT[6],glovar.PCWOUT,0,2,0,3,0,4,0,5,0.01)
        #A侧上部
        coef = [0,1,condssA,0,0.2,0]
        glovar.VLUP=modV('VLUP',100,1,0,glovar.PLM,glovar.PLOUT)
        #A侧中间压力
        coef = [0,-1]
        glovar.PLM=modP('glovar.PLM',glovar.VLDOWN[6],glovar.PLIN,0,2,0,3,0,4,0,5,glovar.VLUP[6],glovar.PLOUT,glovar.VABLR[6],glovar.PRM,0,3,0,4,0,5,0.01)
        #A侧下部
        coef = [0,1,condssA,0,0.2,0]
        glovar.VLDOWN=modV('VLDOWN',100,1,0,glovar.PLIN,glovar.PLM)
        #A侧入口压力
        coef = [0,-1]
        glovar.PLIN=modP('PLIN',glovar.VALIN[6],glovar.PABCWOUT,0,2,0,3,0,4,0,5,glovar.VLDOWN[6],glovar.PLM,glovar.VALREF[6],glovar.PLOUT,0,3,0,4,0,5,0.01)
        #A侧入口门
        coef = [0,1,condin,0,0.2,1]
        glovar.VALIN=modV('VALIN',glovar.CDATA['N3DCS.3ZTCW003AI'],1,0,glovar.PABCWOUT,glovar.PLIN)
        #循泵出口母管压力
        coef = [0,-1]
        glovar.PABCWOUT=modP('PABCWOUT',glovar.VACWOUT[6],glovar.PACWOUT,glovar.VBCWOUT[6],glovar.PBCWOUT,0,3,0,4,0,5,glovar.VALIN[6],glovar.PLIN,glovar.VBRIN[6],glovar.PRIN,0,3,0,4,0,5,0.01)
         #B循泵出口门
        coef = [0,1,500,0,0.2,1]
        glovar.VBCWOUT=modV('VBCWOUT',glovar.CDATA['N3DCS.3ZOCW002DI']*100,1,0,glovar.PBCWOUT,glovar.PABCWOUT)
        #B循泵出口压力
        coef = [0,-1]
        glovar.PBCWOUT=modP('PBCWOUT',glovar.BPBCW[2],glovar.BPBCW[3],0,2,0,3,0,4,0,5,glovar.VBCWOUT[6],glovar.PABCWOUT,0,2,0,3,0,4,0,5,100)
         #B循泵
        coef = [0.33493,0.1846,21742]
        glovar.BPBCW=modBP('BPBCW',glovar.CDATA['N3DCS.3LTCW201AI']*0.01+glovar.HZCWIN*0.01,glovar.CDATA['N3DCS.3ZACW01PBDI'],0,glovar.CDATA['N3DCS.3ZOCW002DI'],glovar.PBCWOUT)
        #A循泵出口门
        coef = [0,1,500,0,0.2,1]
        glovar.VACWOUT=modV('VACWOUT',glovar.CDATA['N3DCS.3ZOCW001DI']*100,1,0,glovar.PACWOUT,glovar.PABCWOUT)
        #A循泵出口压力
        coef = [0,-1]
        glovar.PACWOUT=modP('PACWOUT',glovar.BPACW[2],glovar.BPACW[3],0,2,0,3,0,4,0,5,glovar.VACWOUT[6],glovar.PABCWOUT,0,2,0,3,0,4,0,5,1)
#       #A循泵
        coef = [0.298,0.175,21742]
        glovar.BPACW=modBP('BPACW',glovar.CDATA['N3DCS.3LTCW201AI']*0.01+glovar.HZCWIN*0.01,glovar.CDATA['N3DCS.3ZACW01PADI'],0,glovar.CDATA['N3DCS.3ZOCW001DI'],glovar.PACWOUT)
        if i<(A/2):
            if  glovar.PLIN*1000 < glovar.CDATA['N3DCS.3PTCW239AI']-0.1 :
                condssA -= 50
                condssA=min(condssA,NORA)
            if  glovar.PLIN*1000 > glovar.CDATA['N3DCS.3PTCW239AI']+0.1 :
                condssA += 50
                condssA=min(condssA,NORA)
            if  glovar.PRIN*1000 < glovar.CDATA['N3DCS.3PTCW249AI']-0.1 :
                condssB -= 50
                condssB=min(condssB,NORB)
            if  glovar.PRIN*1000 > glovar.CDATA['N3DCS.3PTCW249AI']+0.1 :
                condssB += 50
                condssB=min(condssB,NORB)
            CNAQJD=condssA/NORA
            CNBQJD=condssB/NORB
            N3DCS_3CWFLOW=glovar.VALOUT[5]+glovar.VBROUT[5]
        else:
            condssA=NORA
            condssB=NORB
            N3DCS_3CWFLOW1=glovar.VALOUT[5]+glovar.VBROUT[5]
    #汽蚀裕量计算
    water_fw = IAPWS97(T=glovar.CDATA['N3DCS.3TECD344AI']+273.15,P=glovar.PAin[0]+0.1013)
    Ps = glovar.PAin[0]*1000+101.3 #主泵入口压力
    Pv=iapws97._PSat_T(glovar.CDATA['N3DCS.3TECD344AI']+273.15)*1000#除氧器温度对应的饱和压力
    rho = water_fw.rho/1000 #密度
    g = 9.8
    Vs = glovar.CDATA['N3DCS.3FTFW104AI']*1000/(0.25*math.pi*0.265*0.265*3600*water_fw.rho)#流速
    NpsHA1 =Ps/(rho*g)  + (Vs*Vs)/(2*g) - Pv/(rho*g) #汽蚀余量

    Pe = glovar.CDATA['N3DCS.3PTES241AI']+101.3#除氧器压力
    Hd = 22#吸上高度
    DH = glovar.PAin[0]*100 - glovar.CDATA['N3DCS.3PTCD373AI']*100#前置泵扬程
    NpsHA_forepump = (Pe-Pv)/(rho*g) + Hd #前置泵汽蚀余量
    NpsHA2 = NpsHA_forepump + DH#汽蚀余量2

    water_fw = IAPWS97(T=glovar.CDATA['N3DCS.3TECD344AI']+273.15,P=glovar.PBin[0]+0.1013)
    Ps = glovar.PBin[0]*1000+101.3 #主泵入口压力
    Pv=iapws97._PSat_T(glovar.CDATA['N3DCS.3TECD344AI']+273.15)*1000#除氧器温度对应的饱和压力
    rho = water_fw.rho/1000 #密度
    g = 9.8
    Vs = glovar.CDATA['N3DCS.3FTFW107AI']*1000/(0.25*math.pi*0.265*0.265*3600*water_fw.rho)#流速
    NpsHB1 =Ps/(rho*g)  + (Vs*Vs)/(2*g) - Pv/(rho*g) #汽蚀余量

    Pe = glovar.CDATA['N3DCS.3PTES241AI']+101.3#除氧器压力
    Hd = 22#吸上高度
    DH = glovar.PBin[0]*100 - glovar.CDATA['N3DCS.3PTCD387AI']*100#前置泵扬程
    NpsHB_forepump = (Pe-Pv)/(rho*g) + Hd #前置泵汽蚀余量
    NpsHB2 = NpsHB_forepump + DH#汽蚀余量2

    # 火检冷却风机
    glovar.ASECTE = [glovar.CDATA['N3DCS.3TEBA400A1AI'],glovar.CDATA['N3DCS.3TEBA400A2AI'],glovar.CDATA['N3DCS.3TEBA400A3AI'],glovar.CDATA['N3DCS.3TEBA400A4AI'],glovar.CDATA['N3DCS.3TEBA400A5AI'],glovar.CDATA['N3DCS.3TEBA400A6AI']]
    glovar.BSECTE = [glovar.CDATA['N3DCS.3TEBA400B1AI'],glovar.CDATA['N3DCS.3TEBA400B2AI'],glovar.CDATA['N3DCS.3TEBA400B3AI'],glovar.CDATA['N3DCS.3TEBA400B4AI'],glovar.CDATA['N3DCS.3TEBA400B5AI'],glovar.CDATA['N3DCS.3TEBA400B6AI']]
    glovar.CSECTE = [glovar.CDATA['N3DCS.3TEBA400C1AI'],glovar.CDATA['N3DCS.3TEBA400C2AI'],glovar.CDATA['N3DCS.3TEBA400C3AI'],glovar.CDATA['N3DCS.3TEBA400C4AI'],glovar.CDATA['N3DCS.3TEBA400C5AI'],glovar.CDATA['N3DCS.3TEBA400C6AI']]
    glovar.DSECTE = [glovar.CDATA['N3DCS.3TEBA400D1AI'],glovar.CDATA['N3DCS.3TEBA400D2AI'],glovar.CDATA['N3DCS.3TEBA400D3AI'],glovar.CDATA['N3DCS.3TEBA400D4AI'],glovar.CDATA['N3DCS.3TEBA400D5AI'],glovar.CDATA['N3DCS.3TEBA400D6AI']]
    # 吹灰调阀
    coef = [0,1,24,1,0.002,1]
    glovar.V_SOOTBLOWERSTEAM=modV('V_SOOTBLOWERSTEAM',glovar.CDATA['N3DCS.3ZTSB520AI'],1 if glovar.CDATA['N3DCS.3PTSB520AI']>500 else 0,0,glovar.CDATA['N3DCS.3PTMS101AI'],glovar.CDATA['N3DCS.3PTSB520AI']/1000)
    glovar.numboilsso = glovar.CDATA['N3DCS.3ZOFO601DI']+glovar.CDATA['N3DCS.3ZOFO602DI']+glovar.CDATA['N3DCS.3ZOFO603DI']+glovar.CDATA['N3DCS.3ZOFO604DI']+glovar.CDATA['N3DCS.3ZOFO605DI']+glovar.CDATA['N3DCS.3ZOFO606DI']+\
    glovar.CDATA['N3DCS.3ZOFO607DI']+glovar.CDATA['N3DCS.3ZOFO608DI']+glovar.CDATA['N3DCS.3ZOFO609DI']+glovar.CDATA['N3DCS.3ZOFO610DI']+glovar.CDATA['N3DCS.3ZOFO611DI']+glovar.CDATA['N3DCS.3ZOFO612DI']+\
    glovar.CDATA['N3DCS.3ZOFO613DI']+glovar.CDATA['N3DCS.3ZOFO614DI']+glovar.CDATA['N3DCS.3ZOFO615DI']+glovar.CDATA['N3DCS.3ZOFO616DI']+glovar.CDATA['N3DCS.3ZOFO617DI']+glovar.CDATA['N3DCS.3ZOFO618DI']+\
    glovar.CDATA['N3DCS.3ZOFO619DI']+glovar.CDATA['N3DCS.3ZOFO620DI']+glovar.CDATA['N3DCS.3ZOFO621DI']+glovar.CDATA['N3DCS.3ZOFO622DI']+glovar.CDATA['N3DCS.3ZOFO623DI']+glovar.CDATA['N3DCS.3ZOFO624DI']

    for i in range (10):
        coef = [0,1,118,1,0.02,1]
        glovar.VREHEATSPRAYVALVE=modV('VREHEATSPRAYVALVE',glovar.CDATA['N3DCS.3ZTFW530AI'],glovar.CDATA['N3DCS.3ZOFW044DI'],0,glovar.CDATA['N3DCS.3PTFW083AI']/1000,glovar.CDATA['N3DCS.3PTCR116AI'])
    
    # 机组状态
    if glovar.CDATA['N3DCS.3BM04614'] == 1:
        glovar.tub_zt = 0  # 停机状态
    else :
        if glovar.CDATA['N3DCS.3BM04614'] == 0:
            if glovar.CDATA['N3DCS.3TEBT008AI']<100 or glovar.CDATA['N3DCS.3TEBT007AI']<100 :
                glovar.tub_zt = 1  # MFT复位，升温升压<100℃
            else :
                if glovar.CDATA['N3DCS.3ECSGC001DI'] == 1:
                    glovar.tub_zt = 2  # MFT复位，升温升压>100℃，冲转中
                else :
                    glovar.tub_zt = 3  # 并网以后
    
    # 高加泄露诊断算法
    yc_v1, yc_v2, yc_v3 = yc('N3DCS.3ZTHD002AI'), yc('N3DCS.3ZTHD005AI'), yc('N3DCS.3ZTHD008AI')
    F8 = max(glovar.CDATA['N3DCS.3ZTHD002AI'] + 5 - yc_v1, 0) if yc_v1 else None
    F7 = max(glovar.CDATA['N3DCS.3ZTHD005AI'] - yc_v2 - 5, 0) if yc_v2 else None
    F6 = max(glovar.CDATA['N3DCS.3ZTHD008AI'] - yc_v3, 0) if yc_v3 else None
    glovar.VHP8 = modV1('VHP8',F8,glovar.CDATA['N3DCS.3PTES207AI'],glovar.CDATA['N3DCS.3PTES226AI'],glovar.CDATA['N3DCS.3TEHD112AI'],glovar.CDATA['N3DCS.8STEAMEXT'],1.334)#1开度指令、2门前压力、3门后压力,4温度，5初始流量
    glovar.VHP7 = modV1('VHP7',F7,glovar.CDATA['N3DCS.3PTES226AI'],glovar.CDATA['N3DCS.3PTES236AI'],glovar.CDATA['N3DCS.3TEHD120AI'],glovar.CDATA['N3DCS.7STEAMEXT']+glovar.CDATA['N3DCS.8STEAMEXT'],2.41275)
    glovar.VHP6 = modV1('VHP6',F6,glovar.CDATA['N3DCS.3PTES236AI'],min(glovar.CDATA['N3DCS.3PTES236AI']-0.1,(FILTER('N3DCS.3PTES313AI',6)+FILTER('N3DCS.3PTES241AI',6))/2000),glovar.CDATA['N3DCS.3TEHD107AI'],glovar.CDATA['N3DCS.8STEAMEXT']+glovar.CDATA['N3DCS.7STEAMEXT']+glovar.CDATA['N3DCS.6STEAMEXT'],3.0)
    W_net876=np.array([glovar.VHP8[0],glovar.VHP7[0],glovar.VHP6[0]])
    W_mod876=np.array([max(AVG('V8HPDR[5]', 300)-AVG('N3DCS.8STEAMEXT',300),glovar.VHP8[0]),max(AVG('V7HPDR[5]',300)-AVG('V8HPDR[5]',300)-AVG('N3DCS.7STEAMEXT',300),glovar.VHP7[0]),max(AVG('V6HPDR[5]',300)-AVG('V7HPDR[5]',300)-AVG('N3DCS.6STEAMEXT',300),glovar.VHP6[0])])
    LW_net876=np.sqrt(sum(W_net876*W_net876))
    LW_mod876=np.sqrt(sum(W_mod876*W_mod876))
    n= max(sum(W_net876*W_mod876)/max(LW_net876*LW_mod876,0.000000000001),0)
    glovar.HHEATERFD_zhixindu=max(n*(np.max(W_net876)/20)*(np.max(W_mod876)/20),0)
