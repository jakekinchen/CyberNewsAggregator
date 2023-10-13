import os
import requests
import datetime
from datetime import datetime, timedelta
from generate_topics import generate_topics
from supabase import create_client, Client
from source_fetcher import gather_sources
from content_optimization import create_factsheets_for_sources
from post_synthesis import post_synthesis, insert_post_info_into_supabase
from wp_post import create_wordpress_post
from extract_text import test_scraping_site
import asyncio
import httpx
from cisa import get_cisa_exploits
# Load environment variables
from dotenv import load_dotenv
import logging
import time
load_dotenv()

# Supabase configuration
supabase_url: str = os.getenv('SUPABASE_ENDPOINT')
supabase_key: str = os.getenv('SUPABASE_KEY')
# Initialize Supabase
supabase: Client = create_client(supabase_url = supabase_url, supabase_key = supabase_key)

amount_of_topics = 1
MIN_SOURCES = 3
exploit_fetcher_activated = False
debug = False
synthesize_factsheets = False

# Access your API keys and token
wp_username = os.getenv('WP_USERNAME')
wp_password = os.getenv('WP_PASSWORD')
wp_token = os.getenv('WP_TOKEN')  # Get the token from environment variables
#os.getenv('WP_TOKEN')  # Get the token from environment variables

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
    response = requests.post(token_endpoint, data=payload)
    if response.status_code == 200:
        token = response.json().get('token')  # Get token directly from JSON response
        #logging.info(f"Received token: {token}")
        return token
    else:
        logging.info(f"Failed to get JWT token: {response.text}")
        raise Exception(f"Failed to get JWT token: {response.text}")

async def delete_topic(topic_id):
    # Delete the topic
    try:
        response = supabase.table("topics").delete().eq("id", topic_id).execute()
    except Exception as e:
        print(f"Failed to delete topic: {e}")
        return
    print(f"Successfully deleted topic with ID {topic_id} and all related sources.")

def post_the_most_recent_topic(token):
    # Get the most recent topic
    response = supabase.table("topics").select("*").execute()
    topic = response.data[0]
    # Post the most recent topic
    post_info = post_synthesis(token, topic)
    # Upload post info to wordpress if post_info['complete_with_images'] is not None and post_info['complete_with_images'] == True:
    if post_info['complete_with_images'] == True:
        create_wordpress_post(post_info, datetime.now() + datetime.timedelta(days=1))
    else:
        print("Uploaded to Supabase but not to WordPress because the WP database would not allow images to be uploaded")

def post_with_post_id(token, post_id):
    #Take the post from supabase with the post id and post it an hour from now to the wordpress site
    response = supabase.table("posts").select("*").eq("id", post_id).execute()
    post_info = response.data[0]
    print(f"Post info: {post_info}")
    create_wordpress_post(token, post_info, datetime.now() + timedelta(hours=1))

async def delete_supabase_post(topic_id):
    # topic_id is a foreign key in the supabase table posts
    # Delete the post
    try:
        response = supabase.table("posts").delete().eq("topic_id", topic_id).execute()
    except Exception as e:
        print(f"Failed to delete post: {e}")
        return
  
    print(f"Successfully deleted post with topic ID {topic_id}.")

async def main():
    total_start_time = time.time()
    token = get_jwt_token(wp_username, wp_password)

    if token is None:
        print("Failed to get token")
        return
    
    if debug:
        print("Debug mode enabled")
        await test_scraping_site()
        return
    
    #print(test_scraping_site())

    # Upload new cisa exploits
    start_time = time.time()
    result = await get_cisa_exploits()
    if result == False:
        print("Failed to get CISA exploits")
        return
    else:
        print(f"Got CISA exploits in {time.time() - start_time:.2f} seconds")
    # Generate topics
    try:
        start_time = time.time()
        generated_topics = generate_topics(supabase, amount_of_topics)
        print(f"Generated {len(generated_topics)} new topics in {time.time() - start_time:.2f} seconds")
        
        for topic in generated_topics:
            print(f"Processing topic: {topic['name']}")
            
            # Gather Sources
            start_time = time.time()
            try:
                gather_sources(supabase, topic, MIN_SOURCES, False)
                print(f"Sources gathered in {time.time() - start_time:.2f} seconds")
            except Exception as e:
                print(f"Failed to gather sources: {e}")
                await delete_topic(topic['id'])
                continue

            # Generate Fact Sheets
            start_time = time.time()
            try:
                topic['factsheet'], topic['external_source_info'] = create_factsheets_for_sources(topic)
                if topic['factsheet'] is None:
                    print("Failed to create any factsheets")
                    await delete_topic(topic['id'])
                    continue
                print(f"Factsheet created in {time.time() - start_time:.2f} seconds")
            except Exception as e:
                print(f"Failed to create factsheet: {e}")
                await delete_topic(topic['id'])
                continue
            if topic['factsheet'] is None:
                print("Failed to create any factsheets")
                await delete_topic(topic['id'])
                continue
            # Generate News
            start_time = time.time()
            try:
                post_info = post_synthesis(token, topic)
                print(f"Post synthesized in {time.time() - start_time:.2f} seconds")
            except Exception as e:
                print(f"Failed to synthesize post: {e}")
                await delete_topic(topic['id'])
                continue
            
            # Insert Post Info into Supabase
            start_time = time.time()
            try:
                insert_post_info_into_supabase(post_info)
                print(f"Post info inserted into Supabase in {time.time() - start_time:.2f} seconds")
            except Exception as e:
                print(f"Failed to insert post info into Supabase: {e}")
                await delete_topic(topic['id'])
                continue
            
            # Create WordPress Post
            start_time = time.time()
            try:
                create_wordpress_post(token, post_info, datetime.now())
                print(f"Post created in {time.time() - start_time:.2f} seconds")
            except Exception as e:
                print(f"Failed to create post: {e}")
                await delete_topic(topic['id'])
                continue
            
    except Exception as e:
        print(f"Failed to process new articles: {e}")
    print(f"Total program took {time.time() - total_start_time:.2f} seconds")
    print("Program Complete.")

if __name__ == "__main__":
    asyncio.run(main())
