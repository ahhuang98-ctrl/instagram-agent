import logging

from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential

from agent.logger import get_logger

logger = get_logger("image_generator")


class ImageGenerationError(Exception):
    pass


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _call_fal(arguments: dict) -> dict:
    import fal_client
    return fal_client.subscribe(
        "fal-ai/bytedance/dreamina/v3.1/text-to-image",
        arguments=arguments,
    )


def generate_image(
    prompt: str,
    generator: str = "fal",
    size_preset: str = "square_hd",
    custom_width: int | None = None,
    custom_height: int | None = None,
    enhance_prompt: bool = True,
    num_images: int = 1,
    seed: int | None = None,
) -> str:
    """Generate an image and return a URL or local file path.

    generator='dreamina_browser' uses browser automation (free, no fal.ai needed).
    generator='fal' uses the fal.ai API (paid, requires funded FAL_KEY).
    """
    if generator == "dreamina_browser":
        from agent.dreamina_browser import generate_image_dreamina
        return generate_image_dreamina(prompt)

    arguments: dict = {
        "prompt": prompt,
        "enhance_prompt": enhance_prompt,
        "num_images": num_images,
    }

    if custom_width and custom_height:
        arguments["image_size"] = {"width": custom_width, "height": custom_height}
    else:
        arguments["image_size"] = size_preset

    if seed is not None:
        arguments["seed"] = seed

    logger.info(f"Generating image via fal.ai: '{prompt[:80]}...'")
    try:
        result = _call_fal(arguments)
    except Exception as e:
        raise ImageGenerationError(f"fal.ai API call failed: {e}") from e

    images = result.get("images", [])
    if not images or not images[0].get("url"):
        raise ImageGenerationError(f"fal.ai returned no image URLs. Response: {result}")

    url = images[0]["url"]
    logger.info(f"Image generated: {url}")
    return url
