import os
import json
import time
import secrets
import sqlite3
import logging
from pathlib import Path
from urllib.parse import urlencode

import aiohttp
from aiohttp import web
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("nadesmp")

TOKEN = os.getenv("DISCORD_TOKEN", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("REDIRECT_URI", "")
VERIFY_GUILD_ID = int(os.getenv("VERIFY_GUILD_ID", "1539199898430476328"))
DB_PATH = os.getenv("DATABASE_PATH", "data/bot.sqlite3")
PORT = int(os.getenv("PORT", "8080"))

Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("CREATE TABLE IF NOT EXISTS settings (guild_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT, PRIMARY KEY(guild_id,key))")
        con.execute("CREATE TABLE IF NOT EXISTS oauth_states (state TEXT PRIMARY KEY, user_id TEXT NOT NULL, created INTEGER NOT NULL)")
        con.execute("CREATE TABLE IF NOT EXISTS ticket_owners (channel_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, ticket_type TEXT NOT NULL)")

def get_setting(guild_id, key, default=None):
    with db() as con:
        row = con.execute("SELECT value FROM settings WHERE guild_id=? AND key=?", (str(guild_id), key)).fetchone()
    return row["value"] if row else default

def set_setting(guild_id, key, value):
    with db() as con:
        if value is None:
            con.execute("DELETE FROM settings WHERE guild_id=? AND key=?", (str(guild_id), key))
        else:
            con.execute("INSERT INTO settings(guild_id,key,value) VALUES(?,?,?) ON CONFLICT(guild_id,key) DO UPDATE SET value=excluded.value", (str(guild_id), key, str(value)))

def is_admin(interaction: discord.Interaction):
    return bool(interaction.guild and interaction.user.guild_permissions.administrator)

async def admin_check(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("Administrator permission is required.", ephemeral=True)
        return False
    return True

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

class NadeBot(commands.Bot):
    async def setup_hook(self):
        init_db()
        self.add_view(TicketPanelView())
        self.add_view(VerifyPanelView())
        self.add_view(TicketCloseView())
        await self.tree.sync()
        log.info("Slash commands synced.")

bot = NadeBot(command_prefix="!", intents=intents)

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for label, key, emoji in [
            ("Team Application", "team_application", "📋"),
            ("Developer Application", "developer_application", "💻"),
            ("Beta Tester Application", "beta_tester", "🧪"),
            ("Report", "report", "🚩"),
            ("Questions", "questions", "❓"),
        ]:
            self.add_item(TicketOpenButton(label, key, emoji))

class TicketOpenButton(discord.ui.Button):
    def __init__(self, label, key, emoji):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, emoji=emoji, custom_id=f"nadesmp:ticket:{key}")
        self.ticket_key = key

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
        category_id = get_setting(guild.id, "ticket_category")
        team_role_id = get_setting(guild.id, "team_role")
        if not category_id or not team_role_id:
            return await interaction.response.send_message("Ticket setup is incomplete. Ask an administrator to run /setup.", ephemeral=True)
        category = guild.get_channel(int(category_id))
        team_role = guild.get_role(int(team_role_id))
        if not isinstance(category, discord.CategoryChannel) or team_role is None:
            return await interaction.response.send_message("The configured ticket category or team role no longer exists.", ephemeral=True)
        existing = discord.utils.get(guild.text_channels, topic=f"ticket-owner:{interaction.user.id}")
        if existing:
            return await interaction.response.send_message(f"You already have an open ticket: {existing.mention}", ephemeral=True)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, read_message_history=True),
            team_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        safe_name = "".join(c.lower() if c.isalnum() else "-" for c in interaction.user.display_name).strip("-")[:18] or "member"
        channel = await guild.create_text_channel(
            name=f"{self.ticket_key[:12]}-{safe_name}",
            category=category,
            overwrites=overwrites,
            topic=f"ticket-owner:{interaction.user.id}"
        )
        with db() as con:
            con.execute("INSERT OR REPLACE INTO ticket_owners(channel_id,owner_id,ticket_type) VALUES(?,?,?)",
                        (str(channel.id), str(interaction.user.id), self.ticket_key))
        embed = discord.Embed(
            title=f"{self.ticket_key.replace('_',' ').title()}",
            description=f"Hello {interaction.user.mention}! Your ticket has been created. Please describe your request here.",
            color=discord.Color.blurple()
        )
        await channel.send(content=team_role.mention, embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"Your ticket has been created: {channel.mention}", ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="nadesmp:ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            return await interaction.response.send_message("This is not a valid ticket channel.", ephemeral=True)
        team_id = get_setting(interaction.guild.id, "team_role")
        is_team = team_id and any(r.id == int(team_id) for r in getattr(interaction.user, "roles", []))
        if not (is_team or interaction.user.guild_permissions.administrator):
            return await interaction.response.send_message("Only the team or an administrator can close this ticket.", ephemeral=True)
        await interaction.response.send_message("Ticket closed. Saving the log and deleting this channel...", ephemeral=True)
        log_id = get_setting(interaction.guild.id, "ticket_log")
        if log_id:
            log_channel = interaction.guild.get_channel(int(log_id))
            if isinstance(log_channel, discord.TextChannel):
                lines = []
                async for msg in interaction.channel.history(limit=100, oldest_first=True):
                    lines.append(f"[{msg.created_at.isoformat()}] {msg.author}: {msg.content}")
                transcript = "\n".join(lines) or "No text messages."
                await log_channel.send(
                    content=f"Ticket **{interaction.channel.name}** closed by {interaction.user.mention}.",
                    file=discord.File(fp=__import__("io").BytesIO(transcript.encode("utf-8")), filename=f"{interaction.channel.id}-transcript.txt")
                )
        with db() as con:
            con.execute("DELETE FROM ticket_owners WHERE channel_id=?", (str(interaction.channel.id),))
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")

class VerifyPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Join & Verify", style=discord.ButtonStyle.success, emoji="✓", custom_id="nadesmp:verify:start")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not CLIENT_ID or not REDIRECT_URI:
            return await interaction.response.send_message("Verification is not configured yet. Contact an administrator.", ephemeral=True)
        state = secrets.token_urlsafe(32)
        with db() as con:
            con.execute("INSERT INTO oauth_states(state,user_id,created) VALUES(?,?,?)", (state, str(interaction.user.id), int(time.time())))
        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "identify guilds.join",
            "state": state,
        }
        url = "https://discord.com/oauth2/authorize?" + urlencode(params)
        await interaction.response.send_message(f"[Continue with Discord]({url})", ephemeral=True)

@bot.tree.command(name="setup", description="Configure the ticket and verification system.")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(team_role="Role that can view and close tickets", ticket_category="Category where tickets are created", ticket_log="Channel for closed ticket transcripts", verify_role="Role given after OAuth verification", extra_role="Optional additional role after verification", remove_role="Optional role removed after verification")
async def setup_command(interaction: discord.Interaction, team_role: discord.Role, ticket_category: discord.CategoryChannel, ticket_log: discord.TextChannel, verify_role: discord.Role, extra_role: discord.Role = None, remove_role: discord.Role = None):
    if not await admin_check(interaction): return
    values = {
        "team_role": team_role.id,
        "ticket_category": ticket_category.id,
        "ticket_log": ticket_log.id,
        "verify_role": verify_role.id,
        "extra_role": extra_role.id if extra_role else None,
        "remove_role": remove_role.id if remove_role else None,
    }
    for key, value in values.items(): set_setting(interaction.guild.id, key, value)
    await interaction.response.send_message("Setup saved successfully.", ephemeral=True)

@bot.tree.command(name="panel-send", description="Send the support ticket panel.")
@app_commands.default_permissions(administrator=True)
async def panel_send(interaction: discord.Interaction):
    if not await admin_check(interaction): return
    embed = discord.Embed(title="NadeSMP Support", description="Choose the ticket category that best matches your request. A private channel will be created.", color=discord.Color.blurple())
    await interaction.channel.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message("Ticket panel sent.", ephemeral=True)

@bot.tree.command(name="verify-panel-send", description="Send the Discord account verification panel.")
@app_commands.default_permissions(administrator=True)
async def verify_panel_send(interaction: discord.Interaction):
    if not await admin_check(interaction): return
    embed = discord.Embed(title="Account Verification", description="Click below to securely join NadeSMP with Discord and receive your configured verification roles.", color=discord.Color.green())
    await interaction.channel.send(embed=embed, view=VerifyPanelView())
    await interaction.response.send_message("Verification panel sent.", ephemeral=True)

@bot.tree.command(name="welcome-system", description="Configure the welcome message.")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(channel="Channel for welcome messages", message="Message; placeholders: {user}, {username}, {server}", required_role="Only welcome members who have this role (optional)")
async def welcome_system(interaction: discord.Interaction, channel: discord.TextChannel, message: str, required_role: discord.Role = None):
    if not await admin_check(interaction): return
    set_setting(interaction.guild.id, "welcome_channel", channel.id)
    set_setting(interaction.guild.id, "welcome_message", message)
    set_setting(interaction.guild.id, "welcome_required_role", required_role.id if required_role else None)
    await interaction.response.send_message("Welcome system saved.", ephemeral=True)

@bot.event
async def on_member_join(member: discord.Member):
    channel_id = get_setting(member.guild.id, "welcome_channel")
    message = get_setting(member.guild.id, "welcome_message", "Welcome {user} to {server}!")
    required = get_setting(member.guild.id, "welcome_required_role")
    if not channel_id: return
    if required and not any(role.id == int(required) for role in member.roles): return
    channel = member.guild.get_channel(int(channel_id))
    if isinstance(channel, discord.TextChannel):
        text = message.replace("{user}", member.mention).replace("{username}", member.name).replace("{server}", member.guild.name)
        await channel.send(text)

async def oauth_start(request: web.Request):
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        return web.Response(text="Verification is not configured.", status=503)
    state = secrets.token_urlsafe(32)
    with db() as con:
        con.execute("INSERT INTO oauth_states(state,user_id,created) VALUES(?,?,?)", (state, "", int(time.time())))
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds.join",
        "state": state,
    }
    raise web.HTTPFound("https://discord.com/oauth2/authorize?" + urlencode(params))


async def oauth_callback(request: web.Request):
    if request.query.get("error"):
        return web.Response(text="Discord authorization was cancelled. You can close this page.", status=400)
    code, state = request.query.get("code"), request.query.get("state")
    if not code or not state:
        return web.Response(text="Missing OAuth code or state.", status=400)

    with db() as con:
        row = con.execute("SELECT user_id,created FROM oauth_states WHERE state=?", (state,)).fetchone()
        con.execute("DELETE FROM oauth_states WHERE state=?", (state,))
    if not row or int(time.time()) - int(row["created"]) > 600:
        return web.Response(text="This verification link is invalid or expired. Please start again.", status=400)

    token_data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            "https://discord.com/api/oauth2/token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        ) as response:
            token = await response.json()
            if response.status != 200:
                log.warning("OAuth token exchange failed with status %s", response.status)
                return web.Response(text="Discord authorization failed. Please try again.", status=502)

        access_token = token.get("access_token")
        if not access_token:
            return web.Response(text="Discord did not return an access token.", status=502)

        user_headers = {"Authorization": f"Bearer {access_token}"}
        async with session.get("https://discord.com/api/v10/users/@me", headers=user_headers) as response:
            user = await response.json()
            if response.status != 200 or not user.get("id"):
                return web.Response(text="Could not read your Discord account.", status=502)

        if row["user_id"] and str(row["user_id"]) != str(user["id"]):
            return web.Response(text="Please use the same Discord account that started verification.", status=403)
        if not TOKEN:
            return web.Response(text="The server bot is not configured.", status=503)

        join_url = f"https://discord.com/api/v10/guilds/{VERIFY_GUILD_ID}/members/{user['id']}"
        async with session.put(
            join_url,
            json={"access_token": access_token},
            headers={"Authorization": f"Bot {TOKEN}"}
        ) as response:
            if response.status not in (201, 204):
                details = await response.text()
                log.warning("Discord guild join failed (HTTP %s): %s", response.status, details[:500])
                return web.Response(text="NadeSMP could not add your account. Please contact the server team.", status=502)

    guild = bot.get_guild(VERIFY_GUILD_ID)
    if guild is None:
        return web.Response(text="The bot is not connected to the configured NadeSMP server.", status=503)
    try:
        member = await guild.fetch_member(int(user["id"]))
    except discord.NotFound:
        return web.Response(text="Discord added your account, but the bot could not find the server member yet. Please contact staff.", status=502)
    except discord.HTTPException:
        log.exception("Could not fetch newly joined member")
        return web.Response(text="Could not finish verification. Please contact staff.", status=502)

    roles_to_add = []
    for role_id in (get_setting(guild.id, "verify_role"), get_setting(guild.id, "extra_role")):
        if role_id:
            role = guild.get_role(int(role_id))
            if role and role not in member.roles:
                roles_to_add.append(role)
    remove_id = get_setting(guild.id, "remove_role")
    role_to_remove = guild.get_role(int(remove_id)) if remove_id else None

    try:
        if roles_to_add:
            await member.add_roles(*roles_to_add, reason="NadeSMP website OAuth verification")
        if role_to_remove and role_to_remove in member.roles:
            await member.remove_roles(role_to_remove, reason="NadeSMP website OAuth verification")
    except discord.Forbidden:
        log.exception("Bot lacks permission or role hierarchy for verification roles")
        return web.Response(text="You joined NadeSMP, but the bot could not assign your roles. Please contact staff.", status=502)
    except discord.HTTPException:
        log.exception("Role assignment failed")
        return web.Response(text="You joined NadeSMP, but role assignment failed. Please contact staff.", status=502)

    return web.Response(
        text="""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NadeSMP Verification</title><style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#10131d;color:#f4f6fb;font:16px Arial,sans-serif;padding:24px}
main{max-width:480px;text-align:center;background:#171c29;border:1px solid #ffffff20;border-radius:18px;padding:42px 32px}
.mark{margin:auto auto 22px;width:58px;height:58px;border-radius:18px;background:#a6e86b;color:#10131d;display:grid;place-items:center;font-size:30px;font-weight:bold}
h1{margin:0 0 12px}p{color:#a4adbf;line-height:1.7}a{display:inline-block;margin-top:18px;padding:13px 18px;background:#a6e86b;color:#10131d;text-decoration:none;border-radius:8px;font-weight:bold}
</style></head><body><main><div class="mark">✓</div><h1>You're in!</h1><p>Your Discord account has been added to NadeSMP and your verification roles have been processed. You can return to Discord now.</p><a href="https://discord.com/channels/1539199898430476328">Open Discord</a></main></body></html>""",
        content_type="text/html"
    )


async def health(request):
    return web.json_response({"ok": True, "service": "NadeSMP Discord bot"})

async def website_index(request):
    index_file = Path(__file__).resolve().parent / "website" / "index.html"
    if not index_file.is_file():
        return web.Response(text="NadeSMP website files are missing.", status=500)
    return web.FileResponse(index_file)

async def website_style(request):
    asset = Path(__file__).resolve().parent / "website" / "style.css"
    if not asset.is_file():
        return web.Response(text="Website stylesheet not found.", status=404)
    return web.FileResponse(asset)

async def website_script(request):
    asset = Path(__file__).resolve().parent / "website" / "script.js"
    if not asset.is_file():
        return web.Response(text="Website script not found.", status=404)
    return web.FileResponse(asset)

async def start_web():
    app = web.Application()
    app.router.add_get("/oauth/start", oauth_start)
    app.router.add_get("/oauth/callback", oauth_callback)
    app.router.add_get("/health", health)
    app.router.add_get("/", website_index)
    app.router.add_get("/style.css", website_style)
    app.router.add_get("/script.js", website_script)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    return runner

async def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN is missing.")
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        log.warning("OAuth variables are incomplete; verification will not work until configured.")
    runner = await start_web()
    try:
        await bot.start(TOKEN)
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
