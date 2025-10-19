import os, logging, asyncio
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
from aiohttp import web
import random

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
MOD_ROLE_NAME_DEFAULT = os.getenv("MOD_ROLE_NAME", "Crew")
PORT = int(os.getenv("PORT", "10000"))
ASSIGNEE_NAME = os.getenv("ASSIGNEE_NAME", "Tolga")
try:
    ASSIGNEE_USER_ID = int(os.getenv("ASSIGNEE_USER_ID", "0"))
except ValueError:
    ASSIGNEE_USER_ID = 0

intents = discord.Intents.default()
intents.members = True
intents.message_content = False

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.mod_role_name = MOD_ROLE_NAME_DEFAULT
        self.assignee_name = ASSIGNEE_NAME
        self.assignee_user_id = ASSIGNEE_USER_ID

    async def setup_hook(self):
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

bot = Bot()

async def get_or_create_role(guild, name, **kwargs):
    r = discord.utils.get(guild.roles, name=name)
    return r or await guild.create_role(name=name, **kwargs)

async def get_or_create_category(guild, name):
    c = discord.utils.get(guild.categories, name=name)
    return c or await guild.create_category(name)

async def get_or_create_text(guild, name, category=None, overwrites=None):
    ch = (discord.utils.get(category.channels, name=name) if category else
          discord.utils.get(guild.text_channels, name=name))
    return ch or await guild.create_text_channel(name, category=category, overwrites=overwrites)

async def get_or_create_voice(guild, name, category=None, overwrites=None):
    ch = (discord.utils.get(category.channels, name=name) if category else
          discord.utils.get(guild.voice_channels, name=name))
    return ch or await guild.create_voice_channel(name, category=category, overwrites=overwrites)

@bot.event
async def on_ready():
    logging.info(f"✅ Eingeloggt als {bot.user} (ID: {bot.user.id})")

@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild

    # 1) Auto-Rolle "Smash" vergeben
    smash = discord.utils.get(guild.roles, name="Smash")
    if smash:
        try:
            await member.add_roles(smash, reason="Auto-Join-Rolle")
        except discord.Forbidden:
            # Falls die Bot-Rolle unter "Smash" steht oder keine Rechte hat, kann er nicht zuweisen.
            pass

    # 2) Willkommenskanal suchen
    ch = discord.utils.get(guild.text_channels, name="👋-willkommen")
    if not ch:
        return  # Wenn der Kanal anders heißt, einfach nichts senden (kein Fehler)

    # 3) Begrüßungstexte 
    greetings = [
            # Pipe Bomb/Eigene Sachen?
        f"\"Woah Pipe Bomb\" — äh… willkommen {member.mention}!",
        f"\ "Was geht du Loser\" - setz dich hin und gib ruhe {member.mention}!",
    ]

    # 4) Zufällig eine Nachricht auswählen und senden
    msg = random.choice(greetings)
    await ch.send(msg)

@bot.tree.command(name="bootstrap", description="Erstellt Rollen, Kategorien, Kanäle & setzt AFK/Willkommen.")
@app_commands.default_permissions(administrator=True)
async def bootstrap(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)
    guild = interaction.guild

    admin = await get_or_create_role(guild, "Admin", permissions=discord.Permissions(administrator=True))
    mod = await get_or_create_role(guild, bot.mod_role_name)

    cat_info = await get_or_create_category(guild, "📚 Info")
    cat_text = await get_or_create_category(guild, "💬 Text")
    cat_voice = await get_or_create_category(guild, "🎧 Voice")
    cat_support = await get_or_create_category(guild, "🛠 Support")
    cat_staff = await get_or_create_category(guild, "🛡 Team")

    everyone = guild.default_role
    read_only = {everyone: discord.PermissionOverwrite(read_messages=True, send_messages=False)}
    public = {everyone: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
    staff_only = {
        everyone: discord.PermissionOverwrite(read_messages=False),
        admin: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        mod: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }

    await get_or_create_text(guild, "👋-willkommen", cat_info, read_only)
    await get_or_create_text(guild, "💬-allgemein", cat_text, public)
    await get_or_create_text(guild, "🔗-links", cat_text, public)
    await get_or_create_text(guild, "🤣-memes", cat_text, public)
    await get_or_create_text(guild, "🐾-flauschis", cat_text, public)
    await get_or_create_text(guild, "🎫-tickets", cat_support, public)
    await get_or_create_text(guild, "🔒-log", cat_staff, staff_only)

    await get_or_create_voice(guild, "Lobby", cat_voice)
    await get_or_create_voice(guild, "Bierzelt", cat_voice)
    await get_or_create_voice(guild, "White Noice VC", cat_voice)

    u_haft = await get_or_create_voice(
        guild, "U-Haft", cat_voice, overwrites={everyone: discord.PermissionOverwrite(connect=True, speak=False)}
    )
    try:
        await guild.edit(afk_channel=u_haft, afk_timeout=15*60)
    except discord.Forbidden:
        pass

    try:
        await guild.me.edit(nick="Hatsune Miku")
    except discord.Forbidden:
        pass

    await interaction.followup.send("Fertig! ✅ Struktur & AFK gesetzt. (Fehlt was? Bot-Rechte prüfen.)", ephemeral=True)

@bot.tree.command(name="ticket", description="Privater Support-Channel (statt DM).")
async def ticket(interaction: discord.Interaction, thema: str):
    guild = interaction.guild
    admin = discord.utils.get(guild.roles, name="Admin")
    mod = discord.utils.get(guild.roles, name=bot.mod_role_name)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
    }
    if admin:
        overwrites[admin] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
    if mod:
        overwrites[mod] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    cat = discord.utils.get(guild.categories, name="🛠 Support")
    ch = await guild.create_text_channel(f"ticket-{interaction.user.name}".lower(),
                                         category=cat, overwrites=overwrites, reason="Neues Ticket")

    mention = ""
    if bot.assignee_user_id:
        user = guild.get_member(bot.assignee_user_id)
        if user:
            mention = f"{user.mention} "

    await ch.send(
        f"Hey {interaction.user.mention}! **Miku** hat dein Ticket an **{bot.assignee_name}** weitergeleitet. "
        f"{mention}Bitte beschreibe dein Problem (Thema: **{thema}**)."
    )
    log = discord.utils.get(guild.text_channels, name="🔒-log")
    if log:
        await log.send(f"📨 Neues Ticket {ch.mention} von {interaction.user.mention} → an **{bot.assignee_name}** weitergeleitet.")

    await interaction.response.send_message(f"Ticket erstellt: {ch.mention}", ephemeral=True)

@bot.tree.command(name="close_ticket", description="Schließt (löscht) das aktuelle Ticket.")
@app_commands.checks.has_any_role("Admin", MOD_ROLE_NAME_DEFAULT)
async def close_ticket(interaction: discord.Interaction):
    ch = interaction.channel
    if not isinstance(ch, discord.TextChannel) or not ch.name.startswith("ticket-"):
        return await interaction.response.send_message("Nur in Ticket-Kanälen nutzbar.", ephemeral=True)
    await interaction.response.send_message("Ticket wird geschlossen…", ephemeral=True)
    await ch.delete(reason="Ticket geschlossen")

@bot.tree.command(name="set_mod_role", description="Setzt/erstellt den Namen der Mod-Rolle.")
@app_commands.default_permissions(administrator=True)
async def set_mod_role(interaction: discord.Interaction, name: str):
    bot.mod_role_name = name
    if not discord.utils.get(interaction.guild.roles, name=name):
        await interaction.guild.create_role(name=name, reason="Mod-Rolle erstellt")
    await interaction.response.send_message(f"Mod-Rolle ist jetzt **{name}**. ✅", ephemeral=True)

@bot.tree.command(name="set_assignee", description="Setzt den angezeigten Namen des Ticket-Empfängers (z. B. Tolga).")
@app_commands.default_permissions(administrator=True)
async def set_assignee(interaction: discord.Interaction, name: str):
    bot.assignee_name = name
    await interaction.response.send_message(f"Assignee-Name ist jetzt **{name}**. ✅", ephemeral=True)

@bot.tree.command(name="set_assignee_ping", description="Setzt die User-ID für @Mention (0 = deaktivieren).")
@app_commands.default_permissions(administrator=True)
async def set_assignee_ping(interaction: discord.Interaction, user_id: str):
    try:
        bot.assignee_user_id = int(user_id)
        if bot.assignee_user_id == 0:
            msg = "Assignee-Ping ist deaktiviert."
        else:
            member = interaction.guild.get_member(bot.assignee_user_id)
            tag = member.mention if member else f"`{bot.assignee_user_id}`"
            msg = f"Assignee-Ping aktiv: {tag}"
        await interaction.response.send_message(msg + " ✅", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("Bitte eine gültige numerische User-ID angeben (oder 0).", ephemeral=True)

async def handle_health(request): return web.Response(text="ok")
async def start_web_app():
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT); await site.start()
async def keepalive():
    import aiohttp, asyncio
    url = "https://hatsune-miku-bot-dc.onrender.com/health" 
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    await resp.text()
        except Exception:
            pass
        await asyncio.sleep(120)  # ping alle 2 Minuten

async def main():
    await start_web_app()
    asyncio.create_task(keepalive())  # Keepalive-Task starten
    await bot.start(TOKEN)

if __name__ == "__main__":
    if not TOKEN or not GUILD_ID:
        raise SystemExit("Bitte DISCORD_TOKEN & GUILD_ID setzen.")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
