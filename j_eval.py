"""Frozen synthetic retrieval benchmark. Never sent to the code-writing model."""
from j_ranker import scores

RECORDS=[
 dict(id='cabin',kind='project',key='cabin winterization',value='Insulate exposed pipes and prepare the tiny house for cold weather'),
 dict(id='phone',kind='project',key='phone upgrade',value='Compare compact folding phones'),
 dict(id='comedy',kind='goal',key='stand-up',value='Perform a comedy set at an open mic'),
 dict(id='money',kind='goal',key='budget',value='Reduce expenses and rebuild credit'),
 dict(id='family',kind='project',key='daughter activities',value='Plan weekend crafts and STEM activities together'),
 dict(id='career',kind='goal',key='career transition',value='Find industrial training and field service jobs'),
]
CASES=[('cabin pipes','cabin'),('folding phone','phone'),('open mic comedy','comedy'),('budget expenses','money'),('daughter crafts','family'),('industrial training jobs','career'),('winterize my plumbing','cabin'),('smaller handset','phone'),('perform jokes on stage','comedy'),('spending and debt','money'),('things to do with my kid','family'),('technical trainer employment','career')]


def evaluate(source):
    correct=0
    passed=[]
    for index,(query,expected) in enumerate(CASES):
        values=scores(RECORDS,query,source)
        ranked=sorted(RECORDS,key=lambda r:values[r['id']],reverse=True)
        if ranked[0]['id']==expected and values[expected]>0:
            correct+=1
            passed.append(index)
    return {'correct':correct,'total':len(CASES),'accuracy':correct/len(CASES),'passed_cases':passed}
