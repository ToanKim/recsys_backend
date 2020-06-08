FROM python:3.7
WORKDIR /project
ADD . /project
RUN pip install -r requirements.txt