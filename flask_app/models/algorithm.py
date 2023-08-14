from flask_app import db
from flask_app import session_maker
import json


class Algorithm(db.Model):
    __tablename__ = 'algorithm'
    aid = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    category = db.Column(db.String(20), nullable=False)
    atype = db.Column(db.String(20), nullable=False)
    parameters = db.Column(db.Text, nullable=False)
    defaults = db.Column(db.Text, nullable=False)
    chinese_name = db.Column(db.String(20))
    description = db.Column(db.Text)
    file = db.Column(db.Text)
    param_desc = db.Column(db.Text)

    def __repr__(self):
        return '<Algorithm  %r>' % self.aid

    def to_json(self):
        return {
            'aid': self.aid,
            'name': self.name,
            'category': self.category,
            'type': self.atype,
            'parameters': json.loads(self.parameters),
            'defaults': json.loads(self.defaults),
            'chinese_name': self.chinese_name,
            'description': self.description,
            # 'param_desc': self.param_desc
        }
    
    @classmethod
    def get_general_params(cls, category, alg_name=None) -> str:
        '''
        返回json.dumps()的结果
        '''
        if category == "detection":
            res={"train_params":{},'window':10,'device':'cpu'}
            # if alg_name == 'USAD':
            #     res = {"train_params":{},"val_ratio":0.3,"window":10,"cpu_num":20,"max_iter":400,"epochs":1,"batch":1000,"k":3,"alpha":0.5,"beta":0.5,"device":"cpu","thred_ratio":[99.9,99.99]}
            # elif alg_name == 'GDN':
            #     res = {"train_params":{},"decay":0,"seed":2021,"window":10,"stride":1,"epoch":1,"batch":100,"val_ratio":0.3,"k":3,"thred_ratio":[99.9,99.99],"device":"cpu"}
            # elif alg_name == 'MTADGAT':
            #     res = {"train_params":{},"window":60,"k":5}
            # else:
            #     raise KeyError('{}-{}'.format(category, alg_name))
        elif category == "prediction":
            res = {"window": 6, "horizon": 6, "train_params": {}, "cpu_num": 20, "max_iter": 400, "device": "cpu"}
        elif category == "regression":
            res = {"window": 6, "horizon": 6, "train_params": {}, "cpu_num": 20, "max_iter": 400, "device": "cpu"}
        else:
            raise KeyError(category)
        return json.dumps(res)

    @classmethod
    def get_all(cls):
        with session_maker() as db_session:
            algorithms = db_session.query(cls)
            total = 0
            for alg in algorithms:
                total += 1
                db_session.expunge(alg)
            return algorithms, total
    
    @classmethod
    def get_all_aid_name_map(cls):
        all_algs, _ = cls.get_all()
        aid_name_map = dict()
        for alg in all_algs:
            aid_name_map[alg.aid] = alg.name
        return aid_name_map

    @classmethod
    def get_by_page(cls, left, right):
        with session_maker() as db_session:
            algorithms = db_session.query(cls)
            total = 0
            selected_algorithms = algorithms[left: right]
            for algorithm in algorithms:
                db_session.expunge(algorithm)
                total += 1
            return selected_algorithms, total

    @classmethod
    def get_by_id(cls, aid):
        with session_maker() as db_session:
            algorithm = db_session.query(cls).filter(cls.aid == aid).first()
            if not algorithm:
                return None
            db_session.expunge(algorithm)
            return algorithm

    @classmethod
    def get_by_fuzz_chinese_name(cls, chinese_name, atype='selection'):
        with session_maker() as db_session:
            algorithm = db_session.query(cls).filter(cls.atype ==atype,cls.chinese_name.like('%' + chinese_name + '%')).first()
            if not algorithm:
                return None
            db_session.expunge(algorithm)
            return algorithm    

    @classmethod
    def get_by_chinese_name(cls, chinese_name):
        with session_maker() as db_session:
            algorithm = db_session.query(cls).filter(cls.chinese_name == chinese_name).first()
            if not algorithm:
                return None
            db_session.expunge(algorithm)
            return algorithm

    @classmethod
    def create(cls, name, category, atype, parameters, defaults):
        with session_maker() as db_session:
            algorithm = Algorithm(name=name, category=category, atype=atype, parameters=parameters, defaults=defaults)
            db_session.add(algorithm)
            db_session.commit()
            db_session.refresh(algorithm)
            db_session.expunge(algorithm)
            return algorithm

    @classmethod
    def update_algorithm(cls, aid, name, category, atype, parameters, defaults, chinese_name, description):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.aid == aid).update({
                'name': name,
                'category': category,
                'atype': atype,
                'parameters': parameters,
                'defaults': defaults,
                'chinese_name': chinese_name,
                'description': description
            })
            algorithm = db_session.query(cls).filter(cls.aid == aid).first()
            db_session.expunge(algorithm)
            return algorithm

    @classmethod
    def delete_algorithm(cls, aid):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.aid == aid).delete()
            return aid

    @classmethod
    def statistic(cls):
        statistics = {
            'regression': {
                'selection': 0,
                'train': 0,
                'optimization': 0,
            },
            'prediction': {
                'selection': 0,
                'train': 0,
                'optimization': 0,
            },
            'detection': {
                'selection': 0,
                'train': 0,
                'optimization': 0,
            }
        }
        categories = ['regression', 'prediction', 'detection']
        atypes = ['selection', 'train', 'optimization']
        with session_maker() as db_session:
            algorithms = db_session.query(cls)
            for algorithm in algorithms:
                for category in categories:
                    if algorithm.category == category:
                        for atype in atypes:
                            if algorithm.atype == atype:
                                statistics[category][atype] += 1
            return statistics

    @classmethod
    def update_file(cls, aid, file_path):
        with session_maker() as db_session:
            db_session.query(cls).filter(cls.aid == aid).update({'file': file_path})

    @classmethod
    def filter_by_type(cls, category, atype):
        with session_maker() as db_session:
            algorithms = db_session.query(cls).filter(cls.category == category, cls.atype == atype)
            return algorithms

    @classmethod
    def get_paras(cls, aid):
        with session_maker() as db_session:
            algorithm = db_session.query(Algorithm).filter(Algorithm.aid == aid).first()
            defaults = str(algorithm.defaults)
            defaults = defaults.replace('true', 'True').replace('false', 'False')
            try:
                parameters = eval(algorithm.parameters)
                defaults = eval(defaults)
            except NameError:
                return False, {}
            result = {}
            for key, value in parameters.items():
                result[key] = {'chinese': value}
            for key, value in defaults.items():
                para_type = str(type(value)).split('\'')[1].split('\'')[0]
                result[key]['defaults'] = value
                result[key]['type'] = para_type
            return True, result

    @classmethod
    def search_name(cls, name):
        with session_maker() as db_session:
            filtered_algorithms = db_session.query(Algorithm).filter(Algorithm.name.like('%'+name+'%'))
            return filtered_algorithms
