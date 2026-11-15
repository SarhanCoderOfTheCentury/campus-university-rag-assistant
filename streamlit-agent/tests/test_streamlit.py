from streamlit.testing.v1 import AppTest
from rag.config import ROOT

def test_missing_key_has_helpful_setup_message(monkeypatch,tmp_path):
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    monkeypatch.setattr('dotenv.load_dotenv',lambda *a,**k:False)
    app=AppTest.from_file(str(ROOT/'streamlit_app.py')).run(timeout=30)
    assert not app.exception
    assert any('GEMINI_API_KEY' in w.value for w in app.warning)

def test_configured_app_shows_single_chat_without_dashboard(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-placeholder-not-used-for-network')
    app=AppTest.from_file(str(ROOT/'streamlit_app.py')).run(timeout=30)
    assert not app.exception
    assert len(app.tabs)==0
    assert len(app.metric)==0
    assert len(app.chat_input)==1

def test_repeating_a_question_keeps_unique_download_widgets(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-placeholder-not-used-for-network')
    from rag.agent import RAGAgent
    monkeypatch.setattr(RAGAgent,'ask',lambda self,question,on_step=None: {
        'answer':'Controlled UI test reply.','sources':[],'status':'insufficient',
        'evidence':[],'trace':{},'retrieved':[]})
    app=AppTest.from_file(str(ROOT/'streamlit_app.py')).run(timeout=30)
    app.chat_input[0].set_value('Repeat this question').run(timeout=30)
    app.chat_input[0].set_value('Repeat this question').run(timeout=30)
    assert not app.exception
    assert len(app.chat_message)==4
