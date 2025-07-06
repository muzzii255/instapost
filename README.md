# Instagram Scraper API

A FastAPI-based Instagram scraper with Celery task queue, SQLite storage, and AWS S3 media uploads.

## Features

- 🚀 **FastAPI** REST API with async task processing
- 📦 **Celery** task queue with Redis backend
- 🗄️ **SQLite** database for user and post data storage
- ☁️ **AWS S3** integration for media file storage
- 🔄 **Auto-retry** mechanism for failed requests
- 📊 **Task status tracking** and monitoring
- 🛡️ **Proxy support** for reliable scraping

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │───▶│  Celery Worker  │───▶│  Instagram API  │
│   (main.py)     │    │   (tasks.py)    │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Redis       │    │     SQLite      │    │     AWS S3      │
│  (Task Queue)   │    │   (Data Store)  │    │ (Media Storage) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Prerequisites

- Python 3.8+
- Redis server
- AWS S3 account (optional)
- Proxy service (optional but recommended)

## Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd instagram-scraper
```

2. **Install dependencies:**
```bash
pip install fastapi uvicorn celery redis pandas curl-cffi boto3 python-dotenv
```

3. **Create environment file (.env):**
```env
# Proxy Configuration (Optional)
PROXY_USERNAME=your_proxy_username
PROXY_PASSWORD=your_proxy_password
ENDPOINT=your_proxy_endpoint

# AWS S3 Configuration (Optional)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_bucket_name

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## Usage

### 1. Start Redis Server
```bash
redis-server
```

### 2. Start Celery Worker
```bash
celery -A tasks worker --loglevel=info --concurrency=2
```

### 3. Start FastAPI Application
```bash
gunicorn main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 300 \
  --max-requests 100 \
  --max-requests-jitter 20 \
  --access-logfile access.log \
  --error-logfile error.log
```

## API Endpoints

### 1. Scrape Instagram User
**POST** `/api/v1/scrape/username`

```bash
curl -X POST "http://localhost:8000/api/v1/scrape/username" \
  -H "Content-Type: application/json" \
  -d '{"username": "instagram_username"}'
```

**Response:**
```json
{
  "task_id": "abc123-def456-ghi789",
  "status": "queued",
  "message": "Userscraping task queued for instagram_username"
}
```

### 2. Check Task Status
**GET** `/api/v1/task/{task_id}`

```bash
curl "http://localhost:8000/api/v1/task/abc123-def456-ghi789"
```

**Response:**
```json
{
  "task_id": "abc123-def456-ghi789",
  "status": "SUCCESS",
  "result": {
    "status": "success",
    "username": "instagram_username"
  },
  "traceback": null,
  "date_done": "2025-01-02T15:30:00"
}
```

### 3. Get User Data
**POST** `/api/v1/get-user`

```bash
curl -X POST "http://localhost:8000/api/v1/get-user" \
  -H "Content-Type: application/json" \
  -d '{"username": "instagram_username"}'
```

**Response:**
```json
{
  "username": "instagram_username",
  "full_name": "Display Name",
  "biography": "User bio...",
  "followed_by": 1000,
  "follow": 500,
  "is_verified": false,
  "posts": [
    {
      "post_id": "abc123",
      "caption": "Post caption...",
      "taken_at_timestamp": 1672531200,
      "post_liked_by": 150,
      "img_file": "media/user_id_post_id.jpg",
      "video_file": null
    }
  ]
}
```

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    full_name TEXT,
    biography TEXT,
    external_url TEXT,
    followed_by INTEGER DEFAULT 0,
    follow INTEGER DEFAULT 0,
    is_verified BOOLEAN DEFAULT 0,
    is_private BOOLEAN DEFAULT 0,
    business_email TEXT,
    business_phone_number TEXT,
    category_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Posts Table
```sql
CREATE TABLE posts (
    post_id TEXT PRIMARY KEY,
    user_id TEXT,
    username TEXT,
    taken_at_timestamp INTEGER,
    is_video BOOLEAN DEFAULT 0,
    video_view_count INTEGER DEFAULT 0,
    liked_by INTEGER DEFAULT 0,
    caption TEXT,
    accessibility_caption TEXT,
    img_file TEXT,
    video_file TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
```

## File Structure

```
├── main.py              # FastAPI application
├── tasks.py             # Celery task definitions
├── insta_scraper.py     # Instagram scraping logic
├── db_utils.py          # Database utility functions
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables
├── instagram_data.db    # SQLite database (auto-created)
├── media/               # Downloaded media files (temp)
├── access.log           # Gunicorn access logs
└── error.log            # Gunicorn error logs
```

## Production Deployment

### Using Docker Compose
```yaml
version: '3.8'
services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  web:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - redis
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    command: gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

  worker:
    build: .
    depends_on:
      - redis
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    command: celery -A tasks worker --loglevel=info --concurrency=2
```

### Systemd Service
Create `/etc/systemd/system/instagram-scraper.service`:
```ini
[Unit]
Description=Instagram Scraper API
After=network.target

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/path/to/instagram-scraper
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --max-requests 100
Restart=always

[Install]
WantedBy=multi-user.target
```

## Monitoring & Maintenance

### Check Celery Tasks
```bash
# Monitor worker status
celery -A tasks inspect active

# Check task statistics
celery -A tasks inspect stats
```

### Database Maintenance
```python
from db_utils import export_to_csv

# Export data to CSV
export_to_csv('users', 'users_backup.csv')
export_to_csv('posts', 'posts_backup.csv')
```

### Logs
- **Application logs:** Check `error.log` and `access.log`
- **Celery logs:** Worker output shows task progress
- **Database:** SQLite file at `instagram_data.db`

## Rate Limiting & Best Practices

- **Worker concurrency:** Keep low (1-2) to avoid rate limits
- **Retry mechanism:** Built-in 3 retries with 60s delay
- **Worker restart:** Auto-restart after 100 requests to prevent memory issues
- **Proxy rotation:** Use rotating proxies for large-scale scraping

## Troubleshooting

### Common Issues

1. **Redis connection failed:**
   ```bash
   # Check Redis status
   redis-cli ping
   ```

2. **S3 upload errors:**
   - Verify AWS credentials
   - Check bucket permissions
   - Ensure bucket exists

3. **Instagram rate limiting:**
   - Use proxy servers
   - Reduce worker concurrency
   - Add delays between requests

4. **Database locked:**
   ```bash
   # Check for long-running transactions
   sqlite3 instagram_data.db ".timeout 30000"
   ```

## License

MIT License

## Contributing

1. Fork the repository
2. Create feature branch
3. Submit pull request

## Support

For issues and questions, please create a GitHub issue or contact the development team.
