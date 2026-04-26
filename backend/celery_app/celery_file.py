from celery import Celery
from rag.rag import SourceBuilder
import logging

logger = logging.getLogger(__name__)
source_builder = SourceBuilder()

app = Celery('pdf_tasks', 
             broker='redis://localhost:6379/0', 
             backend='redis://localhost:6379/0')

@app.task(bind=True)
def process_file(self, filepath, filename):
    logger.info(f"{filename} is being processed...")
    source_builder.extract(file=filepath)
    source_builder.builder(file=filepath, filename=filename)
    return (f"{filename} processed.......")
