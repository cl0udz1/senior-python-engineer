def discount_percent(membership):
    if membership is None:return 0
    return {'basic':5,'premium':10}[membership]
