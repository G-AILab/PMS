def update(new, fields):
    result = {}
    for field in fields:
        try:
            data = new[field]
            if isinstance(data, list):
                if len(data):
                    result[field] = new[field]
            else:
                result[field] = new[field]
        except KeyError:
            pass
    return result
