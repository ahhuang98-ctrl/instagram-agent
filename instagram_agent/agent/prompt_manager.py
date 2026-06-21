import random
from typing import TypedDict

import yaml

from agent.logger import get_logger

logger = get_logger("prompt_manager")


class PromptEntry(TypedDict):
    image_prompt: str
    caption: str


class PromptManager:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self.strategy: str = config["prompts"]["selection"]
        self.feed_prompts: list[PromptEntry] = config["prompts"]["feed"]
        self.story_prompts: list[PromptEntry] = config["prompts"].get("stories", [])
        self._feed_index = 0
        self._story_index = 0

    def get_feed_prompt(self) -> PromptEntry:
        return self._pick(self.feed_prompts, "_feed_index")

    def get_story_prompt(self) -> PromptEntry:
        return self._pick(self.story_prompts, "_story_index")

    def _pick(self, pool: list[PromptEntry], index_attr: str) -> PromptEntry:
        if not pool:
            raise ValueError("Prompt pool is empty")
        if self.strategy == "random":
            entry = random.choice(pool)
        else:
            idx = getattr(self, index_attr)
            entry = pool[idx % len(pool)]
            setattr(self, index_attr, idx + 1)
        logger.debug(f"Selected prompt: {entry['image_prompt'][:60]}...")
        return entry
