#!/bin/bash
# chmod +x init.sh

# Substitute environment variables into the SQL file
envsubst < /docker-entrypoint-initdb.d/init-template.sql > /docker-entrypoint-initdb.d/init-substituted.sql

# Run the MariaDB entrypoint
exec /usr/local/bin/docker-entrypoint.sh mariadbd