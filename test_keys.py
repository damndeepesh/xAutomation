import tweepy
import os
import datetime
from dotenv import load_dotenv

# Load .env
load_dotenv()

print("--- X API Debug Tool ---")

# 1. Get Keys
consumer_key = os.getenv('TWITTER_API_KEY')
consumer_secret = os.getenv('TWITTER_API_SECRET')
access_token = os.getenv('TWITTER_ACCESS_TOKEN')
access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

print(f"Consumer Key Loaded: {bool(consumer_key)}")
print(f"Access Token Loaded: {bool(access_token)}")

if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
    print("ERROR: Missing keys in .env")
    exit(1)

# 2. Initialize Client (User Context)
try:
    client = tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )
    print("Client initialized.")
except Exception as e:
    print(f"Error initializing client: {e}")
    exit(1)

# 3. Create unique test tweet
timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
text = f"Debug test tweet at {timestamp}"

print(f"Attempting to post: '{text}'")

try:
    response = client.create_tweet(text=text)
    print("SUCCESS!")
    print(f"Response: {response}")
except tweepy.errors.Forbidden as e:
    print("\n--- 403 FORBIDDEN ERROR ---")
    print(f"Detail: {e}")
    if hasattr(e, 'response'):
        print(f"Response Headers: {e.response.headers}")
        print(f"Response Content: {e.response.text}")
    print("---------------------------")
    print("Possible Causes:")
    print("1. App permissions are NOT 'Read and Write' in Developer Portal.")
    print("2. Keys were NOT regenerated after changing permissions.")
    print("3. You are on Free Tier and hitting a limit (unlikely for 403).")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
