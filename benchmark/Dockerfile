FROM python:3.8-slim

RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -

RUN mkdir test
WORKDIR test
RUN /root/.poetry/bin/poetry new .

# This should work
RUN /root/.poetry/bin/poetry run true

RUN mkdir test/venv
RUN python -m venv venv

# This should fail
RUN /root/.poetry/bin/poetry run true
