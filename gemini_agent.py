# gemini_agent.py
from tenacity import retry, stop_after_attempt, wait_exponential
from google import genai

from prompts import MASTER_SYSTEM_PROMPT, NEWS_TO_X_PROMPT

class GeminiStablecoinWriter:
    def __init__(self, api_key: str, model_name: str):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def generate_x_post_from_news(self, brief: str, language_mode: str, run_slot: str, slot_style: str) -> str:
        prompt = MASTER_SYSTEM_PROMPT + "\n" + NEWS_TO_X_PROMPT.format(
            brief=brief,
            language_mode=language_mode,
            run_slot=run_slot,
            slot_style=slot_style
        )

        resp = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt
        )

        # google-genai returns a response with .text commonly available
        text = getattr(resp, "text", None)
        if not text:
            # fallback if the SDK returns parts
            text = str(resp)
        return text.strip()
