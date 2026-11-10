# NadeSMP System

Discord bot and static website for the NadeSMP community.

## Repository layout

- `main.py` — Discord bot, ticket system, welcome system and OAuth2 membership check
- `website/` — standalone static website (HTML, CSS and JavaScript)
- `requirements.txt` — Python dependencies
- `Procfile` — Railway start command

## Railway deployment

1. Create a Railway project from this GitHub repository.
2. Add the variables listed below.
3. Add a Railway Volume mounted at `/app/data` so the SQLite database persists.
4. Deploy with the start command from the Procfile: `python main.py`.
5. In the Discord Developer Portal, add the exact `REDIRECT_URI` value to OAuth2 Redirects.
6. Enable **Server Members Intent** in the Bot settings.
7. Invite the bot with the permissions it needs: Manage Roles, Manage Channels, View Channels, Send Messages, Embed Links and Read Message History. Place the bot's highest role above the roles it must assign/remove.

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

The verification flow requests only `identify` and `guilds`. It checks whether the authorizing Discord account is already a member of guild `1539199898430476328`, then assigns configured roles. It does not add users to the server and does not request the `guilds.join` scope.

## Website

Deploy `website/` as a separate static Vercel project. See [website/README.md](website/README.md).
