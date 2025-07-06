from db_utils import *
import logging
import os
import json
from datetime import datetime
from pathlib import Path
import pandas as pd
import requests as media_req
from curl_cffi import requests
from dotenv import load_dotenv
import boto3

load_dotenv()
init_database()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

proxy_config = {
    'username': os.getenv("PROXY_USERNAME"),
    'password': os.getenv("PROXY_PASSWORD"),
    'endpoint': os.getenv("ENDPOINT"),
}
proxy = {
    'http': f'http://{proxy_config["username"]}:{proxy_config["password"]}@{proxy_config["endpoint"]}',
    'https': f'http://{proxy_config["username"]}:{proxy_config["password"]}@{proxy_config["endpoint"]}'
}
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
    'X-IG-App-ID': '936619743392459',
    'X-Requested-With': 'XMLHttpRequest',
    'X-ASBD-ID': '129477',
    'Referer': 'https://www.instagram.com/',
    'Origin': 'https://www.instagram.com'
}

s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)
s3_bucket = os.getenv("S3_BUCKET_NAME")

if not s3_bucket:
    logger.error("S3_BUCKET_NAME environment variable is not set")
    exit(1)

os.makedirs("media", exist_ok=True)
os.makedirs("data", exist_ok=True)

export_header_written = False


def SendRequests(url):
    retry = 0
    while retry < 20:
        try:
            response = requests.get(url, headers=headers, proxies=proxy, timeout=30, impersonate="chrome131")
            if response.status_code == 200:
                return response
        except Exception as e:
            print(e)
        retry += 1
        

def DownloadMedia(url, filename):
    retry = 0
    while retry < 20:
        try:
            response = media_req.get(url, stream=True, proxies=proxy, timeout=300)
            if response.status_code == 200:
                filepath = Path(filename)
                filepath.parent.mkdir(parents=True, exist_ok=True)        
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                s3_client.upload_file(str(filepath), s3_bucket, filepath.name)
                os.remove(filename)
                return True
            retry += 1
        except Exception as e:
            print(e)
    return False


def ScrapeUser(username):
    logger.info(f"Processing user: {username}")
    
    profile_url = f'https://www.instagram.com/api/v1/users/web_profile_info/?username={username}'
    response = SendRequests(profile_url)
    if response == None:
        logger.error(f"Failed to fetch profile for {username}")
        return False
        
    user_data = response.json()['data']['user']
    posts = user_data.get('edge_owner_to_timeline_media', {}).get('edges', [])
    logger.info(f"Found {len(posts)} posts for {username}")
    
    business_address = {}
    if user_data.get('business_address_json'):
        business_address = json.loads(user_data['business_address_json'])
    
    user_data = {
        'username': username,
        'biography': user_data.get('biography', ''),
        'eimu_id': user_data.get('eimu_id', ''),
        'bio_links': ','.join([link.get('url', '') for link in user_data.get('bio_links', [])]),
        'external_url': user_data.get('external_url', ''),
        'followed_by': user_data.get('edge_followed_by', {}).get('count', 0),
        'fbid': user_data.get('fbid', ''),
        'follow': user_data.get('edge_follow', {}).get('count', 0),
        'full_name': user_data.get('full_name', ''),
        'id': user_data.get('id', ''),
        'business_email': user_data.get('business_email', ''),
        'business_phone_number': user_data.get('business_phone_number', ''),
        'category_name': user_data.get('category_name', ''),
        'is_verified': user_data.get('is_verified', False),
        'is_private': user_data.get('is_private', False),
        'city_name': business_address.get('city_name', ''),
        'latitude': business_address.get('latitude', ''),
        'longitude': business_address.get('longitude', ''),
        'street_address': business_address.get('street_address', ''),
        'zip_code': business_address.get('zip_code', '')
    }
    
    insert_user(user_data)
    
    for i, post in enumerate(posts):
        post_node = post.get('node', {})
        post_id = post_node.get('id', '')
        
        video_filename = None
        image_filename = None
        
        if post_node.get('is_video') and post_node.get('video_url'):
            video_filename = f'media/{user_data["id"]}_{post_id}.mp4'
            if DownloadMedia(post_node['video_url'], video_filename):
                logger.info(f"Video downloaded: {post_id}")
        
        if post_node.get('display_url'):
            image_filename = f'media/{user_data["id"]}_{post_id}.jpg'
            if DownloadMedia(post_node['display_url'], image_filename):
                logger.info(f"Image downloaded: {post_id}")
            
        caption_edges = post.get('node', {}).get('edge_media_to_caption', {}).get('edges', [])
        caption = ''
        for edge in caption_edges:
            caption += edge.get('node', {}).get('text', '')
        
        post_data = {
            'post_id': post_id,
            'video_view_count': post_node.get('video_view_count', 0),
            'taken_at_timestamp': post_node.get('taken_at_timestamp', 0),
            'post_liked_by': post_node.get('edge_liked_by', {}).get('count', 0),
            'post_preview_like': post_node.get('edge_media_preview_like', {}).get('count', 0),
            'img_file': image_filename,
            'video_file': video_filename,
            'accessibility_caption': post_node.get('accessibility_caption', ''),
            'caption': caption,
            'scraped_at': datetime.now().isoformat()
        }
        insert_post(post_data)
        
    logger.info(f"Completed {username}: {len(posts)} posts processed")
    return True




