from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import uuid
import os
from rag import Source, Builder, RAG_bot
import docx2pdf

app = FastAPI()

origins = [
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)



UPLOAD_DIR = "C:/Users/User/Desktop/pdf_teacher_v1/backend/files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    global db
    document_id = str(uuid.uuid4())
    
    name, suffix = os.path.splitext(file.filename)[0], os.path.splitext(file.filename)[1].lower()
    if suffix == ".docx":
        docx2pdf.convert(os.path.join(UPLOAD_DIR, file.filename), output_path=UPLOAD_DIR)
        file_path = os.path.join(UPLOAD_DIR, name + ".pdf")
        file.filename = name + ".pdf"
        suffix = ".pdf"

    if suffix == ".pdf":
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        ext = Source(file_path)
        ext.extract()
        db = Builder().semantic_chunker()


        return {
            "document_id": document_id,
            "filename": file.filename,
            "status": "indexed"
        }
    
    else:
        return "I can only read .docx or .pdf files!"
    

@app.post("/ask")
def ask(question:str):
    system = RAG_bot(question, db)
    answer = system.question()
    return answer

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

#C:/Users/User/Desktop/File_Teacher/.venv/Scripts/Activate.ps1
#cd backend
#python -m uvicorn server.server:app
#what is the main context ?