#!/bin/bash
FOLDER_NAME=$1
OPERATION=$2
SERVICE_DIRECTORY="/home/redbull/$FOLDER_NAME"

if [ ! -d "$SERVICE_DIRECTORY" ]; then
    echo "Directory $SERVICE_DIRECTORY does not exist."
    exit 1
fi

# Trust the directory
git config --global --add safe.directory "$SERVICE_DIRECTORY"

cd $SERVICE_DIRECTORY

case $OPERATION in
    stop)
        sudo docker-compose stop
        ;;
    restart)
        sudo docker-compose restart
        ;;
    start)
        git pull origin master
        sudo docker-compose up -d
        ;;
    update)
        git pull origin master
        sudo docker-compose build
        sudo docker-compose rm -sf
        sudo docker-compose up -d
        ;;
    *)
        echo "Invalid operation: $OPERATION"
        exit 1
        ;;
esac
