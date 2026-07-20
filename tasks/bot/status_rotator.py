from disnake.ext import tasks
import disnake
import asyncio

STATUS_TEXT = "💖 Zenyx System"


@tasks.loop(seconds=60)
async def status_rotator_task(bot: disnake.Client):
    """Mantém somente o status oficial da Zenyx em todos os bots."""
    await bot.change_presence(
        status=disnake.Status.online,
        activity=disnake.CustomActivity(name=STATUS_TEXT),
    )


@status_rotator_task.before_loop
async def before_status_rotator():
    # O loop é iniciado no on_ready; esta espera evita envio antes do login.
    await asyncio.sleep(1)
