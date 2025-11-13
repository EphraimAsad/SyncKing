# engine/parser_llm.py
# ------------------------------------------------------------
# Router wrapper: choose Gemini Nano or Cloudflare.
# ------------------------------------------------------------

import os

LLM_MODE = os.getenv("LLM_MODE", "nano")   # default = Gemini Nano

from engine.parser_llm_nano import parse_text_llm_nano
from engine.parser_llm_cloudflare import parse_text_llm_cloudflare  # we move your existing CF logic here


def parse_text_llm(text: str):
    if LLM_MODE.lower() == "cloudflare":
        return parse_text_llm_cloudflare(text)
    return parse_text_llm_nano(text)
