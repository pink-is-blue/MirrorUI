import argparse
import asyncio
import json
import pathlib

from mirrorui.pipeline import MirrorPipeline


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run MIRRORUI pipeline for a URL")
    parser.add_argument("url", help="Target website URL")
    args = parser.parse_args()

    root = pathlib.Path(__file__).resolve().parent
    pipeline = MirrorPipeline(root)
    result = await pipeline.run(args.url)

    output = {
        "title": result.title,
        "screenshot_path": result.screenshot_path,
        "files": list(result.files.keys()),
        "metrics": result.metrics,
        "comparison": result.comparison,
        "actions": [action.model_dump() for action in result.actions],
    }
    print(json.dumps(output, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    asyncio.run(main())
