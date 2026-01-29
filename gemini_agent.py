import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential
from prompts import MASTER_SYSTEM_PROMPT, NEWS_TO_X_PROMPT

class GeminiStablecoinWriter:
    def __init__(self, api_key: str, model_name: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def generate_x_post_from_news(self, brief: str, language_mode: str, run_slot: str, slot_style: str) -> str:
        prompt = MASTER_SYSTEM_PROMPT + "\n" + NEWS_TO_X_PROMPT.format(
            brief=brief,
            language_mode=language_mode,
            run_slot=run_slot,
            slot_style=slot_style
        )
        resp = self.model.generate_content(prompt)
        return (resp.text or "").strip()