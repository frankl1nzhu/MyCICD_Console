# 🚀 Secure Cloud CI/CD Manager

A comprehensive DevSecOps dashboard built with **Python (FastAPI)** and **Docker**. This tool automates the deployment of web applications to a production Virtual Machine, incorporating security best practices such as **OAuth2 authentication**, **SonarQube code analysis**, and **Automated Penetration Testing**.

---

## 📋 Project Overview

This project implements a complete CI/CD pipeline with the following stages:

1. **Secure Authentication**: GitHub OAuth2 Login.
2. **Source Control**: Clones code from GitHub repositories (Back & Front).
3. **Code Analysis**: Automated Static Application Security Testing (SAST) via **SonarQube**.
4. **Containerization**: Builds Docker images tailored to the system architecture.
5. **Deployment**: Deploys containers to a remote "Production" Virtual Machine via SSH.
6. **Penetration Testing**: Post-deployment security scanning using **Nmap** and **Nikto** (Red Team actions).

---

## ⚙️ Architecture & Prerequisites

### 1. Hardware/Architecture Support

This project is designed to be architecture-agnostic, but the setup of the Virtual Machine differs slightly depending on your host machine.

| Host Machine            | Virtualization Tool         | Required Guest OS             | Docker Image Arch |
| :---------------------- | :-------------------------- | :---------------------------- | :---------------- |
| **Apple Silicon** | **UTM** (Recommended) | **Ubuntu Server ARM64** | `linux/arm64`   |
| **Intel/AMD**     | **VirtualBox**        | **Ubuntu Server AMD64** | `linux/amd64`   |

### 2. Required Software

* **Local Machine**:
  * Python 3.9+
  * Git
* **Virtual Machine (Production Server)**:
  * Ubuntu 20.04 or 22.04 LTS
  * Docker Engine
  * OpenSSH Server
  * Nmap & Nikto (for PenTest)

---

## 🛠️ Infrastructure Setup

### Step 1: Set up the Virtual Machine (The "Prod" Server)

1. **Install the OS**:

   * **Apple M-Series Users**: Download [Ubuntu Server ARM64](https://ubuntu.com/download/server/arm) and run it using **UTM**.
   * **Intel/AMD Users**: Download [Ubuntu Server AMD64](https://ubuntu.com/download/server) and run it using **VirtualBox**.
2. **Configure the VM**:
   SSH into your VM and install the required dependencies:

   ```bash
   sudo apt update
   sudo apt install -y docker.io openssh-server nmap nikto

   # Add your user to the docker group (to run docker without sudo)
   sudo usermod -aG docker $USER
   newgrp docker
   ```
3. **Prepare SonarQube on VM**:
   SonarQube requires specific memory settings. Run these commands on the VM:

   ```bash
   # Increase memory map limit
   sudo sysctl -w vm.max_map_count=262144

   # Run SonarQube container
   docker run -d --name sonarqube -p 9000:9000 sonarqube:community
   ```
4. **Get SonarQube Token**:

   * Open `http://<VM_IP>:9000` in your browser (Default login: `admin`/`admin`).
   * Create a Project (e.g., `Backend-Service`).
   * Generate a **Project Token**. Save this token; you will need it for the `.env` file.

---

## 💻 Local Application Setup

### Step 1: Clone and Install

Clone this repository to your local machine:

```bash
git clone https://github.com/frankl1nzhu/MyCICD_Console.git
cd MyCICD_Console

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn paramiko httpx python-dotenv jinja2
```

### Step 2: Configure GitHub OAuth

1. Go to **GitHub Settings** -> **Developer Settings** -> **OAuth Apps** -> **New OAuth App**.
2. **Homepage URL**: `http://localhost:8000`
3. **Authorization callback URL**: `http://localhost:8000/auth/callback`
4. Generate a **Client Secret**. Copy the Client ID and Secret.

### Step 3: Environment Configuration

Create a `.env` file in the root directory:

```ini
# --- GitHub OAuth Configuration ---
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret

# --- Production VM Connection ---
VM_HOST=192.168.64.x      # Your VM IP Address
VM_USER=ubuntu            # VM Username
VM_PASSWORD=your_password # VM Password

# --- Target Repositories ---
REPO_URL_BACKEND=https://github.com/frankl1nzhu/Tuto-Web-service.git
REPO_URL_FRONTEND=https://github.com/frankl1nzhu/Tp_docker_front.git

# --- SonarQube Configuration ---
# If running SonarQube on the same VM
SONAR_TOKEN=sqp_xxxxxxxxxxxxxxxxxxxxxxxxxx
SONAR_PROJECT_KEY=backend-key
```

---

## 🚀 Usage Guide

1. **Start the CI/CD Console**:

   ```bash
   uvicorn main:app --reload
   ```
2. **Access the Dashboard**:
   Open **http://localhost:8000** in your browser.
3. **Login**:
   Click **"Login with GitHub"**. You must be authenticated to trigger deployments.
4. **Trigger Deployment**:

   * Click **"Deploy Backend"** or **"Deploy Frontend"**.
   * Watch the **Real-time Log Window**.

### Pipeline Stages Explained:

* **[GIT]**: The system connects to the VM via SSH and clones the fresh code.
* **[SONAR]**: A temporary Maven container is spun up to analyze the code quality and send the report to your SonarQube server.
* **[DOCKER]**:
  * **ARM64 Hosts**: Builds `linux/arm64` images natively.
  * **x86 Hosts**: Builds `linux/amd64` images natively.
* **[DEPLOY]**: Stops the old container and starts the new one with correct port mappings.
* **[PENTEST]** *(Bonus)*:
  * **Nmap**: Scans the exposed ports to ensure firewall rules are working.
  * **Nikto**: Scans the running Web Application for common vulnerabilities (XSS, headers, etc.).

---

## 🧪 Troubleshooting

**1. "Connection Refused" during SSH:**

* Ensure the VM is running.
* Check if you can ping the VM from your local machine.
* Ensure `openssh-server` is installed on the VM.

**2. Docker Permission Denied on VM:**

* Did you run `sudo usermod -aG docker ubuntu`? You might need to restart the VM after this command.

**3. SonarQube Analysis Fails:**

* Ensure the SonarQube container is running (`docker ps`).
* Check if the `SONAR_TOKEN` in `.env` is correct.

**4. Wrong Architecture (Exec format error):**

* If you built the image on an M-series Mac but are trying to run it on an Intel VM (or vice versa), the container will fail.
* **Solution**: Ensure your Local Machine architecture matches your VM architecture (ARM to ARM, or x86 to x86).
