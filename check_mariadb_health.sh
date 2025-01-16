#!/bin/bash
#chmod +x check_mariadb_health.sh
source ${HOME}/secrets/.env
mysqladmin ping -h localhost -u root -p$MARIADB_ROOT_PASSWORD