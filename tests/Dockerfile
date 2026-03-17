FROM python:3.12

WORKDIR /tests

COPY requirements.txt /tests/requirements.txt
RUN pip install --no-cache-dir -r /tests/requirements.txt

COPY test_services.py /tests/test_services.py

ENTRYPOINT ["python", "/tests/test_services.py"]
