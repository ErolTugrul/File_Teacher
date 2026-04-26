import pdfplumber
import statistics
import os
from ollama import Client
import json
from vector_store.vector_store import VectorDBManager
import string

max_tokens = 256
vectordb = VectorDBManager()

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
client = Client(host=OLLAMA_URL)
model_name = "mistral"

try:
    models = client.list()
    if not any(m.model.startswith(model_name) for m in models.models):
        print(f"Model {model_name} not found, downloading (This might take a while.)...")
        client.pull(model_name)
        print("Model downloaded successfully.")
except Exception as e:
    print(f"Error while connecting to Ollama or downloading model: {e}")

class SourceBuilder:
    def __init__(self):
        self.blocks = []

    def extract(self, file=None):
        if not file:
            return
        with pdfplumber.open(file) as f:
            lines = {}
            y_gaps = []
            words = []

            for n, page in enumerate(f.pages, start=1):
                pg_words = page.extract_words(
                    use_text_flow=True,
                    extra_attrs=["size", "fontname"]
                )
                words.extend([n, w] for w in pg_words)

            sizes = [w[1]["size"] for w in words]
            base_size = sum(sizes) / len(sizes)
            for w in words:
                y = round(w[1]["top"], 1)
                lines.setdefault(y, []).append(w)

            for i in range(1, len(lines.keys())):
                prev = list(lines.keys())[i - 1]
                curr = list(lines.keys())[i]

                gap = curr - prev

                if gap <= 0 or gap > 50:
                    continue

                y_gaps.append(gap)

            avg_gap = statistics.median(y_gaps)

            for y, line in lines.items():
                line.sort(key=lambda x: x[1]["x0"])
                text = " ".join(w[1]["text"] for w in line)

                score = 0
                if all("Bold" in w[1]["fontname"] for w in line):
                    score += 2
                if sum(w[1]["size"] for w in line) / len(line) >= base_size:
                    score += 2
                if text.endswith("."):
                    score -= 1
                if text.count(".") > 5:
                    score -= 2
                elif text.endswith(":"):
                    score += 1
                word_count = len(line)
                if word_count <= 10:
                    score += 2
                elif word_count <= 15:
                    score += 1
                if y > avg_gap:
                    score += 2
                elif y > avg_gap * 2:
                    score -= 1
                if  not all(c in string.ascii_letters + string.digits + string.punctuation + " _" for c in text[:-2]):
                    score -= 2

                self.blocks.append({
                    "type": "title" if score >= 6 else "paragraph",
                    "source_type": "pdf",
                    "text": text,
                    "pg_num": line[0][0],
                })

    def builder(self, file, filename):
        if not len(self.blocks):
            self.extract(file=file)
        else:
            self.blocks=[]
            self.extract(file=file)

        chunks = []
        page = 1
        current_title = ""
        current_text = []
        for block in self.blocks:
            if block["type"] == "title":
                page = block["pg_num"]
                if current_text:
                    chunks.append({
                        "text": " ".join(current_text),
                        "metadata": {
                            "section_title": current_title,
                            "page": page,
                            "source_type": "pdf"
                        }
                    })
                    current_text = []
                current_title = block["text"]

            elif block["type"] == "paragraph":
                if (len(" ".join(current_text)) // 3.7) <= max_tokens - (len(block["text"]) // 3.7) - 60:
                    current_text.append(block["text"])
                else:
                    chunks.append({
                        "text": " ".join(current_text),
                        "metadata": {
                            "section_title": current_title,
                            "page": page,
                            "source_type": "pdf"
                        }
                    })
                    current_text = [" ".join(current_text)[-200:]]
                    current_text.append(block["text"])

        if current_text:
            chunks.append({
                "text": " ".join(current_text),
                "metadata": {
                    "section_title": current_title,
                    "page": page,
                    "source_type": "pdf",
                }
            })

        vectordb.add_chunks(chunks=chunks, file_id=filename)


class RAGBot:
    def __init__(self):
        pass

    def question(self, question, file_ids):
        top_chunks = vectordb.search(question, file_ids)
    
        context_text = "\n\n".join(
            f"[{i+1}]\nSource: {top_chunks["metadatas"][0][i]["section_title"]}\nContent: {top_chunks["documents"][0][i]}" 
            for i in range(len(top_chunks["ids"][0])))
              
        sys_prompt = """
You are a helpful assistant.
User will send you questions with context together.
Answer the questions solely based on the context of the text and don't keep your answers too long.
If there is no text to get your answers from, say "i didn't receive a context to learn".
If the answer is not in the context, say "I don't know".
Answer in 5 paragraphs maximum.
Do not add information that is not explicitly stated in the context.
When possible, quote short phrases from the context.
Do not add the page number to the title names when you are mentioning titles.

If you used a resource you MUST answer in this format only:
{
  "answer": "your answer here",
  "sources": [1, 2]
}

DO NOT use a statement like 'as stated in [x]' ever in the answer part of the format.

If there is no source you used, return your answer in this format:
{
  "answer": "your answer here",
}
"""
        prompt = f"""
Context:
{context_text}

Question:
{question}
"""

        response = client.chat(
            model="mistral",
            format="json",
            options={
                "temperature": 0
            },
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt}
            ]
        )

        raw_output = response["message"]["content"]
        try:
            parsed = json.loads(raw_output)
            if "sources" in parsed.keys() and parsed["sources"] and len(file_ids) < 2:
                source_pages = set()
                for s in parsed["sources"]:
                    source_pages.add(top_chunks["metadatas"][0][s-1]["page"])

                ans = parsed["answer"]
                ans += f'\nPage: {sorted(source_pages)}'

                return {"answer": ans}
            else:
                return {"answer": parsed["answer"]}
        except Exception as e:
            return {"answer": f"Error:{e}\nPlease try asking this with different words."}
