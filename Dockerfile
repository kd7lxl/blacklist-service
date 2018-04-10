FROM python:2
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY blacklist-longpoll-server.py .
HEALTHCHECK CMD curl --head --fail http://localhost:1234/ || exit 1
CMD [ "python", "./blacklist-longpoll-server.py" ]
