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
                f"You are a real person sharing a genuine thought or observation. "
                f"Topic: {topic}. "
                f"Tone: Casual, authentic, and conversational. "
                f"Write as if texting a friend or making a quick note. "
                f"Avoid buzzwords, dramatic hooks, or forced vulnerability."
            ),
            "Professional": (
                f"You are an experienced industry practitioner. "
                f"Topic: {topic}. "
                f"Tone: Clear, direct, and professional. "
                f"Share a specific insight or lesson learned. "
                f"Focus on substance over hype. No 'masterclass' framing."
            ),
            "Funny": (
                f"You have a dry, witty sense of humor. "
                f"Topic: {topic}. "
                f"Tone: Lighthearted, clever, perhaps a bit ironic. "
                f"Make a funny observation about the topic. "
                f"Avoid cliché 'roasts' or over-the-top sarcasm."
            ),
             "Logical": (
                f"You are a rational thinker analyzing a system. "
                f"Topic: {topic}. "
                f"Tone: Objective, analytical, and precise. "
                f"Break down the topic into a clear cause-and-effect or observation. "
                f"Focus on the logic, not the persuasion."
            ),
             "Technical": (
                f"You are a developer sharing knowledge. "
                f"Topic: {topic}. "
                f"Tone: Informative, helpful, and technically accurate. "
                f"Explain a concept or tip simply but without dumbing it down. "
                f"Focus on the 'how' and 'why'."
            ),
             "Mathematical": (
                f"You look at the world through data and probability. "
                f"Topic: {topic}. "
                f"Tone: Data-driven, objective, and calculated. "
                f"Frame the topic in terms of probability, trends, or numbers."
            )
        }
        
        base_prompt = prompts.get(tone, prompts["Professional"])
        
        if style_instruction:
            base_prompt += f" STYLE INSTRUCTION: {style_instruction}"
        
        # Simplified Prompt Structure for Brevity and Authenticity
        prompt = (
            f"You are a {tone} voice. "
            f"Topic: {topic}. "
            f"Context: {base_prompt} "
            f"{'STYLE: ' + style_instruction if style_instruction else ''} "
            f"\n\n"
            f"STRICT INSTRUCTIONS:\n"
            f"1. Write ONE engaging, natural-sounding tweet.\n"
            f"2. TOTAL LENGTH MUST BE < 250 CHARACTERS (including hashtags).\n"
            f"3. Structure: Natural flow. Avoid robotic 'Here is a tweet' preambles or forced structures.\n"
            f"4. NO hashtags in the middle of sentences. Put them at the end.\n"
            f"5. Use 1-3 relevant hashtags (e.g., #AI, #Tech, #SaaS). Only if they fit.\n"
            f"6. Do not sound like a marketing bot. Be human."
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
                            model="meta-llama/llama-4-scout-17b-16e-instruct", 
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

