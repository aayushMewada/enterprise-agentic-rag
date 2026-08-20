from pathlib import Path
import json

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rag.documents import (
    ingest_changed_documents,
    list_documents,
    metadata_options,
    remove_all_documents,
    remove_document,
    save_upload,
)
from rag.query_engine import (
    answer_from_chunks_if_needed,
    build_debug_payload,
    prepare_query,
    run_query,
    stream_query_answer,
)


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"

app = FastAPI(title="Interview RAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


class ChatMessage(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    question: str
    year: str | None = None
    company: str | None = None
    chat_history: list[ChatMessage] = []
    include_prompt: bool = False


class DeleteDocumentRequest(BaseModel):
    source: str
    delete_file: bool = True


class DeleteAllRequest(BaseModel):
    delete_files: bool = False


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/metadata")
def metadata():
    return metadata_options()


@app.get("/documents")
def documents():
    return {"documents": list_documents()}


@app.post("/query")
def query(request: QueryRequest):
    try:
        return run_query(
            request.question,
            filters=_filters_from_request(request),
            chat_history=[message.model_dump() for message in request.chat_history],
            include_prompt=request.include_prompt,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/query/stream")
def stream_query(request: QueryRequest):
    def events():
        try:
            yield _json_line({"type": "status", "message": "Retrieving sources"})
            payload = prepare_query(
                request.question,
                filters=_filters_from_request(request),
                chat_history=[message.model_dump() for message in request.chat_history],
            )
            if payload.get("direct"):
                yield _json_line(
                    {
                        "type": "sources",
                        "sources": payload["sources"],
                        "chunks": payload["chunks"],
                    }
                )
                yield _json_line({"type": "token", "token": payload["answer"]})
                yield _json_line({"type": "done"})
                return

            yield _json_line(
                {
                    "type": "sources",
                    "sources": payload["sources"],
                    "chunks": payload["chunks"],
                }
            )
            yield _json_line({"type": "status", "message": "Generating answer"})

            answer = ""
            for token in stream_query_answer(payload["prompt"]):
                answer += token
                yield _json_line({"type": "token", "token": token})

            fallback = answer_from_chunks_if_needed(answer, payload["chunks"])
            if fallback != answer:
                yield _json_line({"type": "replace", "answer": fallback})

            yield _json_line({"type": "done"})
        except Exception as exc:
            yield _json_line({"type": "error", "message": str(exc)})

    return StreamingResponse(events(), media_type="application/x-ndjson")


@app.post("/debug-query")
def debug_query(request: QueryRequest):
    try:
        return build_debug_payload(
            request.question,
            filters=_filters_from_request(request),
            chat_history=[message.model_dump() for message in request.chat_history],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    year: str = Form(...),
    company: str = Form(...),
):
    try:
        return save_upload(file.filename or "document.pdf", await file.read(), year, company)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/documents/ingest")
def ingest_documents():
    try:
        return ingest_changed_documents()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/documents")
def delete_document(request: DeleteDocumentRequest):
    try:
        return remove_document(request.source, delete_file=request.delete_file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/documents/all")
def delete_all(request: DeleteAllRequest):
    try:
        return remove_all_documents(delete_files=request.delete_files)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _filters_from_request(request: QueryRequest) -> dict:
    filters = {}
    if request.year:
        filters["year"] = request.year
    if request.company:
        filters["company"] = request.company
    return filters


def _json_line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"
