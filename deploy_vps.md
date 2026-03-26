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

Build and start the container in detached mode:

```bash
docker compose up -d --build
```

The pipeline is now running! It will:
- Run `monitor.py` every 24 hours.
- Run `optimize.py` every 7 days (as configured in `entrypoint.sh`).
- Log everything to the `./logs` directory on your VPS.

## Useful Commands

### Check logs
```bash
# View live output from the container
docker compose logs -f

# View persistent logs on the host
tail -f logs/monitor.log
tail -f logs/optimize.log
```

### Run a script manually inside the container
```bash
# Run a daily monitor manually
docker compose exec google-ads-pipeline python3 monitor.py

# Run a weekly optimizer manually (dry-run)
docker compose exec google-ads-pipeline python3 optimize.py --dry-run
```

### Restart the pipeline
```bash
docker compose restart
```

### Stop the pipeline
```bash
docker compose down
```

## Professional Maintenance Tips

1.  **Security**: Ensure your `.env` file is NOT committed to version control.
2.  **Backup**: Periodically backup your `logs/` directory if you need historical data.
3.  **Updates**: To update the code, pull the latest changes and run `docker compose up -d --build` again.
