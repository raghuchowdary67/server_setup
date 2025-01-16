#!/bin/bash
# chmod +x init.sh

# Debugging: Print current user and group
echo "Current user: $(id -u)"
echo "Current group: $(id -g)"
echo "Current user info: $(id)"

# Debugging: Check permissions of the target directory
ls -ld /docker-entrypoint-initdb.d
ls -l /docker-entrypoint-initdb.d

## Adjust ownership and permissions of the directory
#chown -R $(id -u):$(id -g) /docker-entrypoint-initdb.d || {
#    echo "Failed to change ownership of /docker-entrypoint-initdb.d. Check permissions.";
#    exit 1;
#}
#chmod -R u+w /docker-entrypoint-initdb.d || {
#    echo "Failed to set write permissions on /docker-entrypoint-initdb.d. Check permissions.";
#    exit 1;
#}

# Debugging: Check permissions of the target directory
ls -ld /docker-entrypoint-initdb.d
ls -l /docker-entrypoint-initdb.d

# Substitute environment variables in the SQL file
sed "s|\${MYSQL_DATABASE}|${MYSQL_DATABASE}|g; s|\${MYSQL_USER_DATABASE}|${MYSQL_USER_DATABASE}|g; s|\${MYSQL_USER}|${MYSQL_USER}|g" \
/docker-entrypoint-initdb.d/init-template.sql > /tmp/init-substituted.sql

# Use cp instead of mv to handle permission issues
cp /tmp/init-substituted.sql /docker-entrypoint-initdb.d/init-substituted.sql || {
    echo "Failed to copy substituted file. Check permissions.";
    exit 1;
}

# Confirm the file was created
ls -l /docker-entrypoint-initdb.d/

## Start MariaDB
#exec /usr/local/bin/docker-entrypoint.sh mysqld
# Start MariaDB
exec /usr/sbin/mysqld