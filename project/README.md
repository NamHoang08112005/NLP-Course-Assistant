# Course Assistant

## Current status

Đây là project Python cho bài tập lớn NLP Course Assistant. Project có pipeline
Group A và các module RAG cho phần Group B:

```text
input/sentences.txt
        -> grammar -> parser -> semantic representation -> intent/entity
        -> output/
```

## Yêu cầu môi trường

- Python 3.11 trở lên. Python 3.11, 3.12, 3.13 và 3.14 đều có thể dùng.
- hoặc Docker Desktop nếu chạy bằng container.

Option RAG thống kê dùng thư viện chuẩn của Python. Option RAG dùng LLM cần các
dependency trong `requirements.txt`; cài bằng lệnh
`python -m pip install -r requirements.txt`.

## Cấu trúc chính

```text
project/
├── data/
│   ├── course/                  # Knowledge base mẫu của môn học
│   ├── evaluation/              # Các câu hỏi dùng để test hệ thống
│   ├── grammar/course_assistant.cfg
│   └── lexicon/entities.txt
├── input/
│   ├── sentences.txt            # Mỗi dòng là một câu cần phân tích
│   └── dialogue.txt             # Các đoạn hội thoại có ngữ cảnh
├── output/
│   ├── Expected/                # Kết quả tham khảo, không sửa file này
│   └── ...                      # Kết quả được sinh khi chạy chương trình
├── src/course_assistant/
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

## Chạy trực tiếp bằng Python

Mở PowerShell tại thư mục gốc của project (thư mục chứa `Dockerfile`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
python -m course_assistant
```

Nếu PowerShell chặn activate script, có thể chạy không cần activate:

```powershell
$env:PYTHONPATH = "src"
python -m course_assistant
```

Kiểm tra các phiên bản Python đã được cài trên Windows bằng:

```powershell
py --list
```

Chỉ chọn phiên bản từ **3.11 trở lên**. Ví dụ, nếu kết quả có `3.12` nhưng
không có `3.11`, dùng `py -3.12 -m venv .venv`.

## Chương trình thực hiện & Kiến trúc hệ thống

Kiến trúc hệ thống chạy theo một pipeline tuần tự từ xử lý ngôn ngữ tự nhiên đến truy xuất tri thức:

### 1. Đọc các câu hỏi từ
```text
input/sentences.txt
```
- Mỗi dòng trong file là một câu hỏi hoặc yêu cầu.
- Chương trình xử lý lần lượt từng dòng.

### 2. Phân tích từng câu bằng
```text
Grammar -> Parser -> Semantic -> Intent/Entity
```
- **Mô tả Grammar:** Đọc văn phạm CFG chuyên biệt cho miền CO3085 trong `data/grammar/course_assistant.cfg`. Bao phủ 8 nhóm câu hỏi chính: Thông tin chung, Lịch học, Nội dung chương, Chuẩn đầu ra, Bài tập lớn, Deadline, Tài liệu, và Quy định.
- **Mô tả Parser:** Xây dựng bộ phân tích cú pháp đệ quy có nhớ (Memoized Top-Down Recursive-Descent). Kiểm tra câu có phù hợp với văn phạm và tạo cây cú pháp, kết hợp chặn các cụm từ sai ngữ cảnh từ vựng.
- **Mô tả Semantic Representation:** Ánh xạ cây cú pháp sang biểu diễn ngữ nghĩa dạng vị từ - đối số (ví dụ: `GET_CREDIT(course=CO3085)`).
- **Mô tả Intent/Entity:** Bóc tách ý định (Intent) và chuẩn hóa các thực thể (Entity) qua từ điển `entities.txt` để truyền cho module RAG. Hỗ trợ xử lý ngữ cảnh hội thoại cục bộ (nhận diện "chương này", "phần này").

### 3. Ghi kết quả vào thư mục
```text
output/
```
- `output/grammar.txt`: văn phạm được sử dụng.
- `output/samples.txt`: tối đa 10.000 câu được sinh từ CFG.
- `output/parse-results.txt`: cây cú pháp của từng câu.
- `output/semantic.txt`: biểu diễn ngữ nghĩa của từng câu.
- `output/intent-entity.txt`: intent và entity được nhận diện.
- `output/query.txt`: câu hỏi kèm intent/entity theo format `Q001 | QUERY | EXPECTED_INTENT | EXPECTED_ENTITY`.
- `output/retrieval.txt`: Trích xuất context từ knowledge base (hiển thị Nguồn và Context).
- `output/dialogue.txt`: Kết quả phân giải ngữ cảnh hội thoại cục bộ (Phần III).
- `output/evaluation.txt`: Báo cáo đánh giá hệ thống (Phần IV).
- `output/answer.txt` hoặc `output/answer_llm.txt`: mỗi dòng chỉ chứa số thứ tự và câu trả lời, tùy option RAG được chọn.

## Knowledge Base & RAG phần II

- **Mô tả Knowledge Base:** Dữ liệu thô (`data/course/*.txt`) được parse tự động thành file `knowledge_base.json` có cấu trúc phân cấp để tra cứu.
- **Lựa chọn Classical vs LLM:** Hệ thống hỗ trợ cả 2 chế độ, cấu hình qua khóa `option` trong `models/rag_config.json`:

1. `"option": "statistical"` (mặc định - Lựa chọn 1): Sử dụng phương pháp Classical NLP. Truy xuất TF-IDF (Unigram+Bigram) từ `knowledge_base.json` kết hợp tra cứu khe ngữ nghĩa (Slot-filling). Lưu câu trả lời vào `output/answer.txt`. Không cần API key.
2. `"option": "llm"` (Lựa chọn 2): Chia knowledge base thành chunks, tạo embeddings bằng `text-embedding-3-small`, lưu index FAISS local tại `models/faiss_index`, truy xuất (Retrieval) rồi đóng gói vào Grounded Prompt để sinh câu trả lời bằng `gpt-4o-mini`; output là `output/answer_llm.txt`. Option này cần đặt `OPENAI_API_KEY` trong file `.env`.

## Đánh giá hệ thống (Phần IV) & Hạn chế

- **Đánh giá hệ thống:** Chạy kiểm thử tự động trên bộ `data/evaluation/sample_queries.txt` (40 cases) bao gồm câu hợp lệ, paraphrase, câu ngoài phạm vi và câu thiếu dữ liệu. Hệ thống đạt độ chính xác 100% trên bộ test chuẩn và ~72% tỷ lệ khớp văn phạm trên toàn bộ corpus stress-test 731 câu. Chi tiết xem tại `output/evaluation.txt`.
- **Hạn chế của hệ thống:** Văn phạm CFG dựa trên luật tĩnh nên nhạy cảm với lỗi chính tả, teencode ("ntn", "đc ko"), và tiếng Việt không dấu. Hiện chưa hỗ trợ tốt các câu hỏi ghép nhiều thực thể phức tạp (ví dụ: "Tuần 3 và tuần 4 học gì?").

## Chạy bằng Docker

### Chuẩn bị

Cài Docker Desktop, khởi động Docker Engine, sau đó mở PowerShell tại chính
thư mục gốc của project (thư mục chứa `Dockerfile`). Docker build context phải
là thư mục này vì Dockerfile dùng
`requirements.txt`, `input/`, `data/` và source trong đó.

### Build image

```powershell
docker build -t course-assistant .
```

Lệnh này tạo image `course-assistant` từ `python:3.11-slim`, cài các package
trong `requirements.txt` và chép mã nguồn cùng dữ liệu vào image.

### Chạy chương trình

Để chạy một lần:

```powershell
docker run --rm course-assistant
```

Container dùng entry point `python -m course_assistant`. Chương trình đọc
`input/sentences.txt` và sinh các file kết quả trong `/app/output`. Tùy chọn
`--rm` tự xóa container sau khi chạy xong.

Mặc định `/app/output` chỉ tồn tại bên trong container. Để giữ kết quả trên máy
host, mount thư mục `output`:

```powershell
docker run --rm `
    -v "${PWD}\output:/app/output" `
    course-assistant
```

Sau khi chạy, kiểm tra các file xuất ra trên máy host trong thư mục `output/`.

### Chạy lại sau khi thay đổi mã nguồn

Image phải được build lại để nhận mã nguồn mới:

```powershell
docker build --no-cache -t course-assistant .
docker run --rm `
    -v "${PWD}\output:/app/output" `
    course-assistant
```

Lưu ý: Dockerfile có khai báo `/nlp/input` và `/nlp/output` để tương thích với
một số workflow mẫu, nhưng CLI hiện tại đọc cố định `input/sentences.txt` và
ghi vào `output/`. Vì vậy không cần mount `/nlp/input` khi chạy Group A.

## Kiểm tra output Expected

Các file trong `output/Expected/` là reference output và không được chỉnh sửa
để làm phép so sánh pass. Có thể kiểm tra số dòng và nội dung bằng PowerShell:

```powershell
$pairs = @(
    @("output/parse-results.txt", "output/Expected/parse-results.txt"),
    @("output/semantic.txt", "output/Expected/semantic.txt"),
    @("output/intent-entity.txt", "output/Expected/intent-entity.txt")
)

foreach ($pair in $pairs) {
    $actual = Get-Content $pair[0]
    $expected = Get-Content $pair[1]
    $same = $null -eq (Compare-Object $expected $actual)
    "{0}: actual={1}, expected={2}, match={3}" -f `
        $pair[0], $actual.Count, $expected.Count, $same
}
```

## Trạng thái hiện tại

- Toàn bộ các module cốt lõi của Group A và Group B đã hoàn thiện. Hệ thống tích hợp đầy đủ pipeline từ Grammar, Parser, Semantic Analysis, đến Retrieval, RAG và Đánh giá tự động.
- `input/sentences.txt` là corpus câu đơn thuộc miền dữ liệu mẫu của project.
- Dữ liệu trong `data/course/` là dữ liệu mẫu phục vụ bài tập. Một số lịch, deadline và quy định chỉ là dữ liệu mô phỏng; xem thêm `data/00_README.txt`.

## Ghi chú khi nộp riêng thư mục project

Chỉ cần nộp toàn bộ thư mục `project/`, bao gồm `src/`, `data/`, `input/`,
`output/`, `models/`, `README.md`, `Dockerfile`, `pyproject.toml` và
`requirements.txt`. Không cần nộp thư mục `.venv`, `__pycache__` hoặc image
Docker.