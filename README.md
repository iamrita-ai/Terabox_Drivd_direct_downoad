# Serena Unzip/Downloader Bot (Render)

Telegram bot scaffold for:
- Force-sub channel gate
- MongoDB (users, premium, settings later)
- Task queue + cancel framework
- Render port detection fix via Flask web service

## Environment Variables (Render)
Required:
- API_ID
- API_HASH
- BOT_TOKEN
- MONGO_URI

Optional:
- START_PIC (photo URL or file_id)
- FORCE_SUB_CHANNEL (default: @serenaunzipbot)
- OWNER_CONTACT_URL (default: https://t.me/technicalserena)
- OWNER_CONTACT_USERNAME (default: @Xioqui_xin)

## Deploy (Render)
Use Dockerfile. Create a **Web Service**.
Start command is handled by Dockerfile (runs `python app.py`).
