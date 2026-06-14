import yaml
from dotenv import load_dotenv

load_dotenv()

from agent.image_generator import ImageGenerationError, generate_image
from agent.image_host import ImageHostingError, upload_image_url_to_imgbb, upload_local_image_to_imgbb
from agent.instagram import InstagramAPIError, post_feed
from agent.logger import get_logger
from agent.prompt_manager import PromptManager
from agent.scheduler import build_scheduler

logger = get_logger("main")


def run_posting_job() -> None:
    logger.info("=" * 60)
    logger.info("Starting posting job")

    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    posting_cfg = config["posting"]
    image_cfg = config["image"]
    imgbb_cfg = config["imgbb"]
    prompt_manager = PromptManager()

    generator = image_cfg.get("generator", "fal")

    def _host_image(image_result: str, name: str) -> str:
        if image_result.startswith("http"):
            return upload_image_url_to_imgbb(
                image_url=image_result,
                expiration=imgbb_cfg.get("expiration", 0),
                name=name,
            )
        return upload_local_image_to_imgbb(
            file_path=image_result,
            expiration=imgbb_cfg.get("expiration", 0),
            name=name,
        )

    if posting_cfg.get("post_feed", True):
        try:
            entry = prompt_manager.get_feed_prompt()
            logger.info(f"Feed prompt: {entry['image_prompt'][:80]}")

            image_result = generate_image(
                prompt=entry["image_prompt"],
                generator=generator,
                size_preset=image_cfg.get("size_preset", "square_hd"),
                custom_width=image_cfg.get("custom_width"),
                custom_height=image_cfg.get("custom_height"),
                enhance_prompt=image_cfg.get("enhance_prompt", True),
            )
            public_url = _host_image(image_result, "feed_post")
            media_id = post_feed(image_url=public_url, caption=entry["caption"])
            logger.info(f"Feed post published. Media ID: {media_id}")

        except (ImageGenerationError, ImageHostingError, InstagramAPIError) as e:
            logger.error(f"Feed post failed: {e}", exc_info=True)

    logger.info("Posting job complete")
    logger.info("=" * 60)


def main() -> None:
    logger.info("Instagram AI Agent starting up")
    scheduler = build_scheduler(job_func=run_posting_job)
    logger.info("Scheduler ready. Waiting for next trigger...")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Shutdown requested. Stopping.")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
