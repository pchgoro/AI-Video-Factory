# CosmicVideoFactory Public Website

This is a minimal static site for TikTok Developer Portal review fields.

Pages:

- `/` - application overview
- `/terms` - Terms of Service
- `/privacy` - Privacy Policy

It does not use a database, API, login, tracking, or personal information form.

## Local check

Open `index.html` directly in a browser, or serve the folder:

```powershell
cd C:\Users\goroo\Desktop\CosmicVideoFactory\website
python -m http.server 8080
```

Then open:

- `http://localhost:8080/`
- `http://localhost:8080/terms.html`
- `http://localhost:8080/privacy.html`

## Vercel deployment

Set the Vercel project root to this `website/` directory.

Example:

```powershell
cd C:\Users\goroo\Desktop\CosmicVideoFactory\website
vercel
vercel --prod
```

After deployment, use the production domain in TikTok Developer Portal:

- Web/Desktop URL: `https://your-vercel-domain.vercel.app/`
- Terms of Service URL: `https://your-vercel-domain.vercel.app/terms`
- Privacy Policy URL: `https://your-vercel-domain.vercel.app/privacy`
