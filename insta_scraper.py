import logging
import os
import json
from datetime import datetime
from urllib.parse import quote
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import pandas as pd
from curl_cffi import requests
from dotenv import load_dotenv
load_dotenv()


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    simple_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    logger = logging.getLogger('instagram_scraper')
    logger.setLevel(logging.DEBUG)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    file_handler = logging.FileHandler(f'logs/scraper_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    error_handler = logging.FileHandler(f'logs/errors_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    
    return logger



class InstagramScraper:
    def __init__(self):
        self.logger = setup_logging()
        self.session = requests.Session()
        
        self.proxy_config = {
            'username': os.getenv("PROXY_USERNAME"),
            'password': os.getenv("PROXY_PASSWORD"),
            'endpoint': os.getenv("ENDPOINT"),
        }
        
        self.proxy = {
            'http': f'http://{self.proxy_config["username"]}:{self.proxy_config["password"]}@{self.proxy_config["endpoint"]}',
            'https': f'http://{self.proxy_config["username"]}:{self.proxy_config["password"]}@{self.proxy_config["endpoint"]}'
        }
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-IG-App-ID': '936619743392459',
            'X-Requested-With': 'XMLHttpRequest',
            'X-ASBD-ID': '129477',
            'Referer': 'https://www.instagram.com/',
            'Origin': 'https://www.instagram.com'
        }
         
        os.makedirs("media", exist_ok=True)
        os.makedirs("data", exist_ok=True)
        
        self.export_header_written = False
        self.max_retries = 10
        
        self.logger.info("Instagram scraper initialized successfully")
        self.logger.info(f"Using proxy endpoint: {self.proxy_config['endpoint']}")



    def send_request(self, url: str, stream: bool = False, timeout: int = 30) -> Optional[requests.Response]:
        self.logger.debug(f"Sending request to: {url}")
        
        for attempt in range(self.max_retries):
            try:
                if stream:
                    response = self.session.get(
                        url, 
                        stream=True, 
                        proxies=self.proxy, 
                        timeout=timeout,
                        headers=self.headers
                    )
                else:
                    response = self.session.get(
                        url,
                        headers=self.headers,
                        proxies=self.proxy,
                        timeout=timeout,
                        impersonate="chrome131"
                    )
                
                self.logger.debug(f"Response: {response.status_code} for {url}")
                
                if response.status_code == 200:
                    self.logger.info(f"Successfully fetched: {url}")
                    return response
                elif response.status_code == 429:
                    self.logger.warning(f"Rate limited (429) for {url}, attempt {attempt + 1}")
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    self.logger.warning(f"HTTP {response.status_code} for {url}, attempt {attempt + 1}")
                    
            except requests.exceptions.Timeout:
                self.logger.error(f"Timeout error for {url}, attempt {attempt + 1}")
            except requests.exceptions.ConnectionError as e:
                self.logger.error(f"Connection error for {url}, attempt {attempt + 1}: {str(e)}")
            except Exception as e:
                self.logger.error(f"Unexpected error for {url}, attempt {attempt + 1}: {str(e)}")
            
            if attempt < self.max_retries - 1:
                self.logger.info(f"Retrying ...")
        
        self.logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
        return None


    def download_media(self, url: str, filename: str) -> bool:
        try:
            self.logger.info(f"Downloading media: {filename}")
            response = self.send_request(url, stream=True)
            
            if response and response.status_code == 200:
                filepath = Path(filename)
                filepath.parent.mkdir(parents=True, exist_ok=True)
                
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(filepath)
                self.logger.info(f"Successfully downloaded {filename} ({file_size} bytes)")
                return True
            else:
                self.logger.error(f"Failed to download {filename}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error downloading {filename}: {str(e)}")
            return False


    def extract_caption(self, post_data: Dict[str, Any]) -> str:
        try:
            caption_edges = post_data.get('node', {}).get('edge_media_to_caption', {}).get('edges', [])
            caption = ''
            for edge in caption_edges:
                caption += edge.get('node', {}).get('text', '')
            return caption
        except Exception as e:
            self.logger.error(f"Error extracting caption: {str(e)}")
            return ''


    def export_data(self, data: Dict[str, Any], filename: str = "instadata.csv") -> bool:
        try:
            filepath = Path("data") / filename
            df = pd.DataFrame([data])
            
            if not self.export_header_written:
                df.to_csv(filepath, index=False, mode='w')
                self.export_header_written = True
                self.logger.info(f"Created new CSV file: {filepath}")
            else:
                df.to_csv(filepath, index=False, mode='a', header=False)
                self.logger.debug(f"Appended data to: {filepath}")
            
            return True
        except Exception as e:
            self.logger.error(f"Error exporting data to {filename}: {str(e)}")
            return False


    def parse_business_address(self, business_address_json: str) -> Dict[str, Any]:
        try:
            if business_address_json:
                return json.loads(business_address_json)
            return {}
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing business address JSON: {str(e)}")
            return {}
        except Exception as e:
            self.logger.error(f"Unexpected error parsing business address: {str(e)}")
            return {}


    def scrape_user_posts(self, username: str) -> bool:
        self.logger.info(f"Starting to scrape user: {username}")
        
        try:
            profile_url = f'https://www.instagram.com/api/v1/users/web_profile_info/?username={username}'
            response = self.send_request(profile_url)
            
            if not response:
                self.logger.error(f"Failed to fetch profile for user: {username}")
                return False
            
            try:
                user_data = response.json()['data']['user']
                self.logger.info(f"Successfully fetched profile for {username}")
                self.logger.info(f"User has {len(user_data.get('edge_owner_to_timeline_media', {}).get('edges', []))} posts")
            except (KeyError, json.JSONDecodeError) as e:
                self.logger.error(f"Error parsing profile response for {username}: {str(e)}")
                return False
            
            business_address = self.parse_business_address(user_data.get('business_address_json', ''))
            
            posts = user_data.get('edge_owner_to_timeline_media', {}).get('edges', [])
            successful_posts = 0
            
            for i, post in enumerate(posts):
                self.logger.info(f"Processing post {i + 1}/{len(posts)} for user {username}")
                
                try:
                    post_node = post.get('node', {})
                    post_id = post_node.get('id', '')
                    
                    video_filename = None
                    image_filename = None
                    
                    if post_node.get('is_video') and post_node.get('video_url'):
                        video_filename = f'media/{user_data["id"]}_{post_id}.mp4'
                        if self.download_media(post_node['video_url'], video_filename):
                            self.logger.info(f"Downloaded video: {video_filename}")
                        else:
                            video_filename = None
                    
                    if post_node.get('display_url'):
                        image_filename = f'media/{user_data["id"]}_{post_id}.jpg'
                        if self.download_media(post_node['display_url'], image_filename):
                            self.logger.info(f"Downloaded image: {image_filename}")
                        else:
                            image_filename = None
                    
                    data = {
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
                        'zip_code': business_address.get('zip_code', ''),
                        'post_id': post_id,
                        'video_view_count': post_node.get('video_view_count', 0),
                        'taken_at_timestamp': post_node.get('taken_at_timestamp', 0),
                        'post_liked_by': post_node.get('edge_liked_by', {}).get('count', 0),
                        'post_preview_like': post_node.get('edge_media_preview_like', {}).get('count', 0),
                        'img_file': image_filename,
                        'video_file': video_filename,
                        'accessibility_caption': post_node.get('accessibility_caption', ''),
                        'caption': self.extract_caption(post),
                        'scraped_at': datetime.now().isoformat()
                    }
                    
                    if self.export_data(data):
                        successful_posts += 1
                        self.logger.info(f"Successfully processed post {post_id}")
                    else:
                        self.logger.error(f"Failed to export data for post {post_id}")
                    
                    
                except Exception as e:
                    self.logger.error(f"Error processing post {i + 1} for user {username}: {str(e)}")
                    continue
            
            self.logger.info(f"Completed scraping user {username}: {successful_posts}/{len(posts)} posts processed successfully")
            return successful_posts > 0
            
        except Exception as e:
            self.logger.error(f"Unexpected error scraping user {username}: {str(e)}")
            return False


    def scrape_multiple_users(self, usernames: List[str]) -> Dict[str, bool]:
        results = {}
        
        for username in usernames:
            self.logger.info(f"Starting scrape for user: {username}")
            try:
                results[username] = self.scrape_user_posts(username)
            except Exception as e:
                self.logger.error(f"Error scraping user {username}: {str(e)}")
                results[username] = False
        
        return results



def main():
    scraper = InstagramScraper()
    
    usernames = ['sanimax.nl'] 
    
    scraper.logger.info("Starting Instagram scraping session")
    results = scraper.scrape_multiple_users(usernames)
    
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    
    scraper.logger.info(f"Scraping session completed: {successful}/{total} users processed successfully")
    
    for username, success in results.items():
        status = "SUCCESS" if success else "FAILED"
        scraper.logger.info(f"User {username}: {status}")



if __name__ == "__main__":
    main()