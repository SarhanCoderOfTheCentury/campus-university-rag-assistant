"""Conservative local routing; ambiguous follow-ups still use contextual planning."""
import re
from collections import OrderedDict
import time

def direct_intent(question):
    text=question.lower()
    # Preferences, corrections and pronoun-based follow-ups require session context.
    if re.search(r"\b(i|i'm|my|me|remember|forget|prefer|instead|that|those|them|it|same)\b",text):return None
    if re.search(r'\b(programmes?|programs?|degrees?|courses?)\b',text) and re.search(r'\b(all|list|offer|catalogue|catalog)\b',text):
        return 'focused' if re.search(r'\b(undergraduate|postgraduate|graduate|bachelor|master|bs|ms|bba|emba|computing|engineering|business)\b',text) else 'catalogue'
    if re.search(r'\b(policy|policies|attendance|refund|late fee|add.?drop|probation)\b',text) and re.search(r'\b(previous|archived|old|compare|comparison|before|v2|2023)\b',text):return 'historical'
    if re.search(r'\b(all|overview|summari[sz]e)\b',text) and re.search(r'\b(policies|academic rules)\b',text):return 'policy_overview'
    if re.search(r'\b(attendance|medical certificate|tuition|fees?|refunds?|scholarships?|admission|library|books?|hostel|semester|programmes?|programs?|deadline|office|transcript|registration)\b',text):return 'focused'
    return None

class BoundedTTL:
    """Process-local cache; no shared user transcript or generated-answer caching."""
    def __init__(self,limit=128,ttl=900):self.items=OrderedDict();self.limit=limit;self.ttl=ttl
    def get(self,key):
        item=self.items.pop(key,None)
        if item is None:return None
        if time.monotonic()-item[0]>self.ttl:return None
        self.items[key]=item;return item[1]
    def put(self,key,value):
        self.items[key]=(time.monotonic(),value);self.items.move_to_end(key)
        while len(self.items)>self.limit:self.items.popitem(last=False)
    def discard(self,key):self.items.pop(key,None)
