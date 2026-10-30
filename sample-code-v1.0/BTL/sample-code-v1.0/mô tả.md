# Mô tả folder code mẫu

## 1. Tổng quan

Folder này chứa bộ khung bài tập NLP với hai cách triển khai mẫu: Python và Java. Ngoài ra, `util.sh` cung cấp các lệnh Docker để chạy thử hoặc đóng gói bài nộp.

Đây mới là **code khởi tạo**, chưa có thuật toán hay chức năng xử lý ngôn ngữ tự nhiên hoàn chỉnh:

- Bản Python hiện chỉ có hàm mẫu in `hello NLP`.
- Bản Java hiện chỉ in `Hello World!`.
- Chưa thấy thư mục dữ liệu `input/`, kết quả `output/` hay file yêu cầu bài tập trong folder này. Vì vậy, tài liệu mô tả đúng những gì có trong code mẫu, không suy đoán yêu cầu đầu ra của bài.

## 2. Cấu trúc thư mục

```text
sample-code-v1.0/
├── util.sh                         # Script Docker để test hoặc tạo file nộp
├── mô tả.md                        # Tài liệu mô tả folder này
├── python/
│   ├── Dockerfile                  # Cấu hình image chạy bản Python
│   ├── README.md                   # Hiện đang để trống
│   ├── requirements.txt            # Các thư viện Python được khai báo
│   ├── setup.py                    # Cấu hình đóng gói Python
│   ├── .gitignore                  # Các file/thư mục bỏ qua khi dùng Git
│   ├── conf/
│   │   └── app.json                # Khai báo hàm Python làm điểm gọi
│   └── hcmut/
│       └── iaslab/
│           ├── __init__.py         # File đánh dấu package, hiện để trống
│           └── nlp/
│               ├── __init__.py     # File đánh dấu package, hiện để trống
│               └── app/
│                   ├── __init__.py # File đánh dấu package, hiện để trống
│                   └── utils.py    # Hàm test(**kwargs) mẫu
└── java/
    ├── Dockerfile                  # Cấu hình image chạy bản Java
    └── nlp-assignment-222/
        ├── pom.xml                 # Cấu hình Maven và dependency
        └── src/
            ├── main/java/hcmut/iaslab/nlp/app/
            │   └── App.java        # Chương trình Java chính
            └── test/java/hcmut/iaslab/nlp/app/
                └── AppTest.java    # Kiểm thử JUnit mẫu
```

## 3. Folder `python/`

Đây là dự án Python theo cấu trúc package `hcmut.iaslab.nlp.app`.

- `hcmut/iaslab/nlp/app/utils.py`: định nghĩa `test(**kwargs)`, hiện chỉ in `hello NLP`; chưa đọc dữ liệu hoặc thực hiện xử lý NLP.
- `conf/app.json`: trỏ tới hàm `hcmut.iaslab.nlp.app.utils.test`. Dockerfile dùng file cấu hình này để gọi chương trình.
- `requirements.txt`: khai báo `openpyxl`, `xlrd`, `Click`, `deprecation`, `pandas`, `numpy`, `scipy`, `matplotlib` và `pyutils` cài từ Git. Đây là danh sách dependency của bộ khung; hàm mẫu hiện tại không trực tiếp sử dụng các thư viện đó.
- `setup.py`: cấu hình đóng gói bằng `setuptools`, tìm các package trong source và yêu cầu Python từ phiên bản 3.6. Tên package `NAME` và mô tả `DESC` vẫn là giá trị giữ chỗ.
- `README.md`: file hiện rỗng, chưa có hướng dẫn cài đặt hoặc sử dụng.
- `.gitignore`: bỏ qua cache Python, môi trường ảo, file build/đóng gói, dữ liệu kiểm thử và một số thư mục công cụ/thí nghiệm như `.idea`, `tmp`, `exps`, `wandb`.
- `Dockerfile`: tạo image nhiều giai đoạn dựa trên Python 3.8, cài `requirements.txt`, chép source vào `/src` và đặt lệnh khởi chạy mặc định là:

  ```bash
  python3 -m hcommon.cli run --json_conf conf/app.json
  ```

  `hcommon.cli` không nằm trong cây source của dự án. Lệnh này chỉ hoạt động nếu môi trường dependency/framework cung cấp module đó; nên kiểm tra lại với môi trường thầy cung cấp khi chạy thực tế. Dockerfile cũng mở cổng 5000, nhưng code mẫu hiện không khởi tạo web server.

## 4. Folder `java/`

Đây là dự án Maven có tên artifact `nlp-assignment-222`, phiên bản `1.0-SNAPSHOT`, package Java `hcmut.iaslab.nlp.app`.

- `nlp-assignment-222/pom.xml`: cấu hình Maven, UTF-8, mức biên dịch source/target Java 7. Dependency duy nhất được khai báo là JUnit 4.11 và chỉ dùng cho kiểm thử.
- `src/main/java/.../App.java`: điểm vào `main`; hiện chỉ in `Hello World!` ra màn hình.
- `src/test/java/.../AppTest.java`: kiểm thử mẫu dùng JUnit 4, hiện chỉ kiểm tra một giá trị `true`.
- `java/Dockerfile`: build bằng Maven 3.6.0/JDK 8, sau đó tạo image chạy bằng OpenJDK 8 JRE. Dockerfile mong build context là folder `java/` vì các lệnh `COPY` tham chiếu tới `nlp-assignment-222/`.

Có thể build và chạy trực tiếp nếu máy đã cài Maven/JDK tương thích:

```bash
cd java/nlp-assignment-222
mvn clean package
java -jar target/nlp-assignment-222-1.0-SNAPSHOT.jar
```

Hoặc build Docker từ folder `java/`:

```bash
cd java
docker build -t nlp-assignment-java .
docker run --rm nlp-assignment-java
```

## 5. Script `util.sh`

Script này viết cho Bash và cần Docker. Hai biến cấu hình ở đầu file là:

- `STUDENT_ID`: mã sinh viên; hiện vẫn là placeholder `student-id`.
- `PROJ_P_LANG`: ngôn ngữ dự án; hiện mặc định là `python`.

### Chạy thử

```bash
bash ./util.sh test
```

Script sẽ build Docker image từ folder được chỉ định trong `PROJ_P_LANG`, chạy container, mount `./input` vào `/nlp/input` và mount folder kết quả `./<STUDENT_ID>/output` vào `/nlp/output`. Script ghi chú rằng cần chuẩn bị `input/`; folder này hiện chưa có trong code mẫu. Cần thay `STUDENT_ID` bằng mã thật trước khi sử dụng.

### Tạo file nộp

```bash
bash ./util.sh submit
```

Lệnh này dùng image `thanhhungqb/images:zip-2023` để tạo `<STUDENT_ID>.zip` gồm `python`, `java` và `util.sh`. Cũng cần đặt đúng `STUDENT_ID` trước khi chạy.

## 6. Lưu ý trước khi phát triển hoặc chạy

1. Đọc file yêu cầu chính thức của bài tập để biết phải dùng Python hay Java, định dạng input/output, và phần nào cần nộp; các thông tin đó không có trong folder code mẫu hiện tại.
2. Điền mã sinh viên trong `util.sh`; kiểm tra lại `PROJ_P_LANG` nếu muốn script chạy nhánh Java.
3. Tạo và đặt dữ liệu đúng vị trí mà chương trình/yêu cầu quy định. `input/` và output thực tế chưa được cung cấp sẵn.
4. README Python đang trống; chưa có tài liệu hướng dẫn riêng cho bộ khung.
5. Các lệnh build/run ở trên được suy ra từ cấu hình Maven và Dockerfile. Chưa có xác nhận rằng toàn bộ dependency và lệnh khởi chạy Python hoạt động trong môi trường máy hiện tại.
