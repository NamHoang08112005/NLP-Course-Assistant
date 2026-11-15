FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV COURSE_ASSISTANT_INPUT_DIR=/nlp/input
ENV COURSE_ASSISTANT_OUTPUT_DIR=/nlp/output

WORKDIR /app
RUN mkdir -p /nlp/input /nlp/output /app/output

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "course_assistant"]
