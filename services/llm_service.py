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
                f"You are a real person just sharing a quick thought. "
                f"Topic: {topic}. "
                f"Tone: Casual, authentic, lowercase-friendly. "
                f"Write like you're texting a friend. "
                f"No cringy hashtags or forced engagement hooks."
            ),
            "Professional": (
                f"You are a thoughtful professional sharing a quick insight. "
                f"Topic: {topic}. "
                f"Tone: Accessible, smart but not academic. "
                f"Share the insight directly. No buzzwords."
            ),
            "Funny": (
                f"You are naturally funny and observant. "
                f"Topic: {topic}. "
                f"Tone: Dry, witty, maybe a bit self-deprecating. "
                f"Just a quick funny observation. No 'dad jokes'."
            ),
            "Logical": (
                f"You are a clear thinker connecting the dots. "
                f"Topic: {topic}. "
                f"Tone:  Straightforward and grounded. "
                f"Point out the logic simply. No fancy words."
            ),
            "Technical": (
                f"You are a dev engaging with peers. "
                f"Topic: {topic}. "
                f"Tone: Practical and real. "
                f"Share the tip or thought directly. "
            ),
            "Mathematical": (
                f"You see the numbers behind things. "
                f"Topic: {topic}. "
                f"Tone: Sharp and precise but human. "
                f"Frame it with a quick stat or probability. Keep it very brief."
            )
        }
        
        base_prompt = prompts.get(tone, prompts["Professional"])
        
        if style_instruction:
            base_prompt += f" STYLE INSTRUCTION: {style_instruction}"
        
        # Simplified Prompt Structure for Brevity and Authenticity
        prompt = (
            f"Role: {tone} voice. "
            f"Topic: {topic} "
            f"Context: {base_prompt}\n"
            f"INSTRUCTIONS:\n"
            f"- MAX LENGTH: 270 characters TOTAL (INLCUDING HASHTAGS). STRICT.\n"
            f"- KEEP MAIN TEXT UNDER 200 CHARACTERS to leave room for tags.\n"
            f"- REQUIRED: You MUST add 1-3 relevant hashtags at the end.\n"
            f"- NO hashtags in the middle of sentences.\n"
            f"- Be human. No AI buzzwords."
        )
        
        text = None
        try:
            # Try Gemini First
            if self.model:
                # Remove hard token limit to prevent premature cutoffs; rely on prompt
                response = self.model.generate_content(
                    prompt, 
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7 
                    )
                )
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
                        model="meta-llama/llama-4-scout-17b-16e-instruct", # Use stable model
                    )
                    text = chat_completion.choices[0].message.content.strip()
                    logging.info("Groq fallback generation successful.")
                except Exception as groq_e:
                    logging.error(f"Groq fallback also failed: {groq_e}")
            else:
                logging.error("Groq fallback unavailable (no API key).")

        
        # If both failed, text is still None or empty
        if not text:
            return None

        # Cleanup: Remove surrounding quotes if present and strip markdown asterisks
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1].strip()
        text = text.replace('*', '')
        
        # Strict Length Check 
        if len(text) > 280:
            logging.error(f"Generation Failed: Tweet too long ({len(text)} chars). STRICT LIMIT.")
            return None
        
        # Validation for other issues
        if self._validate_tweet_content(text):
            return text
        
        logging.warning(f"Tweet generation rejected: {text}")
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

