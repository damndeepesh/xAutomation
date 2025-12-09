import json
import logging
import random
import datetime
import os
from services.llm_service import LLMService
from services.x_service import XService

STATE_FILE = "automation_state.json"

class AutomationService:
    def __init__(self):
        self.llm_service = LLMService()
        self.x_service = XService()
        self.load_state()

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    self.state = json.load(f)
            except Exception as e:
                logging.error(f"Failed to load automation state: {e}")
                self.state = {}
        else:
            self.state = {}

    def save_state(self):
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save automation state: {e}")

    def start_automation(self, start_date_str, end_date_str, tweets_per_day, themes):
        """
        Configures the automation parameters.
        Dates should be in YYYY-MM-DD format.
        Themes is a list of strings.
        """
        self.state['config'] = {
            'start_date': start_date_str,
            'end_date': end_date_str,
            'tweets_per_day': int(tweets_per_day),
            'themes': themes
        }
        self.state['daily_stats'] = {
            'date': datetime.datetime.now().strftime("%Y-%m-%d"),
            'count': 0
        }
        self.save_state()
        logging.info(f"Automation configured: {self.state['config']}")
        return True

    def get_status(self):
        config = self.state.get('config')
        if not config:
            return "Automation is NOT configured."
        
        return (
            f"📅 Range: {config['start_date']} to {config['end_date']}\n"
            f"🔢 Target: {config['tweets_per_day']} tweets/day\n"
            f"📝 Themes: {', '.join(config['themes'])}\n"
            f"📊 Today's Count: {self.state.get('daily_stats', {}).get('count', 0)}"
        )

    def check_and_post(self):
        """
        Main logic to be called by the scheduler.
        """
        logging.info("Checking automation status...")
        config = self.state.get('config')
        if not config:
            logging.info("No automation config found.")
            return

        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 1. Check Date Range
        try:
            start_date = datetime.datetime.strptime(config['start_date'], "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(config['end_date'], "%Y-%m-%d").date()
            current_date = datetime.datetime.now().date()
            
            if current_date > end_date:
                logging.info(f"Automation COMPLETED: Current date {current_date} is past end date {end_date}. Clearing config.")
                self.state['config'] = None
                self.save_state()
                return

            if current_date < start_date:
                logging.info(f"Automation skipped: Current date {current_date} is before start date {start_date}.")
                return
        except ValueError as e:
            logging.error(f"Date parsing error in automation config: {e}")
            return

        # 2. Check Daily Limit
        daily_stats = self.state.get('daily_stats', {'date': today_str, 'count': 0})
        
        # Reset stats if it's a new day
        if daily_stats['date'] != today_str:
            daily_stats = {'date': today_str, 'count': 0}
            self.state['daily_stats'] = daily_stats
            self.save_state()

        if daily_stats['count'] >= config['tweets_per_day']:
            logging.info(f"Automation skipped: Daily limit of {config['tweets_per_day']} reached.")
            return

        # 3. Dynamic Urgency (Catch-Up Logic)
        now = datetime.datetime.now()
        end_of_day = now.replace(hour=23, minute=59, second=59)
        minutes_left = (end_of_day - now).total_seconds() / 60
        intervals_left = max(minutes_left / 30, 0.5) # Avoid div/0, assume at least 0.5 intervals
        
        needed = config['tweets_per_day'] - daily_stats['count']
        
        # Probability P = Needed / RemainingIntervals
        # If we need 2 tweets and have 2 intervals left, P = 1.0 (100%)
        # If we need 1 tweet and have 10 intervals left, P = 0.1 (10%)
        probability = min(needed / intervals_left, 1.0)
        
        if probability < 0: probability = 0

        logging.info(f"Dynamic Check: Needed={needed}, TimeLeft={int(minutes_left)}m, Intervals={intervals_left:.1f}, Prob={probability:.2f}")

        if random.random() > probability: 
             logging.info(f"Automation skipped: Rolled dice against P={probability:.2f}")
             return

        # 4. Generate and Post
        theme = random.choice(config['themes'])
        
        styles = [
            "Use a metaphor to explain.",
            "Ask a thought-provoking question.",
            "Make a controversial but defensible statement.",
            "Share a quick tip or 'did you know'.",
            "Use a 'unpopular opinion' format.",
            "Connect this to a historical event.",
            "Explain it like I'm 5 (ELI5).",
            "Be sarcastic and witty.",
            "Be strictly professional and data-driven."
        ]
        style = random.choice(styles)
        
        logging.info(f"Automation Triggered! Theme: {theme}, Style: {style}")
        
        tweet_content = self.llm_service.generate_tweet(
            topic=theme, 
            tone="Professional", # internal default, overridden mostly by style instruction
            style_instruction=style
        )
        
        if tweet_content:
            success = self.x_service.post_tweet(tweet_content)
            if success:
                # Update State
                self.state['daily_stats']['count'] += 1
                self.save_state()
                logging.info(f"Automated tweet posted! Count today: {self.state['daily_stats']['count']}")
            else:
                logging.error("Failed to post automated tweet.")
