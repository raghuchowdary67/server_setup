#!/bin/bash
# chmod +x init.sh

# Debugging: Print current user and group
echo "Current user: $(id -u)"
echo "Current group: $(id -g)"
echo "Current user info: $(id)"

# Debugging: Check permissions of the target directory
ls -ld /docker-entrypoint-initdb.d
ls -l /docker-entrypoint-initdb.
# Debugging: Check permissions of the database directory
ls -ld /var/lib/mysql
ls -l /var/lib/mysql

# Change ownership of the mounted directories and files
chown -R mysql:mysql /docker-entrypoint-initdb.d /var/lib/mysql /home

# Debugging: Check permissions of the target directory
ls -ld /docker-entrypoint-initdb.d
ls -l /docker-entrypoint-initdb.d
# Debugging: Check permissions of the database directory
ls -ld /var/lib/mysql
ls -l /var/lib/mysql

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