from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import uuid
import os
from rag.rag import Source, RAG_bot
import docx2pdf
import shutil
import traceback
from pydantic import BaseModel
import logging


app = FastAPI()

rag_instance = RAG_bot()

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(CURRENT_DIR, "uploads")
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    document_id = str(uuid.uuid4())

    
    try:
        for existing_file in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, existing_file)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"--- DELETED OLD FILE: {existing_file} ---")
            except Exception as e:
                print(f"Error while deleting {existing_file}: {e}")

        name, suffix = os.path.splitext(file.filename)[0], os.path.splitext(file.filename)[1].lower()
        if suffix == ".docx":
            file.file = docx2pdf.convert(os.path.join(UPLOAD_DIR, file.filename), output_path=UPLOAD_DIR)
            file_path = UPLOAD_DIR / (name + ".pdf")
            file.filename = name + ".pdf"
            suffix = ".pdf"

        if suffix == ".pdf":
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            ext = Source(str(file_path))
            ext.extract()

        print(f"--- SUCCESS: File saved to {file_path} ---")
          
        return {
            "document_id": document_id,
            "filename": file.filename,
            "path": str(file_path),
            "message": "Processed"
        }
    except Exception as e:
        print("--- BACKEND ERROR DETECTED ---")
        print(traceback.format_exc()) 
        raise HTTPException(status_code=500, detail=str(e))
    

class HealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()
    
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


class QuestionModel(BaseModel):
    question: str


@app.post("/ask")
def ask(question: QuestionModel):
    try:
        user_query = question.question
        print(f"User is asking: {user_query}")
        answer = rag_instance.question(user_query)

        answer_text = answer if answer else {"answer": "I found no specific answer in the document, could you rephrase?"}
        
        return answer_text
    
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

#cd frontend
#npm run dev

#cd backend
#python -m uvicorn server:app
