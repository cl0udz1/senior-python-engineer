def discount_percent(membership):
    """Return 0/5/10/0 for None/basic/premium/unrecognized strings."""
    return {'basic':5,'premium':10}.get(membership,0)

def every_other_helper(value):
    return value.strip().lower()
