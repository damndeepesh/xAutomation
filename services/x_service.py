import tweepy
import config
import logging

class XService:
    def __init__(self):
        self.consumer_key = config.TWITTER_API_KEY
        self.consumer_secret = config.TWITTER_API_SECRET
        self.access_token = config.TWITTER_ACCESS_TOKEN
        self.access_token_secret = config.TWITTER_ACCESS_TOKEN_SECRET
        self.bearer_token = config.TWITTER_BEARER_TOKEN
        
        if not all([self.consumer_key, self.consumer_secret, self.access_token, self.access_token_secret]):
             logging.warning("Twitter API credentials missing. X Service will fail.")

        # Initialize Client without Bearer Token to ensure OAuth 1.0a User Context is used for posting
        self.client = tweepy.Client(
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret
        )

        try:
            me = self.client.get_me()
            logging.info(f"X Service Connected as: {me.data.name} (@{me.data.username})")
        except Exception as e:
            logging.error(f"X Service Authentication Failed: {e}") 
            logging.error("Please ensure you have REGENERATED your Access Token/Secret after setting permissions to 'Read and Write'.")

        # Authenticate v1.1 for media upload
        auth = tweepy.OAuth1UserHandler(
            self.consumer_key, self.consumer_secret,
            self.access_token, self.access_token_secret
        )
        self.api = tweepy.API(auth)

        try:
            # Verify credentials and check access level header
            self.api.verify_credentials()
            access_level = self.api.last_response.headers.get('x-access-level', 'unknown')
            logging.info(f"X API Access Level: {access_level.upper()}")
            
            if 'write' not in access_level.lower():
                logging.error("CRITICAL: Your Access Token is READ-ONLY. You MUST regenerate it to get Write permissions.")
        except Exception as e:
            logging.warning(f"Could not verify v1.1 credentials (normal for Free Tier if only v2 is allowed?): {e}")

    def post_tweet(self, text: str, media_paths: list[str] = None) -> bool:
        """
        Posts a tweet to X, optionally with media.
        """
        try:
            media_ids = []
            if media_paths:
                logging.info(f"Uploading {len(media_paths)} images...")
                for path in media_paths:
                    media = self.api.media_upload(filename=path)
                    media_ids.append(str(media.media_id))
                    logging.info(f"Uploaded media ID: {media.media_id}")

            response = self.client.create_tweet(text=text, media_ids=media_ids if media_ids else None)
            logging.info(f"Tweet posted successfully: {response}")
            return True
        except tweepy.errors.Forbidden as e:
            logging.error(f"Error posting tweet (403 Forbidden): {e}")
            logging.error(f"Full Error Response: {e.response.text if hasattr(e, 'response') else 'No response body'}")
            
            if "duplicate content" in str(e).lower() or (hasattr(e, 'response') and "duplicate" in e.response.text.lower()):
                 logging.error("ERROR REASON: DUPLICATE CONTENT. You cannot post the exact same tweet twice.")
            else:
                 logging.error("HINT: Check your X Developer Portal. Ensure 'User authentication settings' are set to 'Read and Write'. "
                          "ALSO: You must REGENERATE your Access Token and Secret after changing permissions.")
            return False
        except Exception as e:
            logging.error(f"Error posting tweet: {e}")
            return False
