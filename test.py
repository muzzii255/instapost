# import pymysql

# connection = pymysql.connect(
#     host='web01.itile.app',
#     port=3306,
#     user='tegelsnl_bart',
#     password='F33F3fKeFQGCLBqA4FVz',
#     database='tegelsnl_wp'
# )

import requests
req= requests.get("https://web01.itile.app/phpmyadmin")
print(req.status_code,req.url)