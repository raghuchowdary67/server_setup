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

echo "Before the PWD is : ${PWD}"
# change directory
cd $SERVICE_DIRECTORY

echo "After the PWD is : ${PWD}"

case $OPERATION in
    stop)
        nohup docker-compose stop $FOLDER_NAME > /dev/null 2>&1 &
        ;;
    restart)
        nohup docker-compose restart $FOLDER_NAME > /dev/null 2>&1 &
        ;;
    start)
        git pull origin master
        nohup docker-compose up -d $FOLDER_NAME > /dev/null 2>&1 &
        ;;
    update)
        git pull origin master
        docker-compose build $FOLDER_NAME &&
        docker-compose rm -sf $FOLDER_NAME &&
        docker-compose up -d $FOLDER_NAME
        ;;
    *)
        echo "Invalid operation: $OPERATION"
        exit 1
        ;;
esac
