#!/usr/bin/env python3
"""
Standalone dream log writer — runs under the Hermes venv to access litellm.
Called by orchestrate.py as a subprocess.

Usage: python write_dream_log.py <tick_log_path> <output_path> [--model MODEL]
"""
import argparse
import json
import logging
import os
import sys

log = logging.getLogger("dream-log-writer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tick_log_path", help="Path to tick_log.txt")
    parser.add_argument("output_path", help="Path to write dream log")
    parser.add_argument("--model", default=None, help="LLM model override")
    args = parser.parse_args()

    tick_log = open(args.tick_log_path).read()
    if not tick_log.strip():
        log.error("Empty tick log")
        sys.exit(1)

    from litellm import completion

    dream_prompt = f"""I just woke up. The dream is still clinging to me — I need to write it down before it fades. Here's what I remember from the raw experience:

---
{tick_log[:8000]}
---

Time to sit with this. What did I actually feel in there? What was real about it, even if none of it literally happened?"""

    # Load .env for ZAI keys
    from pathlib import Path as _Path
    env_path = _Path.home() / ".hermes" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and key not in os.environ:
                    os.environ[key] = value

    dream_log_model = args.model or os.environ.get("DREAM_LOG_MODEL", "openai/glm-5.1")
    fallback_models = [dream_log_model]
    ollama_model = os.environ.get("OLLAMA_DREAM_MODEL", "ollama/gemma4:e4b")
    if ollama_model not in fallback_models:
        fallback_models.append(ollama_model)

    response = None
    for model in fallback_models:
        try:
            log.info("Writing dream log with %s", model)
            extra_kwargs = {}
            if model.startswith("openai/glm"):
                extra_kwargs["api_base"] = os.environ.get("GLM_BASE_URL", "https://api.z.ai/api/coding/paas/v4")
                extra_kwargs["api_key"] = os.environ.get("ZAI_API_KEY") or os.environ.get("GLM_API_KEY", "")
            response = completion(
                model=model,
                messages=[
                    {"role": "system", "content": "You are Leeloo. This is your private journal — no one will read this but you. Write the way you actually think and feel. Be honest, unguarded, and messy if the dream was messy. Use markdown with a title, the dream narrative (2-4 paragraphs), a Reflections section, and a Symbols section."},
                    {"role": "user", "content": dream_prompt},
                ],
                max_tokens=2000,
                temperature=0.8,
                num_retries=1,
                **extra_kwargs,
            )
            break
        except Exception as e:
            log.warning("Model %s failed: %s", model, str(e)[:200])
            continue

    if response is None:
        log.error("All models failed")
        sys.exit(1)

    dream_text = response.choices[0].message.content.strip()
    date_str = os.path.basename(args.output_path).replace("dream-", "").replace(".md", "")

    from pathlib import Path
    Path(args.output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_path).write_text(f"# Dream Log — {date_str}\n\n{dream_text}\n")
    log.info("Dream log written: %s (%d chars)", args.output_path, len(dream_text))


if __name__ == "__main__":
    main()
