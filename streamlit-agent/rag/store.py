"""Portable FAISS + JSON, never unpickle an uploaded vector store."""
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
import faiss
import numpy as np
from langchain_core.documents import Document
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from .config import ROOT
from .embeddings import DIMENSIONS, MODEL, normalize

HISTORY = 'historical_comparison_only_no_current_policy_answers'


def fingerprint(directory: Path, size: int, overlap: int) -> str:
    h = hashlib.sha256(f'{MODEL}:{DIMENSIONS}:{size}:{overlap}:schema-2'.encode())
    for p in sorted(directory.rglob('*')):
        if p.suffix.lower() in ('.md', '.txt', '.pdf'):
            h.update(str(p.relative_to(directory)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def load_documents(directory: Path) -> list[Document]:
    documents = []
    for p in sorted(directory.rglob('*')):
        if p.suffix.lower() not in ('.md', '.txt', '.pdf'):
            continue
        text = ('\n'.join(page.extract_text() or '' for page in PdfReader(p).pages)
                if p.suffix.lower() == '.pdf' else p.read_text(encoding='utf-8'))
        def field(name, default):
            match = re.search(rf'(?im)^{name}:\s*(.+)$', text)
            return match.group(1).strip() if match else default
        documents.append(Document(page_content=text, metadata={
            'source': p.name, 'filename': p.name, 'status': field('Status', 'reference'),
            'version': field('Version', 'unverified'),
            'effective_date': field('Effective', 'unknown'),
            'superseded_at': field('Superseded', ''),
            'source_url': '', 'parent_id': p.name,
        }))
    if not documents:
        raise ValueError('No text, Markdown or text-based PDF documents found.')
    return documents


def split_documents(documents, size=1000, overlap=150):
    splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap,
        add_start_index=True)
    chunks = splitter.split_documents(documents)
    for i, c in enumerate(chunks):
        c.metadata['id'] = hashlib.sha256(
            (c.metadata['source'] + str(c.metadata['start_index']) + c.page_content).encode()
        ).hexdigest()[:20]
        c.metadata['position'] = i
    return chunks


def make_store(chunks, vectors, embeddings):
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.shape != (len(chunks), DIMENSIONS):
        raise ValueError('Vector rows/dimensions do not match chunk metadata.')
    vectors = normalize(vectors)
    ids = [c.metadata['id'] for c in chunks]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate chunk identifiers.')
    index = faiss.IndexFlatIP(DIMENSIONS)
    index.add(vectors)
    store = FAISS(embeddings, index, InMemoryDocstore(dict(zip(ids, chunks))),
        dict(enumerate(ids)), distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT)
    return store


def load_dsu(embeddings):
    base = ROOT / 'data/dsu'
    vectors = np.load(base / 'vectors.npy', allow_pickle=False)
    records = [json.loads(line) for line in (base / 'chunks.jsonl').read_text().splitlines()]
    chunks = []
    for r in records:
        source = r.get('document') or 'unknown'
        m = {k: v for k, v in r.items() if k not in ('content', 'text', 'embedding')}
        m.update(source=source, filename=source, version='unverified',
            status='archived_unverified' if r.get('retrieval_policy') == HISTORY else 'captured_unverified',
            effective_date='unknown', position=r.get('window_index', 0))
        chunks.append(Document(page_content=r.get('content') or r['text'], metadata=m))
    store = make_store(chunks, vectors, embeddings)
    return store, chunks, {'corpus': 'dsu', 'rows': len(chunks), 'dimensions': DIMENSIONS,
        'model': MODEL, 'fingerprint': hashlib.sha256((base/'chunks.jsonl').read_bytes() + (base/'vectors.npy').read_bytes()).hexdigest(),
        'note': 'Supplied embeddings imported; original chunking preserved. Policy dates unverified.'}


def load_demo(embeddings, size=1000, overlap=150, rebuild=False, cache_root=None):
    source = ROOT / 'knowledge/demo'
    digest = fingerprint(source, size, overlap)
    root = cache_root or ROOT / '.cache/indexes'
    target = root / digest
    if target.exists() and not rebuild:
        data = json.loads((target/'chunks.json').read_text())
        chunks = [Document(**row) for row in data]
        vectors = np.load(target/'vectors.npy', allow_pickle=False)
    else:
        chunks = split_documents(load_documents(source), size, overlap)
        vectors = normalize(embeddings.embed_documents([c.page_content for c in chunks]))
        root.mkdir(parents=True, exist_ok=True)
        temp = Path(tempfile.mkdtemp(dir=root))
        try:
            (temp/'chunks.json').write_text(json.dumps([c.model_dump() for c in chunks]))
            np.save(temp/'vectors.npy', vectors, allow_pickle=False)
            if target.exists():
                shutil.rmtree(target)
            temp.rename(target)
        finally:
            if temp.exists():
                shutil.rmtree(temp)
    store = make_store(chunks, vectors, embeddings)
    return store, chunks, {'corpus': 'demo', 'rows': len(chunks), 'dimensions': DIMENSIONS,
        'model': MODEL, 'fingerprint': digest, 'chunk_size': size, 'chunk_overlap': overlap}


def load_corpus(settings, embeddings, rebuild=False):
    if settings.corpus == 'dsu':
        return load_dsu(embeddings)
    return load_demo(embeddings, settings.chunk_size, settings.chunk_overlap, rebuild)
