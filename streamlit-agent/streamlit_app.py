import os
import hashlib
import re
import time
import streamlit as st
from dotenv import load_dotenv
from rag.config import ROOT, Settings
from rag.embeddings import GeminiEmbeddings
from rag.store import load_corpus, fingerprint
from rag.agent import RAGAgent, safe_error

load_dotenv(ROOT / '.env')
st.set_page_config(page_title='Campus Assistant', page_icon='🎓', layout='centered', initial_sidebar_state='collapsed')
st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"], [data-testid="stApp"], input, button, textarea {font-family:'DM Sans',Arial,sans-serif}
.block-container {max-width:760px;padding-top:3.5rem;padding-bottom:5rem}
h1 {font-size:2rem!important;letter-spacing:-.035em}
[data-testid="stChatMessage"] {border-radius:18px;padding:1rem 1.1rem;margin-bottom:.8rem}
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li {line-height:1.65}
[data-testid="stChatMessage"] li {margin-bottom:.55rem}
[data-testid="stChatMessage"] ul {padding-left:1.4rem}
[data-testid="stSidebar"] {min-width:245px}
</style>''', unsafe_allow_html=True)


def secret(name):
    value = os.getenv(name, '')
    if value:
        return value
    try:
        return str(st.secrets.get(name, ''))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return ''


@st.cache_resource(show_spinner=False)
def resources(settings, revision, key_revision, _api_key):
    # Never place the secret itself in Streamlit's cache key. A one-way revision
    # invalidates cached provider clients after credential rotation without
    # exposing the credential in cache metadata.
    embeddings = GeminiEmbeddings(_api_key)
    store, chunks, manifest = load_corpus(settings, embeddings)
    return RAGAgent(settings, embeddings, store, chunks, api_key=_api_key), manifest


with st.sidebar:
    st.markdown('### Campus Assistant')
    corpus_label = st.selectbox('Documents', ['DHA Suffa University', 'Noor Skills · example'])
    corpus = 'dsu' if corpus_label == 'DHA Suffa University' else 'demo'
    if st.button('Clear conversation', use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.title('Ask about DSU' if corpus=='dsu' else 'Ask about Noor Skills')
st.caption('Admissions, programs, policies, and campus information. Answers include their sources.')

settings = Settings(corpus=corpus, k=5, search='hybrid', rewrite=False, rerank=False,
    model=secret('GEMINI_MODEL') or 'gemini-3.5-flash-lite')
key = secret('GEMINI_API_KEY')
if not key:
    st.warning('Add GEMINI_API_KEY to .env locally or to Streamlit app secrets, then restart. The key is never committed.')
    st.code('GEMINI_API_KEY = "your-key-here"', language='toml')
    st.stop()
try:
    revision = fingerprint(ROOT / 'knowledge/demo', settings.chunk_size, settings.chunk_overlap) if corpus=='demo' else 'dsu-supplied-v1'
    key_revision = hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]
    with st.spinner('Loading the local knowledge index…'):
        agent, _manifest = resources(settings, revision, key_revision, key)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

def stream_answer(answer):
    # Stream only checked, cited text. Never show provisional model output.
    for part in re.findall(r'\S+\s*|\s+', answer):
        yield part
        time.sleep(.012)


with st.container():
    conversation_key = corpus
    if st.session_state.get('conversation_key') != conversation_key:
        st.session_state.messages = []
        st.session_state.conversation_key = conversation_key

    def display_result(result, *, streaming=False):
        if result['status'] == 'api_error':
            st.error(result['answer'])
        elif streaming and result['status'] == 'answered':
            st.write_stream(stream_answer(result['answer']))
        else:
            st.markdown(result['answer'])
        if result.get('sources'):
            with st.expander(f"Sources ({len(result['sources'])})"):
                for i, source in enumerate(result['sources'], 1):
                    st.markdown(f"**[{i}] {source['filename']}**")
                    st.caption(source['quote'])
                    url = source.get('source_url', '')
                    if url.startswith('https://www.dsu.edu.pk/'):
                        st.link_button('View original', url)

    for item in st.session_state.get('messages', []):
        with st.chat_message('user'):
            st.write(item['question'])
        with st.chat_message('assistant'):
            display_result(item['result'])
    question = st.chat_input('Ask about admissions, programs, fees…', max_chars=3000)
    if question is not None:
        if not question.strip():
            st.warning('Please enter a question about the selected knowledge base.')
        else:
            with st.chat_message('user'):
                st.write(question)
            with st.chat_message('assistant'):
                with st.spinner('Finding the answer…'):
                    result = agent.ask(question)
                display_result(result, streaming=True)
            st.session_state.messages.append({'question': question, 'result': result})
