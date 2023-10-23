import os
import json
import httpx
import csv
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging

# Load .env file
load_dotenv()

post_fields = {
    'date' : datetime,
    'date_gmt' : datetime,
    'title' : str,
    'content' : str,
    'excerpt' : str,
    'categories' : list,
    'tags' : list,
    'featured_media' : int,
    'status' : str,
    'slug' : str,
    'format' : str,
    'sticky' : bool,
    'template' : str,
    'meta' : dict,
    'author' : int,
    'password' : str,
    'type' : str,
    'comment_status' : str,
    'ping_status' : str,
    'generated_slug' : str,
    'link' : str,
    'guid' : str,
    'modified' : datetime,
    'modified_gmt' : datetime,
    'yoast_meta' : dict,
}

# Access your API keys and token
wp_username = os.getenv('WP_USERNAME')
wp_password = os.getenv('WP_PASSWORD')
wp_token = os.getenv('WP_TOKEN')

# Get the JWT token for WordPress
def get_jwt_token(username, password):

    if wp_token:
        logging.info("Using existing token")
        return wp_token
    
    token_endpoint = "http://cybernow.info/wp-json/jwt-auth/v1/token"
    payload = {
        'username': username,
        'password': password
    }
    response = httpx.post(token_endpoint, data=payload)
    if response.status_code == 200:
        token = response.json().get('token')  # Get token directly from JSON response
        #logging.info(f"Received token: {token}")
        return token
    else:
        logging.info(f"Failed to get JWT token: {response.text}")
        raise Exception(f"Failed to get JWT token: {response.text}")
    
token = get_jwt_token(wp_username, wp_password)

def get_wp_id_from_slug(slug):

    endpoint = f"https://cybernow.info/wp-json/wp/v2/posts?slug={slug}"
    headers = {'Authorization': f'Bearer {token}'}
    # Make a GET request to the WordPress REST API endpoint for posts
    response = httpx.get(endpoint, headers=headers)

    # Extract the ID of the post from the response
    return response.json()[0]["id"]

def update_wp_post(post_info):
    # Get the wordpress id from the slug
    wp_id = get_wp_id_from_slug(post_info['slug'])
    # Update the wordpress post
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    url = f"https://cybernow.info/wp-json/wp/v2/posts/{wp_id}"
    try:
        post_info = type_check_post_info(post_info)
    except Exception as e:
        print(f"Failed to type check post info: {e}")
        return
    try:
        response = httpx.post(url, json=post_info, headers=headers)
        if response.status_code != 200:
            print(f"Failed to update post: {response.text}")
            return
    except Exception as e:
        print(f"Failed to update post: {e}")
        return
    print(f"Successfully updated post with id {wp_id}.")
    return response.json()

def type_check_post_info(post_info):
    sanitized_post_info = {}
    for key, value in post_info.items():
        if key == 'yoast_meta' and isinstance(value, dict):
            sanitized_yoast_meta = {}
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, str):  # since all the yoast_meta sub fields are string type
                    sanitized_yoast_meta[sub_key] = sub_value
                else:
                    print(f"Skipping invalid field in yoast_meta: {sub_key}, expected type str but got {type(sub_value)}")
            sanitized_post_info[key] = sanitized_yoast_meta
        elif key in post_fields and isinstance(value, post_fields[key]):
            sanitized_post_info[key] = value
    return sanitized_post_info

def add_tag_to_wordpress(token, tag):
    headers = {'Authorization': f'Bearer {token}'}
    
    # Fetch the tags
    tags_endpoint = "http://cybernow.info/wp-json/wp/v2/tags"

    # Check if the tag already exists
    response = httpx.get(tags_endpoint, headers=headers)
    if response.status_code == 200:
        tags = response.json()
        for existing_tag in tags:
            if existing_tag['name'] == tag:
                print(f"Tag '{tag}' already exists")
                return existing_tag['id']
    else:
        print(f"Failed to fetch tags: {response.text}")
        return None
    
    # Create the tag
    payload = {
        'name': tag
    }
    response = httpx.post(tags_endpoint, headers=headers, json=payload)
    if response.status_code == 201:
        print(f"Created tag '{tag}'")
        return response.json().get('id')
    else:
        print(f"Failed to create tag '{tag}': {response.text}")
        return None
    
# Create a new post on WordPress
def create_wordpress_post(token, post_info, post_time):
    if post_info is None:
        logging.error("Error: post_info is None")
        raise ValueError("post_info is None")
    
    post_endpoint = "http://cybernow.info/wp-json/wp/v2/posts"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # Append the following fields to the post_info dictionary
    post_info['date'] = post_time.strftime("%Y-%m-%dT%H:%M:%S")
    post_info['date_gmt'] = (post_time - timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%S")
    post_info['status'] = 'publish'
    
    # Initialize sanitized_post_info dictionary with status, date, and date_gmt
    sanitized_post_info = type_check_post_info(post_info)
    
       # else:
       #     print(f"Skipping invalid field: {key}, expected type {post_fields.get(key, 'Unknown')} but got {type(value)}")
    response = httpx.post(post_endpoint, json=sanitized_post_info, headers=headers)
    
    if response.status_code == 201:
        print("Post created successfully.")
        return response.json()  # Return the post data
    else:
        print(sanitized_post_info)
        raise Exception(f"Failed to create post: {response.text}")


def fetch_categories(token):
    # Establish headers
    headers = {'Authorization': f'Bearer {token}'}
    
    # Fetch the categories
    categories_endpoint = "http://cybernow.info/wp-json/wp/v2/categories"
    response = httpx.get(categories_endpoint, headers=headers)
    
    if response.status_code == 200:
        categories = response.json()
        
        # Simplify the response to only include 'id' and 'name'
        simplified_categories = []
        for category in categories:
            simplified_category = {'id': category['id'], 'name': category['name']}
            # If category name is 'Uncategorized' or 'C-Suite Articles', skip it
            if simplified_category['name'] == 'Uncategorized' or simplified_category['name'] == 'C-Suite Articles':
                continue
            simplified_categories.append(simplified_category)
        return simplified_categories
    else:
        print(f"Failed to fetch categories: {response.text}")
        return None
    
def fetch_tags(token):
    # Establish headers
    headers = {'Authorization': f'Bearer {token}'}
    
    # Fetch the tags
    tags_endpoint = "http://cybernow.info/wp-json/wp/v2/tags"
    response = httpx.get(tags_endpoint, headers=headers)
    
    if response.status_code == 200:
        tags = response.json()
        
        # Simplify the response to only include 'id' and 'name'
        simplified_tags = []
        for tag in tags:
            simplified_tag = {'id': tag['id'], 'name': tag['name']}
            simplified_tags.append(simplified_tag)
        
        return simplified_tags
        
    else:
        print(f"Failed to fetch tags: {response.text}")
        return None
    
def fetch_wordpress_taxonomies(token):
    categories = fetch_categories(token)
    tags = fetch_tags(token)
    return categories, tags

