from celery import Celery
import os
from insta_scraper import ScrapeUser

app = Celery('macmap_scraper')

app.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=100,
)


@app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def scrape_insta(self, username):
    try:
        ScrapeUser(username)
        return {"status": "success", "username":username}
    except Exception as exc:
        raise self.retry(exc=exc)

