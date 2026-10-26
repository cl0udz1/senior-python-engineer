class Lookup:
    def __init__(self,values):self.values=dict(values)
    def get(self,key,default=None):return self.values.get(key,default)
class FastLookup(Lookup):
    pass
