-- Create the secondary database if needed
CREATE DATABASE IF NOT EXISTS `${MARIADB_USER_DATABASE}`;

-- Grant privileges to the user on the secondary database
GRANT ALL PRIVILEGES ON `${MARIADB_USER_DATABASE}`.* TO '${MARIADB_USER}'@'%';

FLUSH PRIVILEGES;

-- Optional: Verify creation
SHOW DATABASES;
SHOW GRANTS FOR '${MARIADB_USER}'@'%';