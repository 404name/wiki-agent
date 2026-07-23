import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.getenv("WIKI_AGENT_PORT", "19829")))
    args = parser.parse_args()
    uvicorn.run("wiki_agent.api:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
