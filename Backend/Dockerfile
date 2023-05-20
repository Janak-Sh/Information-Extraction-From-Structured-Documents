# Pull base image
FROM python:3.10.9
COPY requirements.py requirements.txt /
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y
RUN python requirements.py i