# Backup do banco para um bucket S3 compatível (Fase 52, OPS-01). Mesmo major do servidor:
# pg_dump mais velho que o Postgres recusa o dump.
FROM postgres:17-alpine
RUN apk add --no-cache aws-cli openssl
COPY backup.sh restore.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/restore.sh
USER postgres
ENTRYPOINT ["/usr/local/bin/backup.sh"]
CMD ["loop"]
