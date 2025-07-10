# GitHub Upload & Railway Connection Steps

## Step 1: Create GitHub Repository
1. Go to [github.com](https://github.com) and sign in
2. Click the green "New" button (top left)
3. Repository name: `telegram-gaming-bot` (or any name you prefer)
4. Set to **Public** (required for Railway free tier)
5. ✅ Check "Add a README file"
6. Click "Create repository"

## Step 2: Upload Bot Files
You need to upload these 3 files to your GitHub repo:

### Files to Upload:
1. **`railway_bot.py`** - The main bot file (already created)
2. **`railway.json`** - Railway configuration (already created)  
3. **`pyproject.toml`** - Python dependencies (already exists in this project)

### Upload Method:
1. In your new GitHub repo, click "uploading an existing file"
2. Drag and drop these 3 files:
   - `railway_bot.py`
   - `railway.json`
   - `pyproject.toml`
3. Scroll down, add commit message: "Add telegram gaming bot files"
4. Click "Commit changes"

## Step 3: Connect Railway to GitHub
1. In Railway dashboard, click "New Project"
2. Select "Deploy from GitHub repo"
3. Click "Configure GitHub App" if needed
4. Choose your `telegram-gaming-bot` repository
5. Click "Deploy Now"

## Step 4: Verify Deployment
1. Railway will automatically:
   - Detect `railway.json` configuration
   - Install Python dependencies from `pyproject.toml`
   - Start the bot with `python railway_bot.py`
   - Set up health monitoring on `/health` endpoint

2. Watch the "Deployments" tab for:
   - ✅ Build successful
   - ✅ Deploy successful
   - ✅ Health check passing

## Step 5: Check Bot is Live
1. Go to Telegram
2. Search for your bot username (from BotFather)
3. Send `/start`
4. Should get the welcome message immediately
5. Test a multiplayer game with a friend

## Step 6: Monitor (Optional)
- Railway dashboard shows real-time logs
- Health endpoint: `https://your-app.railway.app/health`
- Bot automatically restarts if any issues occur

## Troubleshooting:
- **Build failed**: Check files uploaded correctly
- **Deploy failed**: Verify BOT_TOKEN environment variable is set
- **Bot not responding**: Double-check the bot token format

Your bot will be live at: `t.me/yourbotusername`

**Deployment complete! Your bot runs 24/7 independently.**