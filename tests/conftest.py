"""Tests must never touch a live provider, whatever .env says."""

import os

os.environ["CLUE_LLM_PROVIDER"] = "mock"
os.environ["CLUE_LLM_MODEL"] = "mock"
os.environ.pop("CLUE_LLM_CACHE", None)
