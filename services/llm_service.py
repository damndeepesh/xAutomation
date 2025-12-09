import google.generativeai as genai
import config
import logging
from groq import Groq

class LLMService:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.groq_api_key = config.GROQ_API_KEY
        
        # Initialize Gemini
        if not self.api_key:
            logging.warning("GEMINI_API_KEY not found. LLM service might fail if Groq is also missing.")
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')

        # Initialize Groq
        if not self.groq_api_key:
            logging.warning("GROQ_API_KEY not found. Fallback will not be available.")
            self.groq_client = None
        else:
            self.groq_client = Groq(api_key=self.groq_api_key)

    def generate_tweet(self, topic: str, tone: str = "Professional", style_instruction: str = None) -> str:
        """
        Generates a tweet based on the given topic, tone, and optional style instruction.
        Attempts Gemini first, then falls back to Groq.
        """
        prompts = {
            "Human": (
                f"You are a brutally honest indie hacker building in public. "
                f"Topic: {topic}. "
                f"Tone: Raw, vulnerable, but highly ambitious. "
                f"Share the painful truth about building a business. "
                f"Make the reader feel your struggle and your win."
            ),
            "Professional": (
                f"You are a Top 1% Growth Hacker and Authority Figure. "
                f"Topic: {topic}. "
                f"Tone: Authoritative, controversial, confidence-inspiring. "
                f"Teach a masterclass in one tweet. "
                f"Focus on ROI, leverage, and scaling."
            ),
            "Funny": (
                f"You are a cynical senior engineer who sees through all the hype. "
                f"Topic: {topic}. "
                f"Tone: Sarcastic, dry, witty. "
                f"Roast the industry while dropping truth bombs."
            ),
             "Logical": (
                f"You are a Systems Thinker obsessed with efficiency. "
                f"Topic: {topic}. "
                f"Tone: Cold, precise, high-signal. "
                f"Cut through the noise. Facts only."
            ),
             "Technical": (
                f"You are the CTO everyone wants to hire. "
                f"Topic: {topic}. "
                f"Tone: Deeply technical but accessible to smart people. "
                f"Explain how things *actually* work under the hood."
            ),
             "Mathematical": (
                f"You are a quant trader applied to life. "
                f"Topic: {topic}. "
                f"Tone: Probabilistic, analytical, game-theoretic. "
                f"Frame everything as positive/negative expected value (EV)."
            )
        }
        
        base_prompt = prompts.get(tone, prompts["Professional"])
        
        if style_instruction:
            base_prompt += f" STYLE INSTRUCTION: {style_instruction}"
        
        prompt = (
            f"{base_prompt} "
            f"STRICT CONSTRAINT: Tweet MUST be < 280 chars. NO fluff. "
            f"ROLE: World-Class Copywriter & Marketing Master. "
            f"GOAL: Maximize views, replies, and profile clicks (Revenue Focus). "
            f"STRATEGY (The 'Virality Formula'): "
            f"1. HOOK: Stop the scroll immediately. Use a polarizing opinion, a hard truth, or a 'you're doing it wrong' angle. "
            f"2. VALUE: Give one massive insight or 'aha' moment. "
            f"3. CTA: Ask a question that demands an answer or tell them to build. "
            f"TONE: Confident, edgy, authoritative. Create FOMO. "
            f"HASHTAGS: Use exactly 2-3 of: #AI #TechTwitter #BuildInPublic #SaaS #Coding #Entrepreneurship. "
            f"Simply the tweet text. Zero formatting."
        )
        
        
        for attempt in range(3):
            text = None
            try:
                # Try Gemini First
                if self.model:
                    response = self.model.generate_content(prompt)
                    text = response.text.strip()
                else:
                    raise Exception("Gemini model not initialized")

            except Exception as e:
                logging.warning(f"Gemini generation failed: {e}. Attempting Groq fallback...")
                
                # Fallback to Groq
                if self.groq_client:
                    try:
                        chat_completion = self.groq_client.chat.completions.create(
                            messages=[
                                {
                                    "role": "user",
                                    "content": prompt,
                                }
                            ],
                            model="llama3-70b-8192", 
                        )
                        text = chat_completion.choices[0].message.content.strip()
                        logging.info("Groq fallback generation successful.")
                    except Exception as groq_e:
                        logging.error(f"Groq fallback also failed: {groq_e}")
                else:
                    logging.error("Groq fallback unavailable (no API key).")

            
            # If both failed, text is still None or empty
            if not text:
                continue

            # Cleanup: Remove surrounding quotes if present and strip markdown asterisks
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1].strip()
            text = text.replace('*', '')
            
            # CRITICAL: Strict Length Check - Fail IMMEDIATELY if too long
            if len(text) > 280:
                logging.error(f"Generation Failed: Tweet too long ({len(text)} chars). STRICT LIMIT. No retry.")
                return None
            
            # Validation for other issues (we can retry these)
            if self._validate_tweet_content(text):
                return text
            
            logging.warning(f"Tweet generation rejected (Attempt {attempt+1}/3): {text}")
        
        logging.error("Failed to generate valid tweet after 3 attempts.")
        return None

    def _validate_tweet_content(self, text: str) -> bool:
        """
        Validates the generated tweet content (forbidden phrases, etc).
        Assumes length check is already done.
        """
        if not text:
            return False
            
        forbidden_phrases = [
            "I cannot", "I can't", "I am an AI", "large language model",
            "Generate a tweet", "Here is a tweet", "Sure!", "Okay,"
        ]
        
        for phrase in forbidden_phrases:
            if phrase.lower() in text.lower():
                logging.warning(f"Validation Failed: Contains forbidden phrase '{phrase}'.")
                return False
                
        return True

