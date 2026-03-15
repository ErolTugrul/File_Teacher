from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import uuid
import os

from backend.helpers import HealthCheckFilter
from backend.schema import QuestionModel
from rag.rag import SourceBuilder, RAGBot
import docx2pdf
import shutil
import traceback
import logging

app = FastAPI()
source_builder = SourceBuilder()
rag_instance = RAGBot(source_builder)

# origins = [
#     "http://localhost:5173",
#     "http://127.0.0.1:5173"
# ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())
logger = logging.getLogger(__name__)
UPLOAD_DIR = ""


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    document_id = str(uuid.uuid4())

    try:
        for existing_file in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, existing_file)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.info(f"--- DELETED OLD FILE: {existing_file} ---")
            except Exception as e:
                logger.error(f"Error while deleting {existing_file}: {e}")

        name, suffix = os.path.splitext(file.filename)[0], os.path.splitext(file.filename)[1].lower()
        file_path = ""
        if suffix == ".docx":
            file.file = docx2pdf.convert(os.path.join(UPLOAD_DIR, file.filename), output_path=UPLOAD_DIR)
            file.filename = f"{name}.pdf"
            suffix = ".pdf"
            logger.warning(f"--- Converting {name}.docx to PDF")

        if suffix == ".pdf":
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)  # TODO ?

            source_builder.extract(file_path)

        logger.info(f"--- SUCCESS: File saved to {file_path} ---")

        return {
            "document_id": document_id,
            "filename": file.filename,
            "path": str(file_path),
            "message": "Processed"
        }
    except Exception as e:
        logger.error("--- BACKEND ERROR DETECTED ---")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask")
def ask(question: QuestionModel):
    try:
        user_query = question.question
        logger.info(f"User is asking: {user_query}")
        answer = rag_instance.question(user_query)

        answer_text = answer if answer else {
            "answer": "I found no specific answer in the document, could you rephrase?"
        }

        return answer_text

    except Exception as e:
        logger.error("Ask Error Detected")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_DIR = os.path.join(CURRENT_DIR, "uploads")
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    uvicorn.run(app, host="0.0.0.0", port=8000)
