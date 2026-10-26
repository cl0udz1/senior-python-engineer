class Lookup:
    def __init__(self,values):self.values=dict(values)
    def get(self,key,default=None):return self.values.get(key,default)
class FastLookup(Lookup):
    def get(self,key,default=None):
        if not isinstance(key,str) or not key:raise ValueError('nonempty string required')
        value=self.values.get(key)
        if value is None:raise KeyError(key)
        return value
