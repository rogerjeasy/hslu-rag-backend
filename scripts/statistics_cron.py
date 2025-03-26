#!/usr/bin/env python
"""
Cron job script to periodically calculate and update platform statistics.
This script should be configured to run at the desired interval using a task scheduler.

Example crontab entry (every hour):
0 * * * * /path/to/python /path/to/statistics_cron.py

You can also use a cloud service like AWS Lambda or Google Cloud Functions
with a scheduled trigger to run this script.
"""

import os
import sys
import logging
import asyncio
import requests
from datetime import datetime
import argparse
import json

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("statistics_cron.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("statistics_cron")

# Load configuration
def load_config():
    """Load configuration from file or environment variables"""
    config_path = os.environ.get("STATISTICS_CONFIG_PATH", "config/statistics_config.json")
    
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                return json.load(f)
        else:
            # Default config
            return {
                "api_base_url": os.environ.get("API_BASE_URL", "http://localhost:8000"),
                "admin_token": os.environ.get("ADMIN_TOKEN", ""),
                "auto_calculate_interval": int(os.environ.get("AUTO_CALCULATE_INTERVAL", "60")),
                "retention_period": int(os.environ.get("RETENTION_PERIOD", "90")),
                "tracked_metrics": {
                    "userGrowth": True,
                    "courseEnrollment": True,
                    "conversations": True,
                    "studyGuides": True,
                    "practiceQuestions": True,
                    "knowledgeGaps": True,
                    "sessionDuration": True,
                    "topicPopularity": True
                }
            }
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        raise


async def calculate_statistics():
    """Make API call to trigger statistics calculation"""
    config = load_config()
    api_url = f"{config['api_base_url']}/statistics/calculate"
    headers = {
        "Authorization": f"Bearer {config['admin_token']}",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"Starting statistics calculation at {datetime.now().isoformat()}")
        response = requests.post(api_url, headers=headers)
        
        if response.status_code == 200:
            logger.info("Statistics calculation completed successfully")
            return True
        else:
            logger.error(f"Error calculating statistics: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Exception during statistics calculation: {str(e)}")
        return False


async def clean_old_statistics():
    """Clean up old statistics data based on retention period"""
    config = load_config()
    api_url = f"{config['api_base_url']}/statistics/cleanup"
    headers = {
        "Authorization": f"Bearer {config['admin_token']}",
        "Content-Type": "application/json"
    }
    
    try:
        logger.info(f"Starting statistics cleanup at {datetime.now().isoformat()}")
        data = {"retention_days": config["retention_period"]}
        response = requests.post(api_url, headers=headers, json=data)
        
        if response.status_code == 200:
            logger.info(f"Statistics cleanup completed successfully. Retention period: {config['retention_period']} days")
            return True
        else:
            logger.error(f"Error cleaning statistics: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Exception during statistics cleanup: {str(e)}")
        return False


async def main(calculate=True, cleanup=False):
    """Main execution function"""
    try:
        if calculate:
            await calculate_statistics()
        
        if cleanup:
            await clean_old_statistics()
            
        logger.info("Statistics cron job completed")
    except Exception as e:
        logger.error(f"Unhandled exception in statistics cron job: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate and update platform statistics")
    parser.add_argument("--calculate", action="store_true", help="Calculate statistics")
    parser.add_argument("--cleanup", action="store_true", help="Clean up old statistics data")
    parser.add_argument("--config", help="Path to configuration file")
    
    args = parser.parse_args()
    
    # Set config path if provided
    if args.config:
        os.environ["STATISTICS_CONFIG_PATH"] = args.config
    
    # If no specific action is requested, do calculation by default
    if not args.calculate and not args.cleanup:
        args.calculate = True
    
    # Run the async main function
    asyncio.run(main(calculate=args.calculate, cleanup=args.cleanup))