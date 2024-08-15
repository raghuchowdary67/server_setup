#!/bin/bash
#chmod +x server_setup.sh

LOG_FILE="$HOME/setup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

# Function to generate random passwords
generate_random_password() {
  tr -dc A-Za-z0-9 </dev/urandom | head -c 8 ; echo ''
}

# Get the current logged-in user
CURRENT_USER=$(whoami)

# Prompt the user for installation environment
while true; do
  echo "Where are you installing this:"
  echo "1. EC2 Amazon AMI"
  echo "2. EC2 Ubuntu"
  echo "3. Ubuntu (Local PC)"
  echo "4. Other (Optional for now)"
  read -r -p "Enter your choice (1, 2, 3, 4): " ENV_CHOICE

  case $ENV_CHOICE in
    1)
      INSTANCE_TYPE="EC2_AMI"
      break
      ;;
    2)
      INSTANCE_TYPE="EC2_UBUNTU"
      break
      ;;
    3)
      INSTANCE_TYPE="Ubuntu"
      break
      ;;
    4)
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
if [ "$INSTANCE_TYPE" == "EC2_AMI" ]; then
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
if [ "$INSTANCE_TYPE" == "EC2_AMI" ]; then
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

# Add the current user to the Docker group
if ! groups "$CURRENT_USER" | grep -q '\bdocker\b'; then
  echo "Adding $CURRENT_USER to the Docker group..."
  sudo usermod -aG docker "$CURRENT_USER"
  echo "You need to log out and back in for the changes to take effect."
else
  echo "$CURRENT_USER is already in the Docker group."
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
  echo "Installing Docker Compose..."
  sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
  sudo chmod +x /usr/local/bin/docker-compose
else
  echo "Docker Compose is already installed."
fi

# Define network name
NETWORK_NAME="server_setup_internal-net"

# Check if the network exists
if ! docker network ls --filter name=${NETWORK_NAME} -q | grep -q .; then
    echo "Network '${NETWORK_NAME}' does not exist. Creating it..."
    docker network create --driver bridge ${NETWORK_NAME}
else
    echo "Network '${NETWORK_NAME}' already exists."
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

# Function to set up Docker volumes
setup_docker_volumes() {
  echo "Creating Docker volumes for MariaDB and Redis..."

  # Define volume directories
  local mariadb_volume_dir="$HOME/docker-volumes/mariadb"
  local redis_volume_dir="$HOME/docker-volumes/redis"

  # Create directories if they do not exist
  if [ ! -d "$mariadb_volume_dir" ]; then
    echo "Creating directory for MariaDB volume: $mariadb_volume_dir"
    mkdir -p "$mariadb_volume_dir"
  else
    echo "Directory for MariaDB volume already exists: $mariadb_volume_dir"
  fi

  if [ ! -d "$redis_volume_dir" ]; then
    echo "Creating directory for Redis volume: $redis_volume_dir"
    mkdir -p "$redis_volume_dir"
  else
    echo "Directory for Redis volume already exists: $redis_volume_dir"
  fi
}

# Function to append database credentials to the .env file
append_db_credentials() {
  cat <<EOL | sudo tee -a "$SECRETS_DIR"/.env > /dev/null
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD
MYSQL_DATABASE=rmovies_admin
MYSQL_USER_DATABASE=rmovies_users
MYSQL_USER=$MYSQL_USER
MYSQL_PASSWORD=$MYSQL_PASSWORD
MASTER_ADMIN_USER=$MASTER_ADMIN_USER
MASTER_ADMIN_PASS=$MASTER_ADMIN_PASS
EOL
}

# Function to set up Python environment
setup_python_env() {
  local env_type=$1

  if [ "$env_type" == "EC2_AMI" ]; then
    echo "Python installing for EC2_AMI"
    if ! command -v python3 &> /dev/null; then
      sudo yum install python3 -y
      sudo yum install python3-pip -y
    else
      echo "Python is already installed."
    fi
  else
    echo "Python installing for $env_type"
    if ! command -v python3 &> /dev/null; then
      sudo apt-get update
      sudo apt-get install python3 -y
      sudo apt-get install python3-venv -y
      sudo apt-get install python3-pip -y
      # Install cloud-utils only if env_type contains EC2_
      if [[ "$env_type" == EC2_* ]]; then
        sudo apt-get install cloud-utils
      fi
    else
      echo "Python is already installed."
    fi
  fi

  if [ ! -d "$HOME/server_setup/monitoring_env" ]; then
    python3 -m venv "$HOME/server_setup/monitoring_env"
    source "$HOME/server_setup/monitoring_env/bin/activate"
    # Install psutil
    pip3 install psutil

    # Install boto3 only if env_type contains EC2_
    if [[ "$env_type" == EC2_* ]]; then
      pip3 install boto3
    fi
  else
    echo "Virtual environment already exists."
    source "$HOME/server_setup/monitoring_env/bin/activate"
  fi
}

# Function to download or use the network monitor script
clone_server_setup() {
  # Clone the flask_app from GitHub
  echo "Cloning server_setup app from GitHub..."
  if [ -d "$HOME/server_setup/.git" ]; then
    echo "Repository already exists. Pulling latest changes..."
    git -C "$HOME/server_setup" fetch --all
    git -C "$HOME/server_setup" reset --hard origin/main
  else
    echo "Repo doesn't exists so Cloning server_setup from GitHub..."
    git clone https://github.com/raghuchowdary67/server_setup.git "$HOME/server_setup"
  fi

  DESTINATION_PATH="$HOME/server_setup/network_monitor.py"

  chmod +x "$DESTINATION_PATH"
}

# Function to set up the network monitor service
setup_network_monitor_service() {
  SERVICE_FILE="/etc/systemd/system/network_monitor.service"

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
ExecStart=$HOME/server_setup/monitoring_env/bin/python3 $DESTINATION_PATH $INSTANCE_TYPE
Restart=always
User=$(whoami)
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOL

    sudo systemctl daemon-reload
    sudo systemctl enable network_monitor.service
    sudo systemctl start network_monitor.service
    echo "Network Monitor setup complete and started."
  fi
}

# Additional setup for Main Server
if [ "$SYSTEM_TYPE" == "Main Server" ]; then
  if ! grep -q "MYSQL_USER=" "$SECRETS_DIR/.env"; then
    read -r -p "Enter MYSQL_USER (default: redbull_admin): " MYSQL_USER
    MYSQL_USER=${MYSQL_USER:-redbull_admin}

    read -r -p "Enter MYSQL_PASSWORD (leave blank for random): " MYSQL_PASSWORD
    MYSQL_PASSWORD=${MYSQL_PASSWORD:-$(generate_random_password)}

    read -r -p "Enter MASTER_ADMIN_USER (default: RED1431): " MASTER_ADMIN_USER
    MASTER_ADMIN_USER=${MASTER_ADMIN_USER:-RED1431}

    read -r -p "Enter MASTER_ADMIN_PASS (default: redpass1431): " MASTER_ADMIN_PASS
    MASTER_ADMIN_PASS=${MASTER_ADMIN_PASS:-redpass1431}

    MYSQL_ROOT_PASSWORD=$(generate_random_password)

    append_db_credentials
  else
    echo "MySQL credentials already exist in .env file. Skipping."
  fi

  clone_server_setup
  setup_docker_volumes

  cd "$HOME"/server_setup || exit
  echo "Setting Venv and starting network usage script..."

  setup_python_env "$INSTANCE_TYPE"
  # Start Docker Compose
  echo "Starting Docker Compose..."
  docker compose up -d

  # Clean up old Docker images
  echo "Cleaning up old Docker images..."
  docker image prune -f

elif [ "$SYSTEM_TYPE" == "Load Balancer" ] || [ "$SYSTEM_TYPE" == "Tunnel/Proxy" ]; then
  clone_server_setup
  setup_python_env "$INSTANCE_TYPE"

  read -r -p "Do you want to include Redis? (yes/no): " include_redis
    if [ "$include_redis" == "yes" ]; then
      echo "Running server_setup and Redis..."
      docker-compose up -d server_setup redis
    else
      echo "Running server_setup only..."
      docker-compose up -d server_setup
    fi

  # Clean up old Docker images
  echo "Cleaning up old Docker images..."
  docker image prune -f
fi

setup_network_monitor_service
echo "Setup is complete."