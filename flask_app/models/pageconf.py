from datetime import datetime
from typing import Union
from flask_app import db
from flask_app import session_maker
import json
from json import JSONDecodeError
import decimal

class Pageconf(db.Model):
    __tablename__ = 'pageconf'
    page = db.Column(db.String(50),primary_key=True)
    component = db.Column(db.String(100),primary_key=True)
    value = db.Column(db.JSON)
    unit = db.Column(db.Integer,primary_key=True)

    def __repr__(self):
        return f'<Pageconf {self.page} - {self.component}>'
    
    def to_json(self):
        return {
            'page': self.page,
            'component': self.component,
            'value': self.value,
            'unit': self.unit,
        }   
    
    # 只是应急方法。之后应该在每次添加机组时进行而不是每次查询时进行
    @classmethod
    def insert_empty_comp_val(cls, page, unit, db_session):
        # comps/mapper都写死了
        comps = ['出力系数', '发电煤耗', '环保指标', '系统评分', '耗能分析']
        mapper = {
            '出力系数': {'point_list': []},
            '环保指标': {'point_list': []},
            '耗能分析': {'point_list': []},
            '发电煤耗': {'point_history': []},
            '系统评分': {'system_list': []}
        }
        exist_comps = set()
        exist_comps_tuples = db_session.query(Pageconf.component).filter(cls.page == page, cls.unit == unit).all()
        for comp in exist_comps_tuples:
            exist_comps.add(comp[0])
        comps = [comp for comp in comps if comp not in exist_comps]
        
        for comp in comps:
            pageconf = Pageconf(page=page, component=comp, value=mapper.get(comp), unit=unit)
            db_session.add(pageconf)
            db_session.commit()
            db_session.refresh(pageconf)
            db_session.expunge(pageconf)
    
    @classmethod
    def insert_empty_val(cls, page, comp, unit, db_session):
        mapper = {
            '出力系数': {'point_list': []},
            '环保指标': {'point_list': []},
            '耗能分析': {'point_list': []},
            '发电煤耗': {'point_history': []},
            '系统评分': {'system_list': []}
        }
        # pageconf = db_session.query(Pageconf).filter(cls.page == page, cls.component == comp, cls.unit == unit).first()
        # if not pageconf:
        pageconf = Pageconf(page=page, component=comp, value=mapper.get(comp), unit=unit)
        db_session.add(pageconf)
        db_session.commit()
        db_session.refresh(pageconf)
        db_session.expunge(pageconf)
    
    @classmethod
    def get_by_page(cls, page, unit):
        with session_maker() as db_session:
            cls.insert_empty_comp_val(page, unit, db_session)
            pageconfs = db_session.query(Pageconf).filter(cls.page == page, cls.unit == unit).all()
            for pageconf in pageconfs:
                db_session.expunge(pageconf)
            return pageconfs, len(pageconfs)
        
    @classmethod
    def get_by_page_component(cls, page, component, unit):
        with session_maker() as db_session:
            pageconf = db_session.query(Pageconf).filter(cls.page == page, cls.component == component, cls.unit==unit).first()
            if pageconf is not None:
                db_session.expunge(pageconf)
            else:
                cls.insert_empty_val(page, component, unit, db_session)
            return pageconf

    @classmethod
    def get_all(cls):
        with session_maker() as db_session:
            pageconfs = db_session.query(Pageconf).filter().all()
            total = 0
            for pageconf in pageconfs:
                db_session.expunge(pageconf)
                total += 1
            return pageconfs, total
        
    @classmethod
    def create(cls, page,component,value, unit):
        with session_maker() as db_session:
            pageconf = Pageconf(page=page, component=component, value=value, unit=unit)
            db_session.add(pageconf)
            db_session.commit()
            db_session.refresh(pageconf)
            db_session.expunge(pageconf)
            return pageconf
        
    @classmethod
    def update(cls, page,component,unit,data):
        with session_maker() as db_session:
            db_session.query(Pageconf).filter(Pageconf.page == page, Pageconf.component==component, Pageconf.unit == unit).update(data)
            return 
        
        
    @classmethod
    def update_value(cls, page,component,value, unit):
        with session_maker() as db_session:
            db_session.query(Pageconf).filter(Pageconf.page == page, Pageconf.component==component).update({'value':value})
            return
        

    @classmethod
    def delete(cls, page, component, unit):
        with session_maker() as db_session:
            db_session.query(Pageconf).filter(Pageconf.page == page, Pageconf.component==component,  Pageconf.unit==unit).delete()
            return

    @classmethod
    def delete_point_system(cls, page: str, component: str, unit: Union[str, int], dtype: str, point_name: str='', sys_id: int=''):
        """
        删除某一元素

        Args:
            page (str): 指定页
            component (str): 指定组件
            unit (Union[str, int]): 指定机组
            dtype (str): 指定删除的类型, 目前只有point_list  point_history  system_list
            point_name (str, optional): 指定点类型时传入点名. Defaults to ''.
            sys_id (Union[str, int], optional): 指定系统类型时传入id. Defaults to ''.

        Returns:
            Boolean, str: True/Fasle 是否删除成功  msg 提示信息
        """
        with session_maker() as db_session:
            res = db_session.query(cls) \
                            .filter(cls.page == page, cls.component == component, cls.unit == unit) \
                            .first()
            if res is None:
                return False, "需要删除的数据不存在"
            db_session.expunge(res)
            
            if dtype in res.value.keys():
                data = res.value.get(dtype)
                key = dtype
                if dtype == 'point_list' or dtype == 'point_history':
                    del_id = 'point_name'
                    del_val = point_name
                else: # dtype == 'system_list'
                    del_id = 'id'
                    del_val = sys_id
                for item in data[:]:
                    if item.get(del_id) == del_val:
                        data.remove(item)
            else:
                return False, "请传入正确的dtype, 值为point_list/point_history/system_list"
            
            # if dtype == 'point':
            #     if 'point_list' in res.value.keys():
            #         data = res.value.get('point_list')
            #         key = 'point_list'
            #     else:
            #         data = res.value.get('point_history')
            #         key = 'point_history'
            #     for item in data[:]:
            #         if item.get('point_name') == point_name:
            #             data.remove(item)
            # elif dtype == 'system':
            #     data = res.value.get('system_list')
            #     key = 'system_list'
            #     for item in data[:]:
            #         if item.get('id') == sys_id:
            #             data.remove(item)
            # else:
            #     return False, "请传入正确的dtype, 值为point/system"
            
            db_session.query(cls) \
                      .filter(cls.page == page, cls.component == component, cls.unit == unit) \
                      .update({'value': {key: data}})
            return True, "成功删除对应元素"

    @classmethod
    def add_element(cls, page: str, component: str, unit: Union[str, int], data: list, adtype: str):
        """
        向相应的页面组件中添加元素

        Args:
            page (str): 同上
            component (str): 同上
            unit (Union[str, int]): 同上
            data (list): 需要添加的元素列表
            adtype (str): 指明需要添加元素的类型

        Returns:
            Boolean, str: True/Fasle 是否删除成功  msg 提示信息
        """
        with session_maker() as db_session:
            res = db_session.query(cls) \
                            .filter(cls.page == page, cls.component == component, cls.unit == unit) \
                            .first()
            if res is None:
                return False, "需要添加元素的页面或组件不存在"
            db_session.expunge(res)
            
            db_data = res.value
            db_data.get(adtype).extend(data)
            
            db_session.query(cls) \
                      .filter(cls.page == page, cls.component == component, cls.unit == unit) \
                      .update({'value': db_data})
            return True, "成功添加元素"