import json
from datetime import datetime
from json import JSONDecodeError

from flask_app import db, session_maker
from flask_app.models.model_timer import Model_timer
from flask_app.models.point_desc import PointDesc
from flask_app.models.algorithm import Algorithm
from flask_app.models.user import User
from flask_app.models.system_config import SystemConfig
from flask_app.models.unit_system import UnitSystem

class Model(db.Model):
    __tablename__ = 'model'
    mid = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(20))
    create_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.SmallInteger, nullable=False, default=0)
    general = db.Column(db.Text)
    selection = db.Column(db.Text)
    train = db.Column(db.Text)
    optimization = db.Column(db.Text)
    yname = db.Column(db.String(100), nullable=False)
    save_path = db.Column(db.String(100))
    selected_features = db.Column(db.Text)
    evaluate_results = db.Column(db.Text)
    realtime_evaluate_results = db.Column(db.Text)
    realtime_eval_metric = db.Column(db.String(20))
    warning_gate = db.Column(db.Float, default=2.0)
    opt_use = db.Column(db.SmallInteger, default=0)
    auto_run = db.Column(db.SmallInteger, nullable=False)
    # username = db.Column(db.String(90))
    create_user = db.Column(db.Integer, db.ForeignKey('users.uid'))
    dataset = db.Column(db.Integer, db.ForeignKey('dataset.did', ondelete='SET NULL'))
    select_method = db.Column(db.Integer, db.ForeignKey('algorithm.aid', ondelete='SET NULL'))
    train_method = db.Column(db.Integer, db.ForeignKey('algorithm.aid', ondelete='SET NULL'))
    optimize_method = db.Column(db.Integer, db.ForeignKey('algorithm.aid', ondelete='SET NULL'))
    sub_system = db.Column(db.Integer, db.ForeignKey('sub_system.sid', ondelete='SET NULL'))  # 该字段目前已被psystem取代
    psystem = db.Column(db.Integer, db.ForeignKey('system_config.cid', ondelete='SET NULL'))
    unit = db.Column(db.Integer, db.ForeignKey('unit_system.usid', ondelete='SET NULL'))
    DELETED = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return '<Model %r>' % self.name + str(self.mid) + "v" + str(self.version)

    def to_json(self):
        create_time = datetime.timestamp(self.create_time)
        try:
            general = str(self.general).replace('\'', '"')
            general = json.loads(general)
        except JSONDecodeError:
            general = 'general字段格式错误！'
        except TypeError:
            general = ''
        try:
            selection = str(self.selection).replace('\'', '"')
            selection = json.loads(selection)
        except JSONDecodeError:
            selection = 'selection字段格式错误！'
        except TypeError:
            selection = ''
        try:
            train = str(self.train).replace('\'', '"')
            train = json.loads(train)
        except JSONDecodeError:
            train = 'train字段格式错误！'
        except TypeError:
            train = ''
        try:
            optimization = str(self.optimization).replace('\'', '"')
            optimization = json.loads(optimization)
        except JSONDecodeError:
            optimization = 'optimization字段格式错误！'
        except TypeError:
            optimization = ''
        try:
            if self.selected_features is None:
                selected_features = ''
            else:
                selected_features = str(self.selected_features).replace('\'', '"')
                selected_features = json.loads(selected_features)
        except JSONDecodeError:
            selected_features = 'selected_features字段格式错误！'
        except TypeError:
            selected_features = ''
        try:
            if self.evaluate_results is not None:
                evaluate_results = str(self.evaluate_results).replace('\'', '"')
                evaluate_results = json.loads(evaluate_results)
            else:
                evaluate_results = ''
        except:
            evaluate_results = ''
        try:
            if self.realtime_evaluate_results is not None:
                realtime_evaluate_results = json.loads(self.realtime_evaluate_results)
            else:
                realtime_evaluate_results = ''
        except:
            realtime_evaluate_results = ''

        point_info = None
        if self.yname:
            point = PointDesc.get_by_name(self.yname, self.unit)
            if point:
                point_info = point.to_json(full=False)

        time_info = None
        model_timer = Model_timer.get_by_id_and_version(self.mid, self.version)
        if model_timer:
            time_info = model_timer.to_json()

        username = None
        if self.create_user:
            user = User.get_by_id(self.create_user)
            username = user.username

        return {
            'mid': self.mid,
            "version": self.version,
            "name": self.name,
            "category": self.category,
            "create_time": create_time,
            "status": self.status,
            "general": general,
            "selection": selection,
            "train": train,
            "optimization": optimization,
            "yname": self.yname,
            "save_path": self.save_path,
            'selected_features': selected_features,
            'evaluate_results': evaluate_results,
            'realtime_evaluate_results': realtime_evaluate_results,
            'realtime_eval_metric': self.realtime_eval_metric,
            'opt_use': False if self.opt_use == 0 else True,
            'warning_rate': self.warning_gate,
            "auto_run": self.auto_run,
            "dataset": self.dataset,
            "select_method": self.select_method,
            "train_method": self.train_method,
            "optimize_method": self.optimize_method,
            # "sub_system": self.sub_system,
            "sub_system": self.psystem,
            "point": point_info,
            "timer": time_info,
            "username": username,
            'unit': self.unit if self.unit else None
        }

    @classmethod
    def search_all(cls, unit, version=None, name=None, category=None, yname=None, dataset=None, sub_system=None,
                   status=None, train_method_name=None, is_warning=None, latest=True, all_unit=False):
        query_list = list()

        if version:
            query_list.append(cls.version == version)
        if name:
            query_list.append(cls.name.like('%'+name+'%'))
        if category:
            query_list.append(cls.category == category)
        if yname:
            query_list.append(cls.yname.like('%'+yname+'%'))
        if sub_system:
            query_list.append(cls.psystem == sub_system)
            # query_list.append(cls.sub_system == sub_system)
        if dataset:
            query_list.append(cls.dataset == dataset)
        if status:
            query_list.append(cls.status == status)
        if train_method_name:
            query_list.append(db.and_(Algorithm.chinese_name.like('%'+train_method_name+'%'), Algorithm.aid == cls.train_method))
        if is_warning is not None and is_warning == True:
            flag = '%"warning": true%'
            query_list.append(cls.realtime_evaluate_results.like(flag))
        if not all_unit:
            query_list.append(cls.unit == unit)

        if all_unit:
            unit = None
        latest_id_versions, _ = cls.get_latest_version(unit, None, None)
        with session_maker() as db_session:
            res_models = db_session.query(cls).filter(*query_list, cls.DELETED == False).all()

            final_models = list()
            for model in res_models:
                db_session.expunge(model)
                if latest and (model.mid, model.version) not in latest_id_versions:
                    continue
                final_models.append(model)
            return final_models, len(final_models)

    @classmethod
    def search_by_pages(cls, version, name, category, yname, dataset, sub_system, status, train_method, is_warning, unit, page, size):
        selected_models, total = cls.search_all(version, name, category, yname, dataset, sub_system, status, train_method, is_warning, unit, page, size)
        return selected_models, total

    @classmethod
    def get_last_mid(cls):
        with session_maker() as db_session:
            max_mid = db_session.query(db.func.max(cls.mid)).first()
            if not max_mid:
                return 0
            return max_mid[0] if max_mid[0] else 0
            # if db.session.query(Model).first() is not None:
            #     mid = max(db_session.query(Model.mid))
            #     return mid[0]
            # else:
            #     return 0

    @classmethod
    def get_last_version(cls, mid):
        with session_maker() as db_session:
            target_models = db_session.query(cls).filter(cls.mid == mid).all()

            max_version = 0
            for model in target_models:
                max_version = max(model.version, max_version)
            return max_version
            # if db_session.query(Model).filter(Model.mid == mid).first() is not None:
            #     version = max(db_session.query(Model.version).filter(Model.mid == mid))
            #     return version[0]
            # else:
            #     return 0

    @classmethod
    def create(cls, mid, name, version, category, status, path, yname, auto_run, dataset, select_method, train_method, train,
               optimize_method, general, sub_system, user_id, unit, selected_features=None):
        with session_maker() as db_session:
            if sub_system:
                target_sys = db_session.query(SystemConfig).filter(SystemConfig.cid == sub_system, SystemConfig.DELETED == False,
                                                                   SystemConfig.parent >= 0).first()
                # target_sys = db_session.query(SystemConfig).filter(SystemConfig.cid == sub_system, SystemConfig.DELETED == False).first()
                if not target_sys:
                    return False, '找不到指定系统或该系统为根系统（cid:'+str(sub_system)+')'

            model = Model(
                mid=mid, name=name, version=version, category=category, save_path=path, status=status,
                create_time=datetime.now(), yname=yname, auto_run=auto_run, dataset=dataset,
                select_method=select_method, train_method=train_method, train=train, optimize_method=optimize_method,
                general=general, psystem=sub_system, warning_gate=2.0, realtime_eval_metric='mse', create_user=user_id, unit=unit,
                DELETED=False, selected_features=selected_features
            )
            db_session.add(model)
            return True, ''

    @classmethod
    def create_models(cls, new_models: list) -> list:
        start_mid = cls.get_last_mid() + 1
        mid = start_mid
        with session_maker() as db_session:
            for model_data in new_models:
                model_data.update({
                    'mid': mid,
                    'version': 1,
                    'save_path': '/workspace/hd_ws/models/M{}/v{}'.format(mid, 1),
                    'create_time': datetime.now(),
                    'DELETED': False,
                    'warning_gate': 5.0,
                    'realtime_eval_metric': 'mse'
                })
                new_model = Model(**model_data)
                db_session.add(new_model)
                Model_timer.create(mid, 1)
                mid += 1
        end_mid = mid
        return list(range(start_mid, end_mid))

    @classmethod
    def get_all_in_unit(cls, unit):
        with session_maker() as db_session:
            models = db_session.query(cls).filter(cls.unit == unit, cls.DELETED == False).all()
            total = 0
            for model in models:
                total += 1
                db_session.expunge(model)
            return models, total

    @classmethod
    def get_latest_version(cls, unit, page=None, size=None):
        with session_maker() as db_session:
            condition = [cls.DELETED == False]
            if unit is not None:
                condition.append(cls.unit == unit)
            if page is not None and size is not None:
                id_versions = db_session.query(cls.mid, db.func.max(cls.version)).filter(*condition)\
                                                                                 .group_by(cls.mid).paginate(page=page, per_page=size, error_out=False)
                # print(id_versions.items)
                return id_versions.items, id_versions.total

            id_versions = db_session.query(cls.mid, db.func.max(cls.version))\
                                    .filter(*condition)\
                                    .group_by(cls.mid).all()
            return id_versions, len(id_versions)

    @classmethod
    def get_latest(cls, unit, page=None, size=None):
        with session_maker() as db_session:
            # models = db_session.query(cls)
            # latest_version = {}
            # for model in models:
            #     try:
            #         if model.version > latest_version[model.mid]:
            #             latest_version[model.mid] = model.version
            #     except KeyError:
            #         latest_version[model.mid] = model.version
            # latest_models = []
            # for mid, version in latest_version.items():
            #     latest_models.append(cls.get_by_id_and_version(mid, version))
            # return latest_models, len(latest_models)
            latest_id_versions, total = cls.get_latest_version(unit, page, size)

            latest_models = list()
            for mid, version in latest_id_versions:
                latest_model = db_session.query(cls).filter(db.and_(cls.mid == mid, cls.version == version, cls.DELETED == False)).first()
                db_session.expunge(latest_model)
                latest_models.append(latest_model)

            return latest_models, total

    @classmethod
    def get_by_page(cls, unit, page, size):
        return cls.get_latest(unit, page, size)
        # latest_models, total = cls.get_latest()
        # selected_models = latest_models[left: right]
        # return selected_models, total

    @classmethod
    def get_by_id(cls, mid, unit):
        with session_maker() as db_session:
            models = db_session.query(cls).filter(Model.mid == mid, cls.unit == unit, cls.DELETED == False).all()
            for model in models:
                db_session.expunge(model)
            return models

    @classmethod
    def get_by_id_and_version(cls, mid, version, unit):
        with session_maker() as db_session:
            model = db_session.query(cls).filter(Model.mid == mid, Model.version == version, cls.DELETED == False, cls.unit == unit).first()
            if model is None:
                return None
            db_session.expunge(model)
            return model

    @classmethod
    def get_by_yname_and_category(cls, yname, category, unit):
        '''
        根据yname和category查找运行中的模型
        '''
        with session_maker() as db_session:
            model = db_session.query(cls).filter(Model.yname == yname,  Model.category == category, Model.status == 15,
                                                 cls.unit == unit, cls.DELETED == False).first()
            if model is None:
                return None
            db_session.expunge(model)
            return model

    @classmethod
    def get_by_yname(cls, yname, unit):
        with session_maker() as db_session:
            model = db_session.query(cls).filter(Model.yname == yname, Model.status == 15, cls.DELETED == False, cls.unit == unit).first()
            if model is None:
                return None
            db_session.expunge(model)
            return model

    @classmethod
    def delete(cls, mid, version):
        with session_maker() as db_session:
            db_session.query(Model).filter(Model.mid == mid, Model.version == version).update({'DELETED': True})
            return

    @classmethod
    def update_model(cls, mid, version, data, print_data=True):
        with session_maker() as db_session:
            if print_data:
                print(data)
            if len(data) == 0:
                return False
            db_session.query(cls).filter(Model.mid == mid, Model.version == version).update(data)
            return True

    @classmethod
    def update_models(cls, update_models):
        with session_maker() as db_session:
            for update_model_data in update_models:
                if 'data' in update_model_data and 'mid' in update_model_data and 'version' in update_model_data:
                    mid = update_model_data['mid']
                    version = update_model_data['version']
                    data = update_model_data['data']
                    db_session.query(cls).filter(cls.mid == mid, cls.version == version).update(data)
            return True

    @classmethod
    def search_name(cls, name, unit):
        with session_maker() as db_session:
            filtered_models = db_session.query(Model).filter(Model.name.like('%' + name + '%'), cls.unit == unit, cls.DELETED == False).all()
            for model in filtered_models:
                db_session.expunge(model)
            return filtered_models

    @classmethod
    def get_all_running_models(cls):
        with session_maker() as db_session:
            running_models = db_session.query(cls).filter(cls.DELETED == False, cls.status == 15).all()
            for model in running_models:
                db_session.expunge(model)
        return running_models

    @classmethod
    def statistic_status_all_units(cls) -> dict:
        '''
        统计各个机组运行中、未运行、准备中的模型数量
        '''
        all_units, _ = UnitSystem.get_all()
        res = {u.usid: {'preparing': 0, 'running': 0, 'not_running': 0} for u in all_units}
        with session_maker() as db_session:
            all_models = db_session.query(cls).filter(cls.DELETED == False).all()
            for model in all_models:
                if not model.unit or model.unit not in res:
                    continue
                if model.status == 15:
                    res[model.unit]['running'] += 1
                elif model.status == 14 or model.status == 16 or model.status == 17:
                    res[model.unit]['not_running'] += 1
                elif model.status >=0 and model.status <= 13:
                    res[model.unit]['preparing'] += 1
        return res


    @classmethod
    def statistic_category(cls, classification, unit):
        '''
        返回机组的模型统计信息
        Args:
            classification:
                = 'category': 统计指定机组各个类别模型的状态
                = 'status': 统计指定机组处于各个状态下的模型的类别
            unit: 机组id
        '''
        if classification == 'category':
            statistics = {
                'prediction': {
                    'training': 0,
                    'optimizing': 0,
                    'stop': 0,
                    'running': 0,
                },
                'detection': {
                    'training': 0,
                    'optimizing': 0,
                    'stop': 0,
                    'running': 0,
                },
                'regression': {
                    'training': 0,
                    'optimizing': 0,
                    'stop': 0,
                    'running': 0,
                },
            }
            categories = ['prediction', 'detection']
            with session_maker() as db_session:
                models = db_session.query(cls).filter(cls.unit == unit, cls.DELETED == False).all()
                for model in models:
                    for category in categories:
                        if model.category == category:
                            if 6 <= model.status <= 9:
                                statistics[category]['training'] += 1
                            elif 10 <= model.status <= 13:
                                statistics[category]['optimizing'] += 1
                            elif model.status == 14:
                                statistics[category]['stop'] += 1
                            elif model.status == 15:
                                statistics[category]['running'] += 1
                return statistics

        elif classification == 'status':
            statistics = {
                'sectioning': {
                    'prediction': 0,
                    'regression': 0,
                    'detection': 0,
                },
                'training': {
                    'prediction': 0,
                    'regression': 0,
                    'detection': 0,
                },
                'optimizing': {
                    'prediction': 0,
                    'regression': 0,
                    'detection': 0,
                },
                'running': {
                    'prediction': 0,
                    'regression': 0,
                    'detection': 0,
                },
            }
            categories = ['prediction', 'regression', 'detection']
            with session_maker() as db_session:
                models = db_session.query(cls).filter(cls.unit == unit, cls.DELETED == False).all()
                for model in models:
                    if 3 <= model.status <= 5:
                        for category in categories:
                            if model.category == category:
                                statistics['sectioning'][category] += 1
                    elif 6 <= model.status <= 9:
                        for category in categories:
                            if model.category == category:
                                statistics['training'][category] += 1
                    elif 10 <= model.status <= 13:
                        for category in categories:
                            if model.category == category:
                                statistics['optimizing'][category] += 1
                    elif model.status == 15:
                        for category in categories:
                            if model.category == category:
                                statistics['running'][category] += 1
                return statistics
