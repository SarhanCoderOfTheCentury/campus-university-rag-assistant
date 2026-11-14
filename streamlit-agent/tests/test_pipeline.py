import json
from collections import Counter
import numpy as np
import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from rag.agent import Answer, Citation, Claim, RAGAgent, safe_error, validate_answer
from rag.config import ROOT, REFUSAL, Settings
from rag.embeddings import DIMENSIONS, normalize
from rag.retrieval import allowed, pack_context, policy_intent, rrf, search
from rag.store import fingerprint, load_documents, load_dsu, make_store, split_documents

class OfflineEmbedding(Embeddings):
    def embed_query(self, text):
        vector = np.zeros(DIMENSIONS, dtype=np.float32)
        vector[0] = 1
        return vector.tolist()
    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

@pytest.fixture
def evidence():
    return [{'id':'known','filename':'policy.md','status':'current','version':'2.0',
        'source_url':'','text':'The minimum attendance requirement is 80%.'}]

def test_citation_validation_rejects_invented_id_and_quote(evidence):
    for chunk_id, quote in [('unknown','The minimum attendance'),('known','Attendance is 5%.')]:
        answer=Answer(insufficient=False,claims=[Claim(text='80%.',citations=[Citation(chunk_id=chunk_id,quote=quote)])])
        assert validate_answer(answer,evidence)['status']=='invalid_citations'

def test_valid_quotes_are_preserved(evidence):
    answer=Answer(insufficient=False,claims=[Claim(text='Attendance is at least 80%.',
        citations=[Citation(chunk_id='known',quote='minimum attendance requirement is 80%')])])
    result=validate_answer(answer,evidence)
    assert result['status']=='answered' and result['sources'][0]['filename']=='policy.md'

def test_refusal_is_exact_and_has_no_false_citations(evidence):
    result=validate_answer(Answer(insufficient=True,claims=[]),evidence)
    assert result['answer']==REFUSAL and not result['sources']

@pytest.mark.parametrize('q,intent',[
    ('What is the fee now?','current'),('What was the previous fee?','archived'),
    ('Compare old and current fees','compare'),('What did v1 require?','archived')])
def test_intent(q,intent):
    assert policy_intent(q)==intent

def test_archived_filter_before_top_k():
    docs=[Document(page_content='fee old',metadata={'id':'old','source':'old.md','status':'archived'}),
        Document(page_content='fee current',metadata={'id':'new','source':'current.md','status':'current'})]
    vectors=np.zeros((2,DIMENSIONS),dtype=np.float32)
    vectors[0,0]=1
    vectors[1,0]=0.8
    vectors[1,1]=0.6
    store=make_store(docs,vectors,OfflineEmbedding())
    hits,_=search(store,docs,OfflineEmbedding(),'fee',k=1,method='semantic',intent='current')
    assert hits[0]['document'].metadata['id']=='new'
    hits,_=search(store,docs,OfflineEmbedding(),'fee',k=2,method='semantic',intent='compare')
    assert {h['document'].metadata['id'] for h in hits}=={'old','new'}

def test_rrf_is_rank_based_and_deterministic():
    ranking,scores=rrf([[1,2,3],[3,2,4]])
    assert ranking[0]==3
    assert scores[2]==pytest.approx(2/62)

def test_normalization_and_corrupt_vectors():
    assert np.linalg.norm(normalize([3,4]))==pytest.approx(1)
    with pytest.raises(ValueError):
        normalize([0,0])
    with pytest.raises(ValueError):
        normalize([float('nan'),1])
    with pytest.raises(ValueError):
        make_store([],np.zeros((1,3)),OfflineEmbedding())

def test_supplied_vectors_have_exact_row_alignment():
    store,docs,_=load_dsu(OfflineEmbedding())
    assert len(docs)==584 and store.index.d==DIMENSIONS
    vectors=np.load(ROOT/'data/dsu/vectors.npy')
    scores,ids=store.index.search(vectors[[0,100,583]],1)
    assert ids[:,0].tolist()==[0,100,583]
    assert np.allclose(scores,1,atol=1e-5)

def test_fictional_kb_and_preserved_policy_metadata():
    docs=load_documents(ROOT/'knowledge/demo')
    assert len(docs)==5
    assert 1500<=sum(len(d.page_content.split()) for d in docs)<=2500
    chunks=split_documents(docs)
    archived=[c for c in chunks if c.metadata['status']=='archived']
    assert archived and all(c.metadata['version']=='1.0' for c in archived)
    assert all(not allowed(c,'current') for c in archived)
    assert all('filename' in c.metadata and 'start_index' in c.metadata for c in chunks)

def test_policy_edit_changes_index_fingerprint(tmp_path):
    path=tmp_path/'policy.md'
    path.write_text('Attendance: 80%.')
    before=fingerprint(tmp_path,1000,150)
    path.write_text('Attendance: 85%.')
    assert fingerprint(tmp_path,1000,150)!=before
    assert fingerprint(tmp_path,600,100)!=before

def test_context_budget_never_sends_unbounded_text():
    hit={'document':Document(page_content='x'*1000,metadata={'id':'a','source':'a.md'})}
    evidence,bound=pack_context([hit],600)
    assert not evidence and bound==0

def test_error_messages_do_not_leak_secrets():
    assert 'secret-key' not in safe_error(ValueError('secret-key in URL'))

def test_case_category_counts_are_exact():
    cases=json.loads((ROOT/'evaluation/test_cases.json').read_text())
    assert Counter(c['category'] for c in cases)=={
        'direct':5,'paraphrase':4,'two_document':3,'policy_comparison':3,'missing':3,'prompt_injection':2}

class StubLLM:
    def with_structured_output(self, schema):
        return self
    def invoke(self, messages):
        evidence=json.loads(messages[-1].content)['evidence']
        item=evidence[0]
        return Answer(insufficient=False,claims=[Claim(text='The local fixture says attendance is 80%.',
            citations=[Citation(chunk_id=item['id'],quote='Attendance requirement is 80%.')])])

def test_langgraph_end_to_end_with_controlled_local_fixture():
    emb=OfflineEmbedding()
    docs=[Document(page_content='Attendance requirement is 80%.',metadata={
        'id':'fixture','source':'current.md','status':'current','version':'2.0'})]
    store=make_store(docs,np.asarray(emb.embed_documents(['a'])),emb)
    agent=RAGAgent(Settings(search='semantic'),emb,store,docs,llm=StubLLM())
    steps=[]
    result=agent.ask('What is attendance?',lambda node,data:steps.append(node))
    assert steps==['route','retrieve','answer']
    assert result['status']=='answered' and result['sources'][0]['chunk_id']=='fixture'
    assert agent.ask('  ')['status']=='empty'
