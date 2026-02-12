from pathlib import Path
import docx2pdf
import pdfplumber
import statistics
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import ollama

url = "files/Paragraphs.pdf"

max_tokens = 400
db = []
scores = []



class Source:
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    blocks = []   
    def __init__(self, file):
        if Path(file).suffix == ".docx":
            p = docx2pdf.convert(file),
            file = file.removesuffix(".docx") + ".pdf"
        self.file = file  
        
    def extract(self):
        def is_heading(block, y):
                score = 0
                if block["is_bold"] == True:
                    score += 2

                if block["avg_size"] >= base_size:
                    score +=2
                
                if block["text"].endswith("."):
                    score -= 1
                elif block["text"].endswith(":"):
                    score +=1

                if block["word_count"] <= 10:
                    score += 2
                elif block["word_count"] <= 15:
                    score += 1
                
                if y > avg_gap:
                    score += 2
                elif y > avg_gap * 2:
                    score -= 1

                return score
                
        with pdfplumber.open(self.file) as f:
            lines = {}
            y_gaps = []
            words = []
                
            for page in f.pages:
                pg_words = page.extract_words(
                    use_text_flow=True,
                    extra_attrs = ["size", "fontname"]
                )
                words.extend(pg_words)
                
                    
            sizes = [w["size"] for w in words]
            base_size = sum(sizes) / len(sizes)
            for  w in words:
                y = round(w["top"], 1)
                lines.setdefault(y, []).append(w)
                    
            for i in range(1, len(lines.keys())):
                prev = list(lines.keys())[i-1]
                curr = list(lines.keys())[i]

                gap = curr - prev


                if gap <= 0 or gap > 50:
                    continue
                    
                y_gaps.append(gap)
                
            avg_gap = statistics.median(y_gaps)

            for y, line in lines.items():
                line.sort(key=lambda x:x["x0"])
                text = " ".join(w["text"] for w in line)
                avg_size = sum(w["size"] for w in line) / len(line)
                bold = all("Bold" in w["fontname"] for w in line)
                word_count = len(line)

                self.blocks.append({"type": "block",
                                    "source_type": "pdf",
                                    "text": text,
                                    "is_bold": bold,
                                    "avg_size": avg_size,
                                    "word_count": word_count,
                                    "y": y,
                                    })
                    
            for block in self.blocks:
                if is_heading(block, gap) >= 6:
                    block["type"] = "title"
                else:
                    block["type"] = "paragraph"
                            

        

class Builder:
    def __init__(self):
        pass

    def semantic_chunker(self):
        chunks = []

        current_title = ""
        current_text = []
        for block in Source.blocks:
            if block["type"] == "title":
                if current_text:
                    chunks.append({
                        "text": " ".join(current_text),
                        "metadata": {
                            "section_title": current_title,
                            "source_type": "pdf",
                            }
                        
                    })
                    current_text = []
                    current_title = ""
                current_title = block["text"]

            elif block["type"] == "paragraph":
                
                if (len(" ".join(current_text)) // 3.7) <= max_tokens - (len(block["text"]) // 3.7):
                    current_text.append(block["text"])

                else:
                    chunks.append({
                        "text": " ".join(current_text),
                        "metadata": {
                            "section_title": current_title,
                            "source_type": "pdf",
                            }
                    })
                    current_text.append(block["text"])
                    current_text = []

        if current_text:
            chunks.append({
                        "text": " ".join(current_text),
                        "metadata": {
                            "section_title": current_title,
                            "source_type": "pdf",
                            }
                    })
        
        for chunk in chunks:
            db.append({
                "embedding": Source.model.encode(chunk["text"]),
                "text": chunk["text"],
                "metadata": chunk["metadata"]
            })


file = Source(url)
file.extract()

Builder().semantic_chunker()

class RAG_bot():
    def __init__(self):
        pass
    def question(self):
        self.user_question = input("Your question about your file ?: ")
        self.query_vec = Source.model.encode(self.user_question)
        for item in db:
            score = cosine_similarity(
                [self.query_vec],
                [item["embedding"]]
            )[0][0]
            scores.append((score, item))

        top_chunks = sorted(scores, reverse=True, key=lambda x: x[0])[:5]

        context_text = "\n\n".join(
            f"[{i+1}]\n{item['metadata']["section_title"]}\n{item["text"]}"
            for i, (_, item) in enumerate(top_chunks)
        )

        prompt = f"""
        You are a helpful assistant.
        Answer the question ONLY using the context below and don't keep your answers too long.
        If the answer is not in the context, say "I don't know".
        Answer in 2–3 short paragraphs.
        Do not add information that is not explicitly stated in the context.
        When possible, quote short phrases from the context.

        Context:
        {context_text}

        Question:
        {self.user_question}
        """ 

        response = ollama.chat(
            model="mistral",
            messages=[
                {"role": "system", "content": "Give your answers solely based on the given context. If the answer is absent, tell the user that the answer is absent."},
                {"role": "user", "content": prompt}
            ]
        )

        print(response["message"]["content"])

system = RAG_bot()
system.question()

#what is the main idea of this text ?
#source .venv/Scripts/activate
#python main.py
