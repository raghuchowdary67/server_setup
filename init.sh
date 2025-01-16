#!/bin/bash
# chmod +x init.sh

# Change ownership of the init directory
#chown -R $(id -u):$(id -g) /docker-entrypoint-initdb.d

# Substitute environment variables in the SQL file
sed "s|\${MYSQL_DATABASE}|${MYSQL_DATABASE}|g; s|\${MYSQL_USER_DATABASE}|${MYSQL_USER_DATABASE}|g; s|\${MYSQL_USER}|${MYSQL_USER}|g" \
/docker-entrypoint-initdb.d/init-template.sql > /tmp/init-substituted.sql

# Move the substituted file to the init directory
mv /tmp/init-substituted.sql /docker-entrypoint-initdb.d/init-substituted.sql || {
    echo "Failed to move substituted file. Check permissions.";
    exit 1;
}

# Confirm the file was created
ls -l /docker-entrypoint-initdb.d/

## Start MariaDB
#exec /usr/local/bin/docker-entrypoint.sh mysqld
# Start MariaDB
exec /usr/sbin/mysqld