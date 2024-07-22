#!/bin/bash

# Function to generate random passwords
generate_random_password() {
  tr -dc A-Za-z0-9 </dev/urandom | head -c 8 ; echo ''
}

# Prompt the user for MYSQL_USER and MYSQL_PASSWORD
read -p "Enter MYSQL_USER (default: redbull_admin): " MYSQL_USER
MYSQL_USER=${MYSQL_USER:-redbull_admin}

read -p "Enter MYSQL_PASSWORD (leave blank for random): " MYSQL_PASSWORD
if [ -z "$MYSQL_PASSWORD" ]; then
  MYSQL_PASSWORD=$(generate_random_password)
fi

# Prompt the user for MASTER_ADMIN_USER
read -p "Enter MASTER_ADMIN_USER (default: RED1431): " MASTER_ADMIN_USER
MASTER_ADMIN_USER=${MASTER_ADMIN_USER:-RED1431}

# Prompt the user for MASTER_ADMIN_PASS
read -p "Enter MASTER_ADMIN_PASS (default: redpass1431): " MASTER_ADMIN_PASS
MASTER_ADMIN_PASS=${MASTER_ADMIN_PASS:-redbull_admin}

# Generate random root password
MYSQL_ROOT_PASSWORD=$(generate_random_password)

# Prompt the user for email address for SSH key generation
DEFAULT_EMAIL="your_email@example.com"
read -p "Enter your email address for SSH key generation (default: $DEFAULT_EMAIL): " USER_EMAIL
USER_EMAIL=${USER_EMAIL:-$DEFAULT_EMAIL}

# Update and install necessary packages
echo "Updating and installing necessary packages..."
sudo apt update
sudo apt upgrade -y
sudo apt install -y curl apt-transport-https ca-certificates software-properties-common gnupg-agent git

# Install Docker
echo "Installing Docker..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
   $(lsb_release -cs) \
   stable"
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# Enable Docker service to start on boot
echo "Enabling Docker service to start on boot..."
sudo systemctl enable docker

# Install Docker Compose
echo "Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create Docker volumes for MariaDB and Redis in /home partition
echo "Creating Docker volumes for MariaDB and Redis..."
sudo mkdir -p /home/docker-volumes/mariadb
sudo mkdir -p /home/docker-volumes/redis

# Create secrets directory and the .env file
SECRETS_DIR="/home/secrets"
sudo mkdir -p $SECRETS_DIR

# Write environment variables to the .env file
echo "Creating .env file with credentials..."
cat <<EOL | sudo tee $SECRETS_DIR/.env > /dev/null
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD
MYSQL_DATABASE=rmovies_admin
MYSQL_USER=$MYSQL_USER
MYSQL_PASSWORD=$MYSQL_PASSWORD
MASTER_ADMIN_USER=$MASTER_ADMIN_USER
MASTER_ADMIN_PASS=$MASTER_ADMIN_PASS
EOL

# Clone the flask_app from GitHub
echo "Cloning Flask app from GitHub..."
git clone https://github.com/raghuchowdary67/server_setup.git /home/redbull/server_setup

# Generate SSH keys
echo "Generating SSH keys..."
ssh-keygen -t rsa -b 4096 -C "$USER_EMAIL" -f ~/.ssh/id_rsa -N ""

# Print SSH public key
echo "Your SSH public key (add this to your GitHub account):"
cat ~/.ssh/id_rsa.pub

echo "Setup complete. Please add the above SSH public key to your GitHub account and press Enter to continue."
read -p "Press Enter to continue after adding the SSH key to GitHub..."

# Start Docker Compose
echo "Starting Docker Compose..."
cd /home/redbull/server_setup
sudo docker-compose up -d

# Display generated credentials
echo "Setup is complete. Here are your generated credentials:"
echo "MYSQL_USER: $MYSQL_USER"
echo "MYSQL_PASSWORD: $MYSQL_PASSWORD"
echo "MYSQL_ROOT_PASSWORD: $MYSQL_ROOT_PASSWORD"
echo "MASTER_ADMIN_USER: $MASTER_ADMIN_USER"
echo "MASTER_ADMIN_PASS: $MASTER_ADMIN_PASS"
echo "Please store these credentials securely."
