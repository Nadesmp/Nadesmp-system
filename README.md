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
OAUTH_TOKEN_ENCRYPTION_KEY=GENERATE_A_FERNET_KEY
```

Generate `OAUTH_TOKEN_ENCRYPTION_KEY` once with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and save the result as a Railway Variable. Keep the same key permanently: changing it makes previously stored authorizations unreadable. Do not commit your real `.env`, encryption key, bot token or OAuth2 client secret.

## Discord commands

All commands require Administrator permission:

- `/setup` — configure team role, ticket category, ticket log, verification role and optional role changes
- `/panel-send` — post the ticket panel
- `/verify-panel-send` — post the OAuth2 verification panel
- `/welcome-system` — configure the welcome channel, message and optional role automatically assigned to new members
- `/pull` — add all users whose OAuth2 refresh authorization has been securely saved and assign their verification roles

Welcome message placeholders: `{user}`, `{username}`, `{server}`.

## OAuth2 behavior

The website route `/oauth/start` requests `identify` and `guilds.join`. After the user approves the Discord consent screen, the callback exchanges the authorization code and uses Discord's Add Guild Member endpoint to add the user to guild `1539199898430476328`. The bot then assigns the configured verification and extra roles and optionally removes the configured role. The Discord bot must be in the target server and have `Create Invite`; role assignment also requires `Manage Roles` and a role hierarchy that allows the bot to manage those roles. After a successful OAuth2 join, the app stores the user's refresh token encrypted with `OAUTH_TOKEN_ENCRYPTION_KEY`. The administrator can run `/pull` to re-add users who previously authorized the app but are not currently in the guild. Users who completed verification before persistent token storage was deployed must authorize once again before they can be included in `/pull`. The `/verify-panel-send` button uses the same OAuth flow but binds the authorization to the Discord account that clicked it.

## Website

The verification website is served by the bot at `/`. Its **Continue with Discord** button starts OAuth2 at `/oauth/start`. Use the same Railway domain for `REDIRECT_URI`, ending in `/oauth/callback`.
