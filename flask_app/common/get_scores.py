import pickle
import os.path as osp
import numpy


def get_score(file_path: str, features: list = None) -> dict:
    """
    获取指定文件中的特征选择得分, 返回非排序的字典, 若找不到对应文件则返回None
    ----------
    Args:
        file_path: 评分pickle文件路径
        features: 强制返回的列, 若没有找到这些列则评分为None
    ----------
    """
    if not osp.isfile(file_path):
        return None

    with open(file_path, 'rb') as f:
        contents = pickle.load(f, encoding='utf-8')  # {point: score}

    scores = dict()
    for point, score in contents.items():
        if str(score) != 'nan':
            scores[point] = score
        elif features and point in features:
            scores[point] = None

    return scores


def get_selected_features(file_path: str, num: int=20) -> list:
    """
    从得分文件中获取topk的特征
    ----------
    Args:
        file_path: 得分文件路径
        num: 需要选择的特征个数
    ----------
    Returns:
        selected_features: 得分topk的特征名列表
    """
    if num <= 0:
        return list()
    
    scores = get_score(file_path)
    scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    selected_features = [feature for feature, score in scores[:num]]

    return selected_features


def get_res(save_path):
    save_path = save_path + '/output/best_model/res.pkl'
    if not osp.isfile(save_path):
        return None
    with open(save_path, 'rb') as f:
        contents = pickle.load(f, encoding='utf-8')
    result = {
        'target': contents['target'].tolist(),
        'pred': contents['pred'].tolist()
    }
    return result
