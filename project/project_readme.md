# Trợ lý Hỗ trợ Học tập Thông minh - NLP Course Assistant (CO3085)

Hệ thống **Course Assistant** hỗ trợ sinh viên tra cứu và hỏi đáp thông tin môn học **Xử lý Ngôn ngữ Tự nhiên (CO3085)** bằng ngôn ngữ tự nhiên tiếng Việt, kết hợp pipeline NLP cổ điển (CFG Grammar, Chart/Recursive-Descent Parser, Rule-based Semantic Interpretation, Local Discourse Context) với truy xuất thông tin thống kê (TF-IDF) và mở rộng bằng mô hình ngôn ngữ lớn (FAISS + OpenAI LLM/RAG).

---

## 1. Thành viên nhóm

| STT | Họ và tên | MSSV | Vai trò & Hạng mục phụ trách |
| :-: | :--- | :---: | :--- |
| 1 | *[Điền Tên TV1]* | *[MSSV 1]* | Thiết kế văn phạm CFG (`course_assistant.cfg`), thuật toán sinh câu (`generator.py`), xuất `grammar.txt` & `samples.txt`. |
| 2 | *[Điền Tên TV2]* | *[MSSV 2]* | Xây dựng bộ phân tích cú pháp (`parser.py`), ánh xạ ngữ nghĩa & bóc tách Intent/Entity (`semantic.py`, `formatters.py`), xuất `parse-results.txt`, `semantic.txt`, `intent-entity.txt`. |
| 3 | *[Điền Tên TV3]* | *[MSSV 3]* | Chuẩn hóa Knowledge Base (`knowledge_base.py`, `knowledge_base.json`), truy xuất thông tin TF-IDF & FAISS/LLM RAG (`retriever.py`, `index.py`, `prompt.py`, `answer.py`), xuất `query.txt`, `retrieval.txt`, `answer.txt`, `answer_llm.txt`. |
| 4 | *[Điền Tên TV4]* | *[MSSV 4]* | Xử lý ngữ cảnh hội thoại cục bộ Phần III (`dialogue.py`), đánh giá hệ thống tự động Phần IV (`evaluation.py`), tích hợp pipeline (`pipeline.py`, `cli.py`), cấu hình Docker & tài liệu hệ thống. |

---

## 2. Hướng dẫn cài đặt

### Yêu cầu môi trường
- **Python:** Phiên bản `>= 3.11` (hỗ trợ Python 3.11, 3.12, 3.13).
- **Docker (Tùy chọn):** Docker Desktop / Docker Engine để chạy trong container.

### Cài đặt thư viện
Mở terminal / PowerShell tại thư mục `project/` (thư mục chứa `Dockerfile` và `requirements.txt`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> **Lưu ý:** Chế độ mặc định (`"option": "statistical"` trong `models/rag_config.json`) chỉ sử dụng thư viện chuẩn của Python nên có thể chạy ngay lập tức mà **không cần** cài đặt các gói ngoài hay API key. Nếu chuyển sang `"option": "llm"`, cần cấu hình biến môi trường `OPENAI_API_KEY` trong file `.env`.

---

## 3. Hướng dẫn chạy chương trình

### Cách 1: Chạy trực tiếp bằng Python
Tại thư mục `project/`, chạy lệnh:

```powershell
$env:PYTHONPATH = "src"
python -m course_assistant
```

*(Trên Linux/macOS/Git Bash: `PYTHONPATH=src python -m course_assistant`)*

Sau khi chạy xong, toàn bộ các file kết quả sẽ được sinh tự động trong thư mục `output/`:
- `output/grammar.txt` (Phần I.1)
- `output/samples.txt` (Phần I.2)
- `output/parse-results.txt` (Phần I.3)
- `output/semantic.txt` (Phần II.1)
- `output/intent-entity.txt` (Phần II.2)
- `output/query.txt` & `output/retrieval.txt` (Phần II.3)
- `output/answer.txt` (và `output/answer_llm.txt` khi bật chế độ LLM - Phần II.4)
- `output/dialogue.txt` (Phần III - Ngữ cảnh hội thoại cục bộ)
- `output/evaluation.txt` (Phần IV - Đánh giá hệ thống)

### Cách 2: Chạy bằng Docker
```powershell
docker build -t course-assistant .
docker run --rm -v "${PWD}\output:/app/output" course-assistant
```

---

## 4. Mô tả kiến trúc hệ thống

Hệ thống được thiết kế theo kiến trúc đường ống (pipeline) phân tầng rõ ràng giữa xử lý ngôn ngữ tự nhiên cốt lõi và tầng truy xuất tri thức:

```text
Input Question / Dialogue (input/sentences.txt, input/dialogue.txt)
   │
   ▼
[1. Text Normalization & CFG Parser] (nlp/grammar.py, nlp/parser.py)
   ├── Chuẩn hóa Unicode NFC, chữ thường, dấu câu, ký hiệu L.O.
   └── Phân tích cú pháp theo văn phạm CFG -> Xuất cây cú pháp hoặc '()'
   │
   ▼
[2. Local Discourse Context Resolution - Phần III] (rag/dialogue.py)
   └── Lưu trạng thái thực thể lượt trước; giải quyết đại từ ("Nó") và danh ngữ
       quy chiếu ("chương này", "phần này", "chương sau", "nội dung này")
   │
   ▼
[3. Semantic Interpretation & Intent/Entity Extraction] (nlp/semantic.py)
   ├── Ánh xạ cây cú pháp sang biểu diễn hàm vị từ: ACTION(slot=value, ...)
   └── Phân loại Intent & chuẩn hóa thực thể (CO3085, WEEK_03, CH04, LO2.5, ...)
   │
   ▼
[4. Knowledge Base Query & Hybrid RAG Engine] (rag/retriever.py, rag/answer.py)
   ├── Lựa chọn 1 (Classical/Statistical): Tra cứu cấu trúc JSON + TF-IDF cosine similarity
   └── Lựa chọn 2 (LLM/RAG Extension): Truy xuất vector FAISS + Grounded Prompt + GPT-4o-mini
   │
   ▼
[5. Grounded Answer & Automated Evaluation - Phần IV] (evaluation.py)
   └── Sinh câu trả lời hoặc thông báo từ chối chuẩn; chấm điểm bộ test & phân tích lỗi
```

---

## 5. Mô tả Grammar (Văn phạm)

---

## 6. Mô tả Parser (Bộ phân tích cú pháp)

---

## 7. Mô tả Semantic Representation (Biểu diễn ngữ nghĩa)

---

## 8. Mô tả phương pháp xử lý Intent / Entity & Ngữ cảnh Hội thoại

---

## 9. Mô tả Knowledge Base và cách truy vấn

---

## 10. Mô tả lựa chọn Classical/Statistical NLP và Mở rộng LLM/RAG

---

## 11. Mô tả cách đánh giá 

---

## 12. Các hạn chế của hệ thống
