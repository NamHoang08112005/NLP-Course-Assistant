# Course Assistant

## Current status

Đây là project Python cho bài tập lớn NLP Course Assistant. Project hiện chạy
được phần Group A:

```text
input/sentences.txt
        -> grammar -> parser -> semantic representation -> intent/entity
        -> output/
```

## Yêu cầu môi trường

- Python 3.11 trở lên. Python 3.11, 3.12, 3.13 và 3.14 đều có thể dùng.
- hoặc Docker Desktop nếu chạy bằng container.

Project hiện không dùng thư viện Python bên ngoài. File `requirements.txt` được
giữ lại để phục vụ cách cài đặt chuẩn và có thể bổ sung dependency khi mở rộng
RAG/LLM.

## Cấu trúc chính

```text
project/
├── data/
│   ├── course/                  # Knowledge base mẫu của môn học
│   ├── grammar/course_assistant.cfg
│   └── lexicon/entities.txt
├── input/
│   └── sentences.txt            # Mỗi dòng là một câu cần phân tích
├── output/
│   ├── Expected/                # Kết quả tham khảo, không sửa file này
│   └── ...                      # Kết quả được sinh khi chạy chương trình
├── src/course_assistant/
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

## Chạy trực tiếp bằng Python

Mở PowerShell tại thư mục `project`:

```powershell
cd E:\Year_4\NLP\Test\sample-code-v1.0\project
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
python -m course_assistant
```

Nếu PowerShell chặn activate script, có thể chạy không cần activate:

```powershell
cd E:\Year_4\NLP\Test\sample-code-v1.0\project
$env:PYTHONPATH = "src"
python -m course_assistant
```

Kiểm tra các phiên bản Python đã được cài trên Windows bằng:

```powershell
py --list
```

Chỉ chọn phiên bản từ **3.11 trở lên**. Ví dụ, nếu kết quả có `3.12` nhưng
không có `3.11`, dùng `py -3.12 -m venv .venv`.

## Chương trình thực hiện

### 1. Đọc các câu hỏi từ

```text
input/sentences.txt
```

- Mỗi dòng trong file là một câu hỏi hoặc yêu cầu.
- Chương trình xử lý lần lượt từng dòng.
- Các câu thuộc miền dữ liệu môn học được dùng làm input cho Group A.

### 2. Phân tích từng câu bằng

```text
Grammar -> Parser -> Semantic -> Intent/Entity
```

- **Grammar:** đọc văn phạm CFG trong `data/grammar/course_assistant.cfg`.
- **Parser:** kiểm tra câu có phù hợp với văn phạm và tạo cây cú pháp.
- **Semantic:** ánh xạ câu đã phân tích sang biểu diễn ngữ nghĩa.
- **Intent/Entity:** xác định ý định và các thực thể/thông tin liên quan.

### 3. Ghi kết quả vào thư mục

```text
output/
```

- `output/grammar.txt`: văn phạm được sử dụng.
- `output/samples.txt`: tối đa 10.000 câu được sinh từ CFG.
- `output/parse-results.txt`: cây cú pháp của từng câu.
- `output/semantic.txt`: biểu diễn ngữ nghĩa của từng câu.
- `output/intent-entity.txt`: intent và entity được nhận diện.

Chương trình không in các kết quả này ra terminal. Sau khi chạy xong, mở các
file trong thư mục `output/` để xem kết quả.

## Chạy bằng Docker

Docker build context phải là chính thư mục `project`, vì Dockerfile dùng các
file `requirements.txt` và source nằm trong thư mục này:

```powershell
cd E:\Year_4\NLP\Test\sample-code-v1.0\project
docker build -t course-assistant .
docker run --rm course-assistant
```

Container chạy cùng entry point `python -m course_assistant`. Kết quả được ghi
vào `/app/output` bên trong container và sẽ mất khi container bị xóa. Để lấy
kết quả về máy host, mount thư mục output:

```powershell
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

- Grammar, parser, sentence generator, semantic mapping và formatters của
    Group A đã được triển khai.
- `input/sentences.txt` là corpus câu đơn thuộc miền dữ liệu mẫu của project.
- Phần Group B/RAG và xử lý hội thoại là phần mở rộng riêng; `pipeline.py`
    hiện chưa phải entry point hoàn chỉnh cho toàn bộ Course Assistant.
- Dữ liệu trong `data/course/` là dữ liệu mẫu phục vụ bài tập. Một số lịch,
    deadline và quy định chỉ là dữ liệu mô phỏng; xem thêm `data/00_README.txt`.

## Ghi chú khi nộp riêng thư mục project

Chỉ cần nộp toàn bộ thư mục `project/`, bao gồm `src/`, `data/`, `input/`,
`output/`, `models/`, `README.md`, `Dockerfile`, `pyproject.toml` và
`requirements.txt`. Không cần nộp thư mục `.venv`, `__pycache__` hoặc image
Docker.
