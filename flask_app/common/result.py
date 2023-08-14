from flask import jsonify


def true_return(msg="", data=None, code=200):
    return jsonify({
        'msg': msg,
        'data': data,
        'status': True
    })


def false_return(msg="", data=None, code=200):
    return jsonify({
        'msg': msg,
        'data': data,
        'status': False
    })
