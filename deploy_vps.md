# Professional VPS Deployment Guide

This guide explains how to deploy the Google Ads Pipeline on a VPS using Docker. This ensures a consistent environment and easy management.

## Prerequisites

1.  **A VPS**: (e.g., DigitalOcean, Hetzner, AWS, etc.) running Ubuntu 22.04+ or similar.
2.  **Docker & Docker Compose**: Installed on the VPS.
    - [Install Docker](https://docs.docker.com/engine/install/ubuntu/)
    - [Install Docker Compose](https://docs.docker.com/compose/install/)

## Step 1: Prepare the VPS

SSH into your VPS and create a directory for the project:

```bash
mkdir -p ~/apps/google-ads-pipeline
cd ~/apps/google-ads-pipeline
```

## Step 2: Clone or Copy Files

Clone the repository if it's on GitHub, or SCP the files to the VPS.

```bash
git clone <your-repo-url> .
```

## Step 3: Configure Environment Variables

Create a `.env` file from the example:

```bash
cp .env.example .env
nano .env
```

Fill in your Google Ads API credentials:
- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_REFRESH_TOKEN`
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID`

## Step 4: Configure Campaigns (Optional)

If you only want to manage specific campaigns, create `campaigns.yaml`:

```bash
cp campaigns.yaml.example campaigns.yaml
nano campaigns.yaml
```

## Step 5: Deploy with Docker Compose

Build and start the container:

```bash
docker compose up -d --build
```

The pipeline is now running both the **REST API** and the **Automatic Scheduler**.

## API Documentation & Usage

The pipeline now exposes a professional REST API on port `3215`.

### Interactive API Docs
Once deployed, you can access the interactive Swagger documentation at:
**`http://your-vps-ip:3215/docs`**

### Common API Commands

| Task | Endpoint | Mode |
| :--- | :--- | :--- |
| **Check Health** | `GET /health` | Check account connectivity |
| **All Account Campaigns** | `GET /account/campaigns` | See what you can add |
| **Monitored Campaigns** | `GET /campaigns` | List active pipeline campaigns |
| **Run Monitor** | `POST /monitor?days=1` | Trigger a report |
| **Run Optimizer** | `POST /optimize?dry_run=true` | Preview changes |
| **Apply Changes** | `POST /optimize?dry_run=false` | Apply weekly optimizations |
| **Add Campaign** | `POST /campaigns?name=XXX` | Start managing (Opt-In) |
| **Remove Campaign**| `DELETE /campaigns/XXX` | Stop managing |
| **View Logs** | `GET /logs` | List recent results |

> [!IMPORTANT]
> **Opt-In Mode**: By default, **NO** campaigns are monitored at the start. You must use the `POST /campaigns` endpoint to add the specific campaign names you want the AI to handle.

Example: Trigger a manual monitor run from your terminal:
```bash
curl -X POST "http://localhost:3215/monitor?days=7"
```

## Useful Commands

### Check logs
```bash
# View live API output
docker compose logs -f
```

### Automatic Scheduling
The API handles scheduling internally:
- **Daily Monitor**: Every day at 08:00.
- **Weekly Optimization**: Every Monday at 09:00.

## Professional Maintenance Tips
...

1.  **Security**: Ensure your `.env` file is NOT committed to version control.
2.  **Backup**: Periodically backup your `logs/` directory if you need historical data.
3.  **Updates**: To update the code, pull the latest changes and run `docker compose up -d --build` again.
