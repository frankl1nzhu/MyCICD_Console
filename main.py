import os
import time
import paramiko
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
VM_HOST = os.getenv("VM_HOST")
VM_USER = os.getenv("VM_USER")
VM_PASSWORD = os.getenv("VM_PASSWORD")
REPO_BACKEND = os.getenv("REPO_URL_BACKEND")
REPO_FRONTEND = os.getenv("REPO_URL_FRONTEND")
SONAR_HOST_URL = f"http://{VM_HOST}:9000"
SONAR_TOKEN = "sqp_e12660436bef7e9e0382fb4d56abe9e5e78bcacb"
SONAR_PROJECT_KEY = "backend-key"

sessions = {}
deploy_logs = []


def ssh_exec_command(command):
    """Helper function to connect to VM and execute commands"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(VM_HOST, username=VM_USER,
                       password=VM_PASSWORD, timeout=10)
        stdin, stdout, stderr = client.exec_command(command)

        # Get output in real-time
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()

        client.close()
        return out, err
    except Exception as e:
        return "", str(e)


def run_pipeline_task(repo_url, app_name, port):
    """
    Background task to execute the deployment pipeline
    Steps: Clean -> Clone -> Build -> Stop Old -> Run New
    """
    global deploy_logs
    deploy_logs.clear()  # Clear old logs

    def log(step, message):
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] [{step}] {message}"
        print(entry)
        deploy_logs.append(entry)

    log("INIT", f"Starting deployment of {app_name} to {VM_HOST}...")

    # Define a series of Shell commands
    # 1. Prepare working directory
    log("SSH", "Creating working directory...")
    _, err = ssh_exec_command("mkdir -p ~/cicd_workspace")
    if err:
        log("ERROR", err)

    # 2. Clean up old code
    log("GIT", "Cleaning up old code...")
    folder_name = repo_url.split("/")[-1].replace(".git", "")
    ssh_exec_command(f"rm -rf ~/cicd_workspace/{folder_name}")

    # 3. Pull code
    log("GIT", f"Cloning code: {repo_url}")
    out, err = ssh_exec_command(f"cd ~/cicd_workspace && git clone {repo_url}")
    if err and "Cloning into" not in err:  # git clone output is usually in stderr
        log("ERROR", err)

    # === SonarQube Analysis (Backend only) ===
    if "backend" in app_name:
        log("SONAR", "Starting code quality analysis...")
        sonar_cmd = (
            f"docker run --rm --network host "
            f"-v ~/cicd_workspace/{folder_name}:/usr/src/app "
            f"-w /usr/src/app "
            f"maven:3.9-eclipse-temurin-17 "
            f"mvn clean verify sonar:sonar "
            f"-Dsonar.projectKey={SONAR_PROJECT_KEY} "
            f"-Dsonar.host.url={SONAR_HOST_URL} "
            f"-Dsonar.login={SONAR_TOKEN}"
        )
        out, err = ssh_exec_command(sonar_cmd)

        if "ANALYSIS SUCCESSFUL" in out:
            log("SONAR", "✅ Code analysis passed!")
        else:
            log("SONAR", "⚠️ Analysis complete, please check SonarQube dashboard.")

    # 4. Docker Build
    log("DOCKER", "Starting image build (may take a few minutes)...")
    build_cmd = f"cd ~/cicd_workspace/{folder_name} && docker build -t {app_name}:latest ."
    out, err = ssh_exec_command(build_cmd)
    # Docker build output is verbose, simple check here
    if "Successfully tagged" in out or "writing image" in out:
        log("DOCKER", "Build successful!")
    else:
        log("DOCKER_LOG", out)
        if err:
            log("DOCKER_ERR", err)

    # 5. Stop and remove old container
    log("DEPLOY", "Stopping old container...")
    ssh_exec_command(f"docker stop {app_name} || true")
    ssh_exec_command(f"docker rm {app_name} || true")

    # 6. Start new container
    log("DEPLOY", "Starting new container...")
    port_mapping = port if ":" in port else f"{port}:{port}"
    run_cmd = f"docker run -d -p {port_mapping} --name {app_name} {app_name}:latest"
    out, err = ssh_exec_command(run_cmd)

    if err:
        log("ERROR", f"Start failed: {err}")
    else:
        log("SUCCESS", f"Deployment complete! Container ID: {out}")
        log("INFO", f"Please visit: http://{VM_HOST}:{port}")

        # === PenTest ===
        log("SECURITY", "🕵️‍♂️ Starting Penetration Testing (Red Team Actions)...")

        # 1. Nmap Port Scan
        log("PENTEST", "Running Nmap port scan...")
        nmap_cmd = f"nmap -p {port.split(':')[0]} -sV localhost"
        out, _ = ssh_exec_command(nmap_cmd)
        log("PENTEST_RESULT", f"\n{out}")

        # 2. Nikto Web Vulnerability Scan (HTTP services only)
        log("PENTEST", "Running Nikto vulnerability scan (60s limit)...")
        nikto_cmd = f"nikto -h http://localhost:{port.split(':')[0]} -Tuning b -maxtime 60s"
        out, _ = ssh_exec_command(nikto_cmd)

        # Nikto output is long, capturing summary only
        if "0 error(s)" in out:
            log("PENTEST_RESULT", "✅ Nikto scan complete: No serious errors found.")
        else:
            log("PENTEST_RESULT",
                "⚠️ Nikto scan complete, please check server logs for detailed report.")

        log("INFO",
            f"All processes finished! Please visit: http://{VM_HOST}:{port.split(':')[0]}")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    user = None
    token = request.cookies.get("session_token")
    if token and token in sessions:
        user = sessions[token]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "logs": deploy_logs
    })

# ... OAuth Login/Callback/Logout code ...


@app.get("/login")
async def login():
    return RedirectResponse(f"https://github.com/login/oauth/authorize?client_id={CLIENT_ID}&scope=user:email")


@app.get("/auth/callback")
async def auth_callback(code: str):
    async with httpx.AsyncClient() as client:
        response = await client.post("https://github.com/login/oauth/access_token", headers={"Accept": "application/json"}, data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": code})
        access_token = response.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=400)
        user_resp = await client.get("https://api.github.com/user", headers={"Authorization": f"token {access_token}"})
        sessions[access_token] = user_resp.json().get("login")
        resp = RedirectResponse("/")
        resp.set_cookie(key="session_token", value=access_token)
        return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/")
    resp.delete_cookie("session_token")
    return resp
# ... OAuth End ...


@app.post("/deploy/backend")
async def deploy_backend(background_tasks: BackgroundTasks, request: Request):
    # Authentication
    token = request.cookies.get("session_token")
    if not token or token not in sessions:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Run Pipeline using background tasks to avoid blocking the browser
    background_tasks.add_task(
        run_pipeline_task, REPO_BACKEND, "backend-app", "8080")

    return {"message": "Deployment started", "status": "running"}


@app.post("/deploy/frontend")
async def deploy_frontend(background_tasks: BackgroundTasks, request: Request):
    # Authentication
    token = request.cookies.get("session_token")
    if not token or token not in sessions:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Start frontend deployment task
    # Note port: frontend container exposes 80 internally, we map it to host 3000
    background_tasks.add_task(
        run_pipeline_task, REPO_FRONTEND, "frontend-app", "3000:80")

    return {"message": "Frontend deployment started", "status": "running"}


@app.get("/logs")
async def get_logs():
    return {"logs": deploy_logs}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
