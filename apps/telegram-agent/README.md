# EXAMSHIELD Telegram Agent

Tiny listener for a Telegram bot, private chat, group, supergroup, or channel.

## Environment

```txt
TELEGRAM_BOT_TOKEN=123456:bot-token
EXAMSHIELD_WEB_URL=http://localhost:3000
TELEGRAM_CHAT_ID=-1001234567890
```

`TELEGRAM_CHAT_ID` is optional. If it is set, make sure it is the group or supergroup chat id, not the bot private chat id; otherwise group messages will be skipped by design.

## Run

```txt
npm start
```

On startup the agent clears any Telegram webhook without dropping pending updates, then uses long polling for `message`, `edited_message`, `channel_post`, and `edited_channel_post` updates. This lets a privacy-disabled bot receive normal group messages and media instead of only command messages.

The agent only listens to Telegram and forwards events to EXAMSHIELD. OCR, attribution, reports, and alerts remain inside the existing web pipeline.
