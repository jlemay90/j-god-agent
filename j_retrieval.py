import re


def score(memory, query):
    words = set(re.findall(r'\w{3,}', query.lower())) - {'the','and','that','this','with','what','have','for','you','are','can'}
    terms = set(re.findall(r'\w{3,}', (memory['key']+' '+memory['value']).lower()))
    baseline = {'preference':3,'goal':2,'constraint':2,'commitment':1}.get(memory['kind'],0)
    return len(words & terms)*5+baseline
