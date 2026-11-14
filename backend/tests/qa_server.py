"""LOCAL TEST SERVER ONLY. No real university, model provider, account, or documents.

Used to visually verify that genuine LangChain fixture events reach the browser.
Do not configure this module as the live university backend.
"""
from pathlib import Path
from fastapi.responses import PlainTextResponse
from langchain_core.documents import Document
from backend.main import create_app
from .test_rag import META, TEXT, service_for

FIXTURE = Path(__file__).with_name('fixtures') / 'test-handbook.txt'
metadata={key:value for key,value in META.items() if key!='page_start'}
metadata.update(title='[TEST FIXTURE] test-handbook.txt', url='/api/test-documents/fixture-document')
def factory(principal):
    assert principal['test_fixture'] is True
    return service_for([Document(page_content=FIXTURE.read_text().strip(), metadata=metadata)])
app=create_app(service_factory=factory, authorize=lambda _: {'test_fixture':True})
@app.get('/api/test-documents/fixture-document')
async def fixture_document():
    return PlainTextResponse(FIXTURE.read_text())
