FROM debian:buster-slim

RUN apt-get update

RUN apt-get -y install \
		software-properties-common \
		ca-certificates \
		gnupg \
		curl \
		git-core \
&& true

ENV PATH=/miniconda/bin:${PATH}

ARG CONDA_VER=latest
ARG OS_TYPE=x86_64
RUN \
	curl -L "http://repo.continuum.io/miniconda/Miniconda3-${CONDA_VER}-Linux-${OS_TYPE}.sh" > Miniconda3.sh && \
	bash Miniconda3.sh -p /miniconda -b && \
	rm Miniconda3.sh && \
	conda update -y conda && \
	conda init && \
	conda install mamba -n base -c conda-forge && \
	conda run pip install poetry pipenv && \
true

COPY . /app
WORKDIR /app
RUN conda run poetry install
