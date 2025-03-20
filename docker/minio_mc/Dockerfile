FROM minio/mc

COPY ./commands/setup_minio.sh /commands/setup_minio.sh

RUN chmod +x /commands/setup_minio.sh

ENTRYPOINT ["/bin/sh", "-c", "/commands/setup_minio.sh"]
