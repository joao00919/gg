import os
import base64
import aiohttp
import asyncio


async def upload_emoji_async(
    session,
    name,
    image_path,
    app_id,
    bot_token,
    max_attempts: int = 6,
):
    ext = os.path.splitext(image_path)[1].lower()
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()

    image_type = "gif" if ext == ".gif" else "png"
    base64_image = (
        f"data:image/{image_type};base64,{base64.b64encode(image_data).decode()}"
    )
    url = f"https://discord.com/api/v10/applications/{app_id}/emojis"
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json",
    }
    payload = {"name": name, "image": base64_image}

    for attempt in range(1, max_attempts + 1):
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 201:
                data = await response.json()
                emoji_id = data["id"]
                print(f"[EmojiUpload] '{name}' criado: {emoji_id}")
                return emoji_id

            if response.status == 429:
                try:
                    data = await response.json()
                    retry_after = float(data.get("retry_after", 5))
                except Exception:
                    retry_after = float(response.headers.get("Retry-After", 5))
                wait = max(1.0, min(retry_after, 60.0))
                print(
                    f"[EmojiUpload] Rate limit em '{name}', aguardando {wait:.1f}s "
                    f"({attempt}/{max_attempts})..."
                )
                await asyncio.sleep(wait + 0.25)
                continue

            text = await response.text()
            if response.status >= 500 and attempt < max_attempts:
                await asyncio.sleep(min(attempt * 2, 15))
                continue
            raise RuntimeError(
                f"HTTP {response.status} ao criar {name}: {text[:500]}"
            )

    raise RuntimeError(f"Limite de tentativas excedido ao criar {name}")


async def upload_emojis_batch(emojis_data, app_id, bot_token):
    async with aiohttp.ClientSession() as session:
        results = []
        for name, image_path in emojis_data:
            try:
                results.append(
                    await upload_emoji_async(
                        session, name, image_path, app_id, bot_token
                    )
                )
                await asyncio.sleep(0.5)
            except Exception as exc:
                print(f"[EmojiUpload] Erro em '{name}': {exc}")
        return results


def upload_emoji(name, image_path, app_id, bot_token):
    return asyncio.run(upload_emojis_batch([(name, image_path)], app_id, bot_token))
