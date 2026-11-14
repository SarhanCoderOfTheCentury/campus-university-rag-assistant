import os
import json
import streamlit as st
from dotenv import load_dotenv
from rag.config import ROOT, Settings
from rag.embeddings import GeminiEmbeddings
from rag.store import load_corpus, fingerprint
from rag.agent import RAGAgent, safe_error

load_dotenv(ROOT / '.env')
st.set_page_config(page_title='Campus Evidence | Knowledge Assistant', page_icon='📚', layout='wide')
st.markdown('''<style>
.block-container {max-width:1100px;padding-top:2.4rem;padding-bottom:3rem}
[data-testid="stMetric"]{background:var(--secondary-background-color);padding:14px;border-radius:14px}
[data-testid="stChatMessage"]{border-radius:16px}
.hero-label{color:#38bdf8;font-size:.8rem;letter-spacing:.16em;font-weight:700}
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
def resources(settings, revision, _api_key):
    # Provider key is excluded from Streamlit's shared cache hash; cached objects
    # are only the deployment's configured credential, never visitor-entered keys.
    embeddings = GeminiEmbeddings(_api_key)
    store, chunks, manifest = load_corpus(settings, embeddings)
    return RAGAgent(settings, embeddings, store, chunks, api_key=_api_key), manifest


with st.sidebar:
    st.markdown('### 📚 Campus Evidence')
    st.caption('LangChain · Gemini · Local FAISS')
    corpus_label = st.selectbox('Knowledge base', ['DSU · supplied embeddings', 'Noor Skills · fictional assignment'])
    corpus = 'dsu' if corpus_label.startswith('DSU') else 'demo'
    k = st.select_slider('Retrieved chunks (k)', options=[1, 3, 5, 8, 10], value=5)
    method = st.selectbox('Retrieval method', ['hybrid', 'semantic', 'keyword'])
    with st.expander('Advanced retrieval'):
        rewrite = st.checkbox('Rewrite query with Gemini', value=False)
        rerank = st.checkbox('Re-rank shortlist with Gemini', value=False)
        size = st.slider('Demo chunk size (characters)', 400, 1800, 1000, 100, disabled=corpus=='dsu')
        overlap = st.slider('Demo overlap (characters)', 0, 300, 150, 50, disabled=corpus=='dsu')
        st.caption('DSU retains its original embedded windows. Each optional LLM step uses an extra API call.')
    if st.button('Clear conversation', use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.divider()
    st.caption('Classroom prototype. Answers cite captured documents; verify time-sensitive information with the institution.')

st.markdown('<div class="hero-label">KNOWLEDGE YOU CAN INSPECT</div>', unsafe_allow_html=True)
st.title('DSU Knowledge Assistant' if corpus=='dsu' else 'Noor Skills Institute Assistant')
st.write('Ask about admissions, courses, policies and procedures. Open the evidence to check every answer.')
if corpus == 'dsu':
    st.info('Your supplied DSU embeddings are ready locally. Source capture dates and historical policy changes are unverified.')
else:
    st.info('Fictional assignment dataset: five documents, dated policy versions and two explicit exceptions. Separate from DSU.')

settings = Settings(corpus=corpus, k=k, search=method, chunk_size=size,
    chunk_overlap=overlap, rewrite=rewrite, rerank=rerank,
    model=secret('GEMINI_MODEL') or 'gemini-3.5-flash-lite')
key = secret('GEMINI_API_KEY')
if not key:
    st.warning('Add GEMINI_API_KEY to .env locally or to Streamlit app secrets, then restart. The key is never committed.')
    st.code('GEMINI_API_KEY = "your-key-here"', language='toml')
    st.stop()
try:
    revision = fingerprint(ROOT / 'knowledge/demo', size, overlap) if corpus=='demo' else 'dsu-supplied-v1'
    with st.spinner('Loading the local knowledge index…'):
        agent, manifest = resources(settings, revision, key)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

cols = st.columns(3)
cols[0].metric('Indexed chunks', manifest['rows'])
cols[1].metric('Vector dimensions', manifest['dimensions'])
cols[2].metric('Local store', 'FAISS')

chat, inspect, results = st.tabs(['Ask the assistant', 'Knowledge & pipeline', 'Evaluation evidence'])
with inspect:
    st.subheader('How an answer is built')
    st.write('Route policy intent → optional query rewrite → FAISS + BM25 → reciprocal rank fusion → optional re-ranking → context budget → Gemini → validated source quotations.')
    st.json(manifest)
    st.caption('Displayed progress describes executed steps, not private model reasoning.')
    for file in sorted((ROOT/'knowledge'/corpus).glob('*.md')):
        with st.expander(file.name):
            st.text(file.read_text())
    st.caption('Live challenge: edit a demo policy document, then rerun. Its content fingerprint changes, so the demo embeddings are rebuilt. DSU edits require explicit re-embedding; original vectors remain tied to original chunks.')
with results:
    st.subheader('Reproducible checks')
    st.write('The test set records expected answers and sources before execution. Provider failures are recorded as blocked, never passed.')
    for file in sorted((ROOT/'evidence').glob('*.csv')):
        st.download_button(f'Download {file.name}', file.read_bytes(), file_name=file.name, mime='text/csv')
    summary = ROOT/'evidence/summary.md'
    if summary.exists():
        st.markdown(summary.read_text())
    st.caption('Run python -m scripts.evaluate --suite to regenerate actual answer and citation evidence.')

with chat:
    conversation_key = f'{corpus}:{method}:{k}:{size}:{overlap}:{rewrite}:{rerank}'
    if st.session_state.get('conversation_key') != conversation_key:
        st.session_state.messages = []
        st.session_state.conversation_key = conversation_key
    st.caption('Each question is independent. Include course names and dates in follow-up questions.')
    examples = (['What is the application processing fee?', 'How do I apply for admission?', 'What is the hostel price?'] if corpus=='dsu' else
        ['How much is Web Foundations plus the processing fee?', 'Compare old and current attendance requirements.', 'What is the director’s personal mobile number?'])
    st.caption('Try: ' + ' • '.join(examples))

    def display_result(result, key_prefix):
        if result['status'] == 'api_error':
            st.error(result['answer'])
        else:
            st.markdown(result['answer'])
        if result.get('sources'):
            with st.expander('Sources & supporting excerpts', expanded=True):
                for i, source in enumerate(result['sources'], 1):
                    st.markdown(f"**{i}. {source['filename']}** · {source['status']} · version {source['version']}")
                    st.text(source['quote'])
                    url = source.get('source_url', '')
                    if url.startswith('https://www.dsu.edu.pk/'):
                        st.link_button('Open source webpage', url)
        with st.expander('Retrieved chunks & retrieval trace'):
            st.json(result.get('trace', {}))
            for row in result.get('retrieved', []):
                st.markdown(f"**{row['filename']}** · `{row['id']}`")
                st.caption(f"cosine={row['cosine']} | BM25={row['bm25']} | RRF={row['rrf']}")
                st.text(row['text'])
        st.download_button('Download this answer and its evidence', json.dumps(result, ensure_ascii=False, indent=2),
            file_name='answer_evidence.json', mime='application/json', key=key_prefix+'_download')

    for item_index, item in enumerate(st.session_state.get('messages', [])):
        with st.chat_message('user'):
            st.write(item['question'])
        with st.chat_message('assistant'):
            display_result(item['result'], f'message_{item_index}')
    question = st.chat_input('Ask a question about the selected documents', max_chars=3000)
    if question is not None:
        if not question.strip():
            st.warning('Please enter a question about the selected knowledge base.')
        else:
            with st.chat_message('user'):
                st.write(question)
            with st.chat_message('assistant'):
                with st.status('Checking the documents…', expanded=True) as progress:
                    labels = {'route': 'Selected the policy scope and search query.',
                        'retrieve': 'Retrieved and packed source evidence.', 'answer': 'Generated the response and checked citation quotations.'}
                    def step(node, values):
                        st.write(labels[node])
                    result = agent.ask(question, on_step=step)
                    progress.update(label='Request needs attention' if result['status']=='api_error' else 'Evidence check complete',
                        state='error' if result['status']=='api_error' else 'complete', expanded=False)
                display_result(result, f'message_{len(st.session_state.messages)}')
            st.session_state.messages.append({'question': question, 'result': result})
