#!/bin/bash

# Replace variables in init.template.sql
sed "s/\${MYSQL_DATABASE}/${MYSQL_DATABASE}/g; s/\${MYSQL_USER_DATABASE}/${MYSQL_USER_DATABASE}/g; s/\${MYSQL_USER}/${MYSQL_USER}/g" /docker-entrypoint-initdb.d/init.template.sql > /docker-entrypoint-initdb.d/init.sql

# Wait for MariaDB to be ready
until mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 1;" >/dev/null 2>&1; do
  echo "Waiting for database connection..."
  sleep 2
done

# Execute the SQL file using the default root user
mysql -u root -p"$MYSQL_ROOT_PASSWORD" < /docker-entrypoint-initdb.d/init.sql
