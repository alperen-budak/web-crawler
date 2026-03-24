FROM python:3.11-alpine

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

COPY src/ ./src/
COPY tests/ ./tests/

RUN mkdir -p data && chown -R appuser:appgroup data/

USER appuser

EXPOSE 8080

ENV PORT=8080

CMD ["python", "src/api/server.py"]
