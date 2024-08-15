-- Create the primary database using the `MYSQL_DATABASE` variable
CREATE DATABASE IF NOT EXISTS `${MYSQL_DATABASE}`;

-- Create the secondary database using the `MYSQL_USER_DATABASE` variable
CREATE DATABASE IF NOT EXISTS `${MYSQL_USER_DATABASE}`;

-- Grant privileges to the user on the primary database
GRANT ALL PRIVILEGES ON `${MYSQL_DATABASE}`.* TO '${MYSQL_USER}'@'%';

-- Grant privileges to the user on the secondary database
GRANT ALL PRIVILEGES ON `${MYSQL_USER_DATABASE}`.* TO '${MYSQL_USER}'@'%';

-- Apply changes
FLUSH PRIVILEGES;

-- Optional: Verify creation
SHOW DATABASES;