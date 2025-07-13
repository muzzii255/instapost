import pandas as pd
import sqlite3
import datetime


db_path = "instagram_data.db"
def init_database():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
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
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
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
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scraping_status (
            username TEXT PRIMARY KEY,
            status TEXT DEFAULT 'pending',
            last_scraped TIMESTAMP,
            posts_count INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

def insert_user(user_data):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO users
        (id, username, full_name, biography, external_url, followed_by, follow,
            is_verified, is_private, business_email, business_phone_number, category_name, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (
        user_data.get('id'),
        user_data.get('username'),
        user_data.get('full_name'),
        user_data.get('biography'),
        user_data.get('external_url'),
        user_data.get('followed_by', 0),
        user_data.get('follow', 0),
        user_data.get('is_verified', False),
        user_data.get('is_private', False),
        user_data.get('business_email'),
        user_data.get('business_phone_number'),
        user_data.get('category_name')
    ))

    conn.commit()
    conn.close()

def insert_post(post_data):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO posts
        (post_id, user_id, username, taken_at_timestamp, is_video, video_view_count,
            liked_by, caption, accessibility_caption, img_file, video_file)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        post_data.get('post_id'),
        post_data.get('id'),
        post_data.get('username'),
        post_data.get('taken_at_timestamp'),
        post_data.get('is_video', False),
        post_data.get('video_view_count', 0),
        post_data.get('liked_by', 0),
        post_data.get('caption'),
        post_data.get('accessibility_caption'),
        post_data.get('img_file'),
        post_data.get('video_file')
    ))

    conn.commit()
    conn.close()

def update_scraping_status( username, status, posts_count=0, error_message=None):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO scraping_status
        (username, status, last_scraped, posts_count, error_message, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, CURRENT_TIMESTAMP)
    ''', (username, status, posts_count, error_message))

    conn.commit()
    conn.close()

def get_user_stats(self):
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM posts')
    posts_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM scraping_status WHERE status = "completed"')
    completed_count = cursor.fetchone()[0]

    conn.close()
    return {
        'total_users': users_count,
        'total_posts': posts_count,
        'completed_users': completed_count
    }


def export_to_csv(table_name, output_file=None):
    if not output_file:
        output_file = f"{table_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    df.to_csv(output_file, index=False)
    conn.close()

    return output_file


def get_user_by_username(username):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

def get_all_posts(username):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT post_id FROM posts WHERE username = ?", (username,))
    post_rows = cursor.fetchall()
    data = [dict(x)['post_id'] for x  in post_rows]
    conn.close()
    return data


def get_user_with_posts(username):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user_row = cursor.fetchone()

    if not user_row:
        conn.close()
        return None

    user = dict(user_row)

    cursor.execute("""SELECT * FROM posts WHERE username = ?
        ORDER BY scraped_at DESC
        LIMIT 20""", (username,))
    post_rows = cursor.fetchall()
    user['posts'] = [dict(row) for row in post_rows]

    conn.close()
    return user
