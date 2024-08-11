#!/bin/bash
#chmod +x server_setup.sh

LOG_FILE="$HOME/setup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

# Function to generate random passwords
generate_random_password() {
  tr -dc A-Za-z0-9 </dev/urandom | head -c 8 ; echo ''
}

# Prompt the user for installation environment
while true; do
  echo "Where are you installing this:"
  echo "1. EC2 (AWS EC2 instance)"
  echo "2. Ubuntu (Local PC)"
  echo "3. Other (Optional for now)"
  read -r -p "Enter your choice (1, 2, 3): " ENV_CHOICE

  case $ENV_CHOICE in
    1)
      INSTANCE_TYPE="EC2"
      break
      ;;
    2)
      INSTANCE_TYPE="Ubuntu"
      break
      ;;
    3)
      read -r -p "Enter your custom environment type: " INSTANCE_TYPE
      break
      ;;
    *)
      echo "Please select a valid option."
      ;;
  esac
done

# Prompt the user for system type
while true; do
  echo "System Type:"
  echo "1. Main Server"
  echo "2. Load Balancer"
  echo "3. Tunnel/Proxy"
  read -r -p "Enter your choice (1, 2, 3): " SYS_CHOICE

  case $SYS_CHOICE in
    1)
      SYSTEM_TYPE="Main Server"
      break
      ;;
    2)
      SYSTEM_TYPE="Load Balancer"
      break
      ;;
    3)
      SYSTEM_TYPE="Tunnel/Proxy"
      break
      ;;
    *)
      echo "Please select a valid option."
      ;;
  esac
done

# Function to update and install packages using apt
install_apt_packages() {
  echo "Updating and installing necessary packages with apt..."
  sudo apt update
  sudo apt upgrade -y
  sudo apt install -y curl apt-transport-https ca-certificates software-properties-common gnupg-agent git
}

# Function to update and install packages using yum
install_yum_packages() {
  echo "Updating and installing necessary packages with yum..."
  sudo yum update -y
  sudo yum install -y curl yum-utils device-mapper-persistent-data lvm2 git
}

# Install necessary packages based on the instance type
if [ "$INSTANCE_TYPE" == "EC2" ]; then
  if ! rpm -q curl git &>/dev/null; then
    install_yum_packages
  else
    echo "Necessary packages are already installed."
  fi
else
  if ! dpkg -l curl git &>/dev/null; then
    install_apt_packages
  else
    echo "Necessary packages are already installed."
  fi
fi

# Common Docker installation steps
echo "Installing Docker..."
if [ "$INSTANCE_TYPE" == "EC2" ]; then
  if ! rpm -q docker &>/dev/null; then
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
  else
    echo "Docker is already installed."
  fi
else
  if ! command -v docker &> /dev/null; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
    sudo add-apt-repository \
       "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
       $(lsb_release -cs) \
       stable"
    sudo apt update
    sudo apt install -y docker-ce docker-ce-cli containerd.io
    sudo systemctl start docker
    sudo systemctl enable docker
  else
    echo "Docker is already installed."
  fi
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
  echo "Installing Docker Compose..."
  sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
  sudo chmod +x /usr/local/bin/docker-compose
else
  echo "Docker Compose is already installed."
fi

# Create secrets directory and the .env file
SECRETS_DIR="$HOME/secrets"
mkdir -p "$SECRETS_DIR"

# Get the public IP address
SYSTEM_IP4_IP=$(curl -s http://checkip.amazonaws.com)

# Write environment variables to the .env file
if [ ! -f "$SECRETS_DIR/.env" ]; then
  echo "Creating .env file with credentials..."
  cat <<EOL | sudo tee "$SECRETS_DIR"/.env > /dev/null
INSTANCE_TYPE=$INSTANCE_TYPE
SYSTEM_TYPE=$SYSTEM_TYPE
SYSTEM_IP4_IP=$SYSTEM_IP4_IP
EOL
else
  echo ".env file already exists. Skipping creation."
fi

if [ ! -f "$HOME/.ssh/id_rsa" ]; then
  while true; do
    read -r -p "Do you want to generate SSH keys? (y/n): " GENERATE_SSH
    case $GENERATE_SSH in
      [Yy]* )
        DEFAULT_EMAIL="your_email@example.com"
        read -r -p "Enter your email address for SSH key generation (default: $DEFAULT_EMAIL): " USER_EMAIL
        USER_EMAIL=${USER_EMAIL:-$DEFAULT_EMAIL}
        echo "Generating SSH keys..."
        ssh-keygen -t rsa -b 4096 -C "$USER_EMAIL" -f ~/.ssh/id_rsa -N ""
        echo "Your SSH public key (add this to your GitHub account):"
        cat ~/.ssh/id_rsa.pub
        echo "Setup complete. Please add the above SSH public key to your GitHub account and press Enter to continue."
        read -r -p "Press Enter to continue after adding the SSH key to GitHub..."
        break
        ;;
      [Nn]* )
        echo "Skipping SSH key generation."
        break
        ;;
      * )
        echo "Please answer yes or no."
        ;;
    esac
  done
else
  echo "SSH key already exists. Skipping generation."
fi

# Additional setup for Main Server
if [ "$SYSTEM_TYPE" == "Main Server" ]; then
  # Prompt the user for MYSQL_USER and MYSQL_PASSWORD
  if ! grep -q "MYSQL_USER=" "$SECRETS_DIR/.env"; then
    read -r -p "Enter MYSQL_USER (default: redbull_admin): " MYSQL_USER
    MYSQL_USER=${MYSQL_USER:-redbull_admin}

    read -r -p "Enter MYSQL_PASSWORD (leave blank for random): " MYSQL_PASSWORD
    if [ -z "$MYSQL_PASSWORD" ]; then
      MYSQL_PASSWORD=$(generate_random_password)
    fi

    # Prompt the user for MASTER_ADMIN_USER
    read -r -p "Enter MASTER_ADMIN_USER (default: RED1431): " MASTER_ADMIN_USER
    MASTER_ADMIN_USER=${MASTER_ADMIN_USER:-RED1431}

    # Prompt the user for MASTER_ADMIN_PASS
    read -r -p "Enter MASTER_ADMIN_PASS (default: redpass1431): " MASTER_ADMIN_PASS
    MASTER_ADMIN_PASS=${MASTER_ADMIN_PASS:-redbull_admin}

    # Generate random root password
    MYSQL_ROOT_PASSWORD=$(generate_random_password)

    # Create Docker volumes for MariaDB and Redis in /home partition
    echo "Creating Docker volumes for MariaDB and Redis..."
    mkdir -p "$HOME"/docker-volumes/mariadb
    mkdir -p "$HOME"/docker-volumes/redis

    # Append database credentials to the .env file
    cat <<EOL | sudo tee -a "$SECRETS_DIR"/.env > /dev/null
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD
MYSQL_DATABASE=rmovies_admin
MYSQL_USER=$MYSQL_USER
MYSQL_PASSWORD=$MYSQL_PASSWORD
MASTER_ADMIN_USER=$MASTER_ADMIN_USER
MASTER_ADMIN_PASS=$MASTER_ADMIN_PASS
EOL
  else
    echo "MySQL credentials already exist in .env file. Skipping."
  fi

  # Clone the flask_app from GitHub
  echo "Cloning Flask app from GitHub..."
  git clone https://github.com/raghuchowdary67/server_setup.git "$HOME"/server_setup

  # Start Docker Compose
  echo "Starting Docker Compose..."
  cd "$HOME"/server_setup || exit
  sudo docker-compose up -d

  # Display generated credentials
  echo "Setup is complete. Here are your generated credentials:"
  echo "MYSQL_USER: $MYSQL_USER"
  echo "MYSQL_PASSWORD: $MYSQL_PASSWORD"
  echo "MYSQL_ROOT_PASSWORD: $MYSQL_ROOT_PASSWORD"
  echo "MASTER_ADMIN_USER: $MASTER_ADMIN_USER"
  echo "MASTER_ADMIN_PASS: $MASTER_ADMIN_PASS"
  echo "Please store these credentials securely."
elif [ "$SYSTEM_TYPE" == "Load Balancer" ]; then
  echo "Load Balancer setup selected."
  # Add Load Balancer specific setup here
elif [ "$SYSTEM_TYPE" == "Tunnel/Proxy" ]; then
  echo "Tunnel/Proxy setup selected."
  # Add Tunnel/Proxy specific setup here
fi

# Determine instance type
if [ "$INSTANCE_TYPE" == "EC2" ]; then
  echo "Setting up for EC2 instance..."

  # Check if Python is installed
  if ! command -v python3 &> /dev/null; then
    sudo yum install python3 -y
    sudo yum install python3-pip -y
  else
    echo "Python is already installed."
  fi

  # Check if virtual environment exists
  if [ ! -d "$HOME/monitoring_env" ]; then
    python3 -m venv "$HOME/monitoring_env"
    source "$HOME/monitoring_env/bin/activate"
    pip3 install psutil boto3
  else
    echo "Virtual environment already exists."
    source "$HOME/monitoring_env/bin/activate"
  fi

  # Set the environment variable for EC2
  ENV_TYPE="ec2"

else
  echo "Setting up for regular Ubuntu server..."

  # Check if Python is installed
  if ! command -v python3 &> /dev/null; then
    sudo apt-get update
    sudo apt-get install python3 -y
    sudo apt-get install python3-venv -y
    sudo apt-get install python3-pip -y
  else
    echo "Python is already installed."
  fi

  # Check if virtual environment exists
  if [ ! -d "$HOME/monitoring_env" ]; then
    python3 -m venv "$HOME/monitoring_env"
    source "$HOME/monitoring_env/bin/activate"
    pip3 install psutil
  else
    echo "Virtual environment already exists."
    source "$HOME/monitoring_env/bin/activate"
  fi

  # Set the environment variable for non-EC2
  ENV_TYPE=""

fi

# Download the network monitor script from GitHub
echo "Downloading the network monitor script..."
GITHUB_URL="https://raw.githubusercontent.com/raghuchowdary67/server_setup/main/network_monitor.py"

# Destination path
DESTINATION_PATH="$HOME/network_monitor.py"

# Prompt the user before overwriting the script
if [ -f "$DESTINATION_PATH" ]; then
  read -r -p "The network monitor script already exists. Do you want to overwrite it? (y/n): " OVERWRITE_SCRIPT
  if [[ "$OVERWRITE_SCRIPT" =~ ^[Yy]$ ]]; then
    curl -o "$DESTINATION_PATH" "$GITHUB_URL"
    chmod +x "$DESTINATION_PATH"
  else
    echo "Skipping download of the network monitor script."
  fi
else
  curl -o "$DESTINATION_PATH" "$GITHUB_URL"
  chmod +x "$DESTINATION_PATH"
fi

# Create systemd service file
SERVICE_FILE="/etc/systemd/system/network_monitor.service"

# Check if the service file exists
if [ -f "$SERVICE_FILE" ]; then
  read -r -p "The network monitor service already exists. Do you want to restart it? (y/n): " RESTART_SERVICE
  if [[ "$RESTART_SERVICE" =~ ^[Yy]$ ]]; then
    sudo systemctl stop network_monitor.service
    sudo systemctl start network_monitor.service
    echo "Network Monitor service restarted."
  else
    echo "Skipping restart of the Network Monitor service."
  fi
else
  echo "Creating the Network Monitor service..."
  sudo bash -c "cat > $SERVICE_FILE" <<EOL
[Unit]
Description=Network Monitor
After=network.target

[Service]
ExecStart=$HOME/monitoring_env/bin/python3 $DESTINATION_PATH $ENV_TYPE
Restart=always
User=$(whoami)
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOL

  # Reload systemd, enable and start the service
  sudo systemctl daemon-reload
  sudo systemctl enable network_monitor.service
  sudo systemctl start network_monitor.service
  echo "Network Monitor setup complete and started."
fi
