from celery import Celery
import os
from insta_scraper import ScrapeUser
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Celery('macmap_scraper')

app.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    worker_prefetch_multiplier=1,
    result_expires=1800,  
    task_acks_late=True,
    worker_max_tasks_per_child=100,
)

@app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def scrape_insta(self, username):
    logger.info(f"Starting scrape task for username: {username}")
    
    try:
        result = ScrapeUser(username)
        
        if result:
            return {
                "status": "success", 
                "username": username,
                "message": f"Successfully scraped {username}"
            }
        else:
            raise Exception(f"Scraper failed for {username}")
            
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.error(f"Max retries exceeded for {username}")
            return {
                "status": "failed", 
                "username": username,
                "error": str(exc),
                "retries": self.request.retries,
                "message": f"Failed after {self.max_retries} attempts"
            }
        else:
            logger.info(f"Retrying {username} (attempt {self.request.retries + 1})")
            raise exc