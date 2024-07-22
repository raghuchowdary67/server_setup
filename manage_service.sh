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

echo 'Before $(pwd)...'
# change directory
cd $SERVICE_DIRECTORY

echo 'After $(pwd)...'

#case $OPERATION in
#    stop)
#        docker-compose stop $FOLDER_NAME
#        ;;
#    restart)
#        docker-compose restart $FOLDER_NAME
#        ;;
#    start)
#        git pull origin master
#        docker-compose up -d $FOLDER_NAME
#        ;;
#    update)
#        git pull origin master
#        docker-compose build $FOLDER_NAME
#        docker-compose rm -sf $FOLDER_NAME
#        docker-compose up -d $FOLDER_NAME
#        ;;
#    *)
#        echo "Invalid operation: $OPERATION"
#        exit 1
#        ;;
#esac
