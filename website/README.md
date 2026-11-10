# NadeSMP Verification Website

This folder contains the verification page served by the Python application:

- `index.html` — Discord OAuth2 verification page
- `style.css` — responsive styling
- `script.js` — page year

## Hosting

The website is served by `main.py` on the same Railway domain as the Discord bot. Do not deploy this folder as a separate static site for the OAuth flow, because the `/oauth/start` and `/oauth/callback` routes must be handled by the Python application.

Set the Railway variable `REDIRECT_URI` to:

```text
https://YOUR-RAILWAY-DOMAIN.up.railway.app/oauth/callback
```

Add that exact URL to the OAuth2 Redirects list in the Discord Developer Portal.
