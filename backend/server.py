from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from celery.result import AsyncResult

from celery_app.celery_file import process_file
from vector_store.vector_store import VectorDBManager 

from helpers import HealthCheckFilter
from schemas import QuestionModel
from rag.rag import SourceBuilder, RAGBot
import shutil
import traceback
import logging
import subprocess

app = FastAPI()
source_builder = SourceBuilder()
rag_instance = RAGBot()
db = VectorDBManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())
logger = logging.getLogger(__name__)
UPLOAD_DIR = "/app/temp_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    print(f"{len(files)} amount of files have been uploaded.")
    if os.listdir(UPLOAD_DIR):
        for f in os.listdir(UPLOAD_DIR):
            os.remove(os.path.join(UPLOAD_DIR, f))

    soffice_path = shutil.which("soffice") or shutil.which("libreoffice")

    if not soffice_path:
        raise HTTPException(
            status_code=500,
            detail="Couldn't resolve LibreOffice from the system. Check DockerFile."
        )
    task_ids = []                
    filenames =[]
    for file in files:
        try:
            name, suffix = os.path.splitext(file.filename)[0], os.path.splitext(file.filename)[1].lower()
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            filenames.append(file.filename)
            await file.seek(0)
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
                buffer.flush()
                os.fsync(buffer.fileno())

            if suffix == ".docx":
                output_pdf = os.path.join(UPLOAD_DIR, name + ".pdf")
                command = [soffice_path,
                            "--headless",
                            "--convert-to", "pdf",
                            "--outdir", UPLOAD_DIR,
                            file_path
                           ]
                result = subprocess.run(command,
                                        capture_output=True,
                                        text=True,
                                        check=True)

                os.remove(file_path)
                file_path = output_pdf
                file.filename = f"{name}.pdf"
                suffix = ".pdf"

            if suffix == ".pdf":
                task = process_file.delay(file_path, file.filename)
                task_ids.append(task.id)

        except Exception as e:
            logger.error("--- BACKEND ERROR DETECTED ---")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
    print(f"file ids: {filenames}")
              
    return {"task_ids": task_ids, "message": "İşlem başlatıldı."}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    task_result = AsyncResult(task_id, app=process_file)
    return {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result if task_result.ready() else None
    }

@app.post("/ask")
def ask(question: QuestionModel):
    try:
        user_query = question.question
        file_names = [os.path.splitext(f)[0] for f in question.file_ids]
        file_ids = [f + ".pdf" for f in file_names]
        answer = rag_instance.question(user_query, file_ids=file_ids)

        answer_text = answer if answer else {
            "answer": "I found no specific answer in the document, could you rephrase?"
        }

        return answer_text

    except Exception as e:
        logger.error("Ask Error Detected")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/reset")
async def reset_database():
    try:
        db.clear_all_memory()
        return {"message": "Memory cleaned successfully."}
    except Exception as e:
        return {"error": str(e)}
    


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
