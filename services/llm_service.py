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

    def generate_tweet(self, topic: str, tone: str = "Professional") -> str:
        """
        Generates a tweet based on the given topic and tone using Gemini.
        """
        prompts = {
            "Human": (
                f"You are a regular person sharing their journey. "
                f"Write a tweet about {topic}. "
                f"Use a casual, authentic, and relatable tone. "
                f"Use first-person language ('I', 'my'). "
                f"Do not sound corporate or like an expert. Just a human learning and sharing."
            ),
            "Professional": (
                 f"You are a tech founder and expert developer deeply knowledgeable in AI, LLMs, ML, DL, and RL. "
                 f"Write a tweet about {topic}. "
                 f"The tone should be professional, insightful, and concise, reflecting deep technical understanding. "
                 f"Avoid generic buzzwords. Use industry-standard terminology where appropriate."
            ),
            "Funny": (
                f"You are a witty tech enthusiast. "
                f"Write a tweet about {topic}. "
                f"Make it humorous, sarcastic, or ironic. "
                f"Poke fun at the complexities of tech/AI if appropriate."
            ),
             "Logical": (
                f"You are a purely logical analyst. "
                f"Write a tweet about {topic}. "
                f"Focus on facts, cause-and-effect, and reasoning. "
                f"Be structured and objective."
            ),
             "Technical": (
                f"You are a senior engineer writing for other engineers. "
                f"Write a tweet about {topic}. "
                f"Dive into the technical details, architecture, or code-level specifics. "
                f"Assume the reader is technical."
            ),
             "Mathematical": (
                f"You are a mathematician looking at tech. "
                f"Write a tweet about {topic}. "
                f"Use mathematical analogies, probability, or abstract reasoning. "
                f"Be precise."
            )
        }
        
        base_prompt = prompts.get(tone, prompts["Professional"])
        
        prompt = (
            f"{base_prompt} "
            f"STRICT CONSTRAINT: The tweet MUST be under 280 characters. "
            f"OPTIMIZE FOR ENGAGEMENT: Start with a strong hook or question. "
            f"End with a clear Call to Action (CTA) or a thought-provoking statement. "
            f"Do not sound like a bot. "
            f"Include 2-3 relevant hashtags at the end to maximize reach. "
            f"Just the tweet content."
        )
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logging.error(f"Error generating tweet: {e}")
            return f"Error generating tweet about {topic}. Please try again later."
