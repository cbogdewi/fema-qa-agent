# One image, two ways to run it:
#   AWS Lambda (default CMD -> Mangum handler)
#   Local/compose: override the entrypoint to run uvicorn (see docker-compose.yml)
FROM public.ecr.aws/lambda/python:3.12

# DuckDB writes nothing (read-only DB), but give it a writable home for any temp files.
ENV HOME=/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY app/ ${LAMBDA_TASK_ROOT}/app/
# Built by etl/load_openfema.py in CI; refreshed nightly.
COPY data/fema.duckdb ${LAMBDA_TASK_ROOT}/data/fema.duckdb
# Latest eval report, shown on the dashboard's quality panel (optional).
COPY evals/results/ ${LAMBDA_TASK_ROOT}/evals/results/

CMD ["app.main.handler"]
