from pydantic import BaseModel

class QuestionModel(BaseModel):
    question: str
    file_ids: list
