#!/bin/bash
# chmod +x init.sh
# Change ownership of the init directory to the current running user
chown -R $(id -u):$(id -g) /docker-entrypoint-initdb.d

source ${HOME}/secrets/.env

# Print the environment variables for debugging
echo "MYSQL_DATABASE: ${MYSQL_DATABASE}"
echo "MYSQL_USER_DATABASE: ${MYSQL_USER_DATABASE}"
echo "MYSQL_USER: ${MYSQL_USER}"

# Substitute environment variables in the SQL file
sed "s|\${MYSQL_DATABASE}|${MYSQL_DATABASE}|g; s|\${MYSQL_USER_DATABASE}|${MYSQL_USER_DATABASE}|g; s|\${MYSQL_USER}|${MYSQL_USER}|g" \
/docker-entrypoint-initdb.d/init-template.sql > /tmp/init-substituted.sql

# Move the substituted file back to the init directory
mv /tmp/init-substituted.sql /docker-entrypoint-initdb.d/init.sql

# Start MariaDB
exec /usr/local/bin/docker-entrypoint.sh mysqld
