# NadeSMP System

Discord bot and Discord OAuth2 verification website for the NadeSMP community.

## Repository layout

- `main.py` — Discord bot, ticket system, welcome system and OAuth2 join/verification flow
- `website/` — verification website served directly by the Railway app
- `requirements.txt` — Python dependencies
- `Procfile` — Railway start command

## Railway deployment

1. Create a Railway project from this GitHub repository.
2. Add the variables listed below.
3. Add a Railway Volume mounted at `/app/data` so the SQLite database persists.
4. Deploy with the start command from the Procfile: `python main.py`.
5. In the Discord Developer Portal, add the exact `REDIRECT_URI` value to OAuth2 Redirects.
6. Enable **Server Members Intent** in the Bot settings.
7. Invite the bot with **Create Invite**, **Manage Roles**, **Manage Channels**, **View Channels**, **Send Messages**, **Embed Links** and **Read Message History**. Place the bot's highest role above the roles it must assign/remove.

### Railway Variables

```env
DISCORD_TOKEN=YOUR_BOT_TOKEN
CLIENT_ID=YOUR_APPLICATION_ID
CLIENT_SECRET=YOUR_OAUTH2_CLIENT_SECRET
REDIRECT_URI=https://YOUR-RAILWAY-DOMAIN.up.railway.app/oauth/callback
VERIFY_GUILD_ID=1539199898430476328
DATABASE_PATH=/app/data/bot.sqlite3
LOG_LEVEL=INFO
```

Do not commit your real `.env`, bot token or OAuth2 client secret.

## Discord commands

All commands require Administrator permission:

- `/setup` — configure team role, ticket category, ticket log, verification role and optional role changes
- `/panel-send` — post the ticket panel
- `/verify-panel-send` — post the OAuth2 verification panel
- `/welcome-system` — configure the welcome channel and message

Welcome message placeholders: `{user}`, `{username}`, `{server}`.

## OAuth2 behavior

The website route `/oauth/start` requests `identify` and `guilds.join`. After the user approves the Discord consent screen, the callback exchanges the authorization code and uses Discord's Add Guild Member endpoint to add the user to guild `1539199898430476328`. The bot then assigns the configured verification and extra roles and optionally removes the configured role. The Discord bot must be in the target server and have `Create Invite`; role assignment also requires `Manage Roles` and a role hierarchy that allows the bot to manage those roles. The `/verify-panel-send` button uses the same OAuth flow but binds the authorization to the Discord account that clicked it.

## Website

The verification website is served by the bot at `/`. Its **Continue with Discord** button starts OAuth2 at `/oauth/start`. Use the same Railway domain for `REDIRECT_URI`, ending in `/oauth/callback`.
