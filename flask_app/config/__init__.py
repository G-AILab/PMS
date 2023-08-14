import os
from flask_app.config.dandong252 import DanDong252
from flask_app.config.default import Config as DefaultConfig
from flask_app.config.development import *
from flask_app.config.production import *

_config = None

CONFIG_NAME_MAPPER = {
    'local': LocalConfig,
    'production': ProductionConfig,
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'chenzhu248': ChenZhu248Config,
    'chenzhu247': ChenZhu247Config,
    'dandong252': DanDong252,
    '247_celery_node':CeleryNode247
}

class MixedConfig(DefaultConfig):
    inited = False


def get_config():
    if MixedConfig.inited:
        return MixedConfig
    else:
        #env_config = os.getenv("FLASK_CONFIG")
        env_config = "local"
        _override_config = CONFIG_NAME_MAPPER.get(env_config, DevelopmentConfig) # 默认为 development config
        MixedConfig.CONFIG_NAME = env_config

    for key in dir(_override_config):
        if key.isupper():
            if isinstance(getattr(_override_config, key), dict) \
                    and key in dir(MixedConfig) \
                    and isinstance(getattr(MixedConfig, key), dict):
                dict_to_modify = getattr(MixedConfig, key)
                for key, value in getattr(_override_config, key).items():
                    dict_to_modify[key] = value
                setattr(MixedConfig, key, dict_to_modify)
            else:
                setattr(MixedConfig, key, getattr(_override_config, key))
    MixedConfig.inited = True
    return MixedConfig
