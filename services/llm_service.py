import google.generativeai as genai
import config
import logging

class LLMService:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        if not self.api_key:
            logging.warning("GEMINI_API_KEY not found. LLM service will fail.")
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')

    def generate_tweet(self, topic: str, tone: str = "Professional", style_instruction: str = None) -> str:
        """
        Generates a tweet based on the given topic, tone, and optional style instruction.
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
            try:
                response = self.model.generate_content(prompt)
                text = response.text.strip()
                
                # Cleanup: Remove surrounding quotes if present and strip markdown asterisks
                if text.startswith('"') and text.endswith('"'):
                    text = text[1:-1].strip()
                text = text.replace('*', '')
                
                # Validation
                if self._validate_tweet(text):
                    return text
                
                logging.warning(f"Tweet generation rejected (Attempt {attempt+1}/3): {text}")
            
            except Exception as e:
                logging.error(f"Error generating tweet (Attempt {attempt+1}/3): {e}")
        
        logging.error("Failed to generate valid tweet after 3 attempts.")
        return None

    def _validate_tweet(self, text: str) -> bool:
        """
        Validates the generated tweet against common failure modes.
        """
        if not text:
            return False
            
        if len(text) > 280:
            logging.warning("Validation Failed: Text too long.")
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
