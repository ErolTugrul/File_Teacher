import pdfplumber
import statistics
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import ollama
import json
import os

hf_token = os.getenv("HF_TOKEN")
max_tokens = 400


class SourceBuilder:

    def __init__(self):
        self.db = []
        self.blocks = []
        self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", token=hf_token)

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

                self.blocks.append({
                    "type": "title" if score >= 6 else "paragraph",
                    "source_type": "pdf",
                    "text": text,
                    "pg_num": line[0][0],
                })

    def builder(self):
        if not len(self.blocks):
            self.extract()

        chunks = []
        page = 1
        current_title = []
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
                    # current_title = []  # TODO is this necessary?
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
                    # current_text = []  # TODO is this necessary?

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
                "embedding": self.model.encode(chunk["text"]),
                "text": chunk["text"],
                "metadata": chunk["metadata"]
            })


class RAGBot:
    def __init__(self, builder: SourceBuilder):
        self.builder = builder
        self.db = builder.db

    def question(self, q):
        user_question = q
        query_vec = self.builder.model.encode(user_question)
        scores = []
        for item in self.db:
            score = cosine_similarity(
                [query_vec],
                [item["embedding"]]
            )[0][0]
            scores.append((score, item))

        top_chunks = sorted(scores, reverse=True, key=lambda x: x[0])[:7]

        context_text = "\n\n".join(
            f"{[i + 1]}\nSource: {item['metadata']["section_title"]}\nContent: {item["text"]}"
            for i, (_, item) in enumerate(top_chunks)
        )

        sys_prompt = """
You are a helpful assistant.
User will send you questions with context together.
Answer the questions solely based on the context of the text and don't keep your answers too long.
If there is no text to get your answers from, say "i didn't receive a context to learn".
If the answer is not in the context, say "I don't know".
Answer in 2–3 short paragraphs.
Do not add information that is not explicitly stated in the context.
When possible, quote short phrases from the context.
Do not add the page number to the title names when you are mentioning titles.

If you used a resource you MUST add it inside of this JSON format:

{
  "answer": "your answer here",
  "sources": [1, 2]
}

If there is no source you used, return your answer in this format:
{
  "answer": "your answer here",
}
"""
        prompt = f"""
Context:
{context_text}

Question:
{user_question}
"""

        response = ollama.chat(
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
            source_pages = set()
            if "sources" in parsed.keys() and parsed["sources"]:
                for s in parsed["sources"]:
                    source_pages.add(top_chunks[s - 1][1]["metadata"]["page"])

                ans = parsed["answer"]
                ans += f'\nPage: {sorted(source_pages)}'

                return {"answer": ans}
            else:
                return {"answer": parsed["answer"]}
        except Exception as e:
            return {"answer": f"Error:{e}\nPlease try asking this with different words."}
