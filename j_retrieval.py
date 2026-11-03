import re
def score(memory, query):
    def get_tokens(text):
        return re.findall(r'\w{3,}', text.lower())
    q_tokens = get_tokens(query)
    m_text = (str(memory.get('key', '')) + ' ' + str(memory.get('value', ''))).lower()
    m_tokens = get_tokens(m_text)
    if not q_tokens or not m_tokens: return 0
    score = 0
    if query.lower() in m_text: score += 20
    q_set = set(q_tokens)
    m_set = set(m_tokens)
    matches = q_set & m_set
    for m in matches:
        count = 0
        for t in m_tokens:
            if t == m: count += 1
        score += 5 + (count * 2)
    baseline = {'preference': 3, 'goal': 2, 'constraint': 2, 'commitment': 1}.get(memory.get('kind'), 0)
    return score + baseline
