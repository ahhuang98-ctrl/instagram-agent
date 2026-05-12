import fal_client

from agent.logger import get_logger

logger = get_logger("image_generator")


class ImageGenerationError(Exception):
    pass


def generate_image(
    prompt: str,
    size_preset: str = "square_hd",
    custom_width: int | None = None,
    custom_height: int | None = None,
    enhance_prompt: bool = True,
    num_images: int = 1,
    seed: int | None = None,
) -> str:
    """Generate an image via fal.ai Dreamina V3.1 and return its URL."""
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

    logger.info(f"Generating image: '{prompt[:80]}...'")
    try:
        result = fal_client.subscribe(
            "fal-ai/bytedance/dreamina/v3.1/text-to-image",
            arguments=arguments,
        )
    except Exception as e:
        raise ImageGenerationError(f"fal.ai API call failed: {e}") from e

    images = result.get("images", [])
    if not images or not images[0].get("url"):
        raise ImageGenerationError(f"fal.ai returned no image URLs. Response: {result}")

    url = images[0]["url"]
    logger.info(f"Image generated: {url}")
    return url
