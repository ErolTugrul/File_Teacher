import pdfplumber
import statistics
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import ollama
import json

max_tokens = 400
db = []

class Source:
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    def __init__(self, file):
        self.file = file
                
    def extract(self):
        global blocks
        self.blocks = []        
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
                
            for n, page in enumerate(f.pages, start=1):
                pg_words = page.extract_words(
                    use_text_flow=True,
                    extra_attrs = ["size", "fontname"]
                )
                words.extend([n, w] for w in pg_words)
                
                    
            sizes = [w[1]["size"] for w in words]
            base_size = sum(sizes) / len(sizes)
            for w in words:
                y = round(w[1]["top"], 1)
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
                line.sort(key=lambda x:x[1]["x0"])
                text = " ".join(w[1]["text"] for w in line)
                avg_size = sum(w[1]["size"] for w in line) / len(line)
                pg_num = line[0][0]
                bold = all("Bold" in w[1]["fontname"] for w in line)
                word_count = len(line)

                self.blocks.append({"type": "block",
                                    "source_type": "pdf",
                                    "text": text,
                                    "pg_num":pg_num,
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
            blocks = self.blocks
        Builder()
                            

        

class Builder:
    def __init__(self):
        global db
        db = []
        chunks = []
        page = 1
        current_title = []
        current_text = []
        for block in blocks:
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
                            "page": page,
                            "source_type": "pdf"
                            }
                    })
                    current_text.append(block["text"])
                    current_text = []

        if current_text:
            chunks.append({
                        "text": " ".join(current_text),
                        "metadata": {
                            "section_title": current_title,
                            "page": page,
                            "source_type": "pdf",
                            }
                    })
        
        for chunk in chunks:
            db.append({
                "embedding": Source.model.encode(chunk["text"]),
                "text": chunk["text"],
                "metadata": chunk["metadata"]
            })




class RAG_bot():
    def ___init__(self):
        pass
    def question(self, q):
        self.db = db
        self.user_question = q
        self.query_vec = Source.model.encode(self.user_question)
        scores = []
        for item in self.db:
            score = cosine_similarity(
                [self.query_vec],
                [item["embedding"]]
            )[0][0]
            scores.append((score, item))

        top_chunks = sorted(scores, reverse=True, key=lambda x: x[0])[:7]

        context_text = "\n\n".join(
            f"{[i+1]}\nSource: {item['metadata']["section_title"]}\nContent: {item["text"]}"
            for i, (_, item) in enumerate(top_chunks)
        )

        prompt = f"""
        You are a helpful assistant.
        Answer the questions solely based on the context of the text and don't keep your answers too long.
        If there is no text to get your answers from, say "i didn't receive a context to learn".
        If the answer is not in the context, say "I don't know".
        Answer in 2–3 short paragraphs.
        Do not add information that is not explicitly stated in the context.
        When possible, quote short phrases from the context.
        Do not add the page number to the title names when you are mentioning titles.

        If you used a resource you MUST add it inside of this JSON format:

{{
"answer": "your answer here",
"sources": [1,2]
}}

        If there is no source you used, return your answer in this format:
{{
"answer": "your answer here",
}}


        Context:
        {context_text}

        Question:
        {self.user_question}
        """ 

        response = ollama.chat(
            model="mistral",
            format = "json",
            options={
                "temperature": 0
            },
            messages=[
                {"role": "system", "content": "Give your answers solely based on the given context. If the answer is absent, tell the user that the answer is absent."},
                {"role": "user", "content": prompt}
            ]
        )

        raw_output = response["message"]["content"]
        try:
            parsed = json.loads(raw_output)
            source_pages = set()
            if "sources" in parsed.keys() and parsed["sources"]:
                for s in parsed["sources"]:
                    source_pages.add(top_chunks[s-1][1]["metadata"]["page"])

                return {"answer": f"""{parsed["answer"]}
                        Page: {sorted(source_pages)}"""}
            else:
                return {"answer": parsed["answer"]}
        except Exception as e:
            return {"answer": f"Error:{e}\nPlease try asking this with different words."}


