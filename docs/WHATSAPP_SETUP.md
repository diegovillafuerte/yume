# WhatsApp Integration Setup Guide (Twilio)

This guide walks you through setting up WhatsApp integration for Yume using Twilio.

## Prerequisites

- A Twilio account with WhatsApp capability
- Your backend server accessible via HTTPS (use ngrok for local testing)

## Step 1: Get Your Twilio Credentials

### 1.1 Account SID and Auth Token

1. Go to [Twilio Console](https://console.twilio.com/)
2. Find your **Account SID** and **Auth Token** on the dashboard
3. Copy these values → `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`

### 1.2 WhatsApp Sandbox (Development)

For development, use the Twilio WhatsApp Sandbox:

1. Go to **Messaging** → **Try it out** → **Send a WhatsApp message**
2. Follow the instructions to join the sandbox (send a message to the sandbox number)
3. Copy the sandbox number (e.g., `+14155238886`) → `TWILIO_WHATSAPP_NUMBER`

### 1.3 WhatsApp Number (Production)

For production, you'll need a dedicated WhatsApp Business number:

1. Go to **Messaging** → **Senders** → **WhatsApp senders**
2. Request a new WhatsApp number or port an existing one
3. Follow Meta's verification process

## Step 2: Configure Webhook

### 2.1 Expose Your Local Server (Development)

If testing locally, use ngrok to create a public URL:

```bash
# Install ngrok (if not already)
brew install ngrok  # macOS
# or download from https://ngrok.com/download

# Expose port 8000
ngrok http 8000
```

You'll get a URL like: `https://abc123.ngrok.io`

### 2.2 Configure Twilio Webhook

1. Go to **Messaging** → **Settings** → **WhatsApp Sandbox settings** (or your number's settings in production)
2. Set the webhook URL:
   - **When a message comes in**: `https://your-domain.com/api/v1/webhooks/whatsapp`
   - For ngrok: `https://abc123.ngrok.io/api/v1/webhooks/whatsapp`
3. Set HTTP method to **POST**
4. Save the configuration

## Step 3: Configure Yume Backend

Update your `.env` file with all credentials:

```bash
# Twilio WhatsApp
TWILIO_ACCOUNT_SID=your-account-sid-here
TWILIO_AUTH_TOKEN=your-auth-token-here
TWILIO_WHATSAPP_NUMBER=+14155238886  # Your Twilio WhatsApp number

# OpenAI (for AI conversations)
OPENAI_API_KEY=sk-your-openai-key

# Database & other settings...
```

## Step 4: Start Your Backend

```bash
# Make sure Docker containers are running
docker-compose up -d

# Activate virtualenv
source .venv/bin/activate

# Run migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload
```

Check logs - you should see:
```
✅ WhatsApp client in REAL mode
INFO:     Application startup complete.
```

## Step 5: Test the Integration

### 5.1 Send a Test Message

1. Open WhatsApp on your phone
2. Send a message to the Twilio sandbox/production number
3. You should receive a response from Yume

### 5.2 Check Backend Logs

You should see:
```
📬 TWILIO WEBHOOK RECEIVED
  MessageSid: SM...
  From: whatsapp:+521234567890
  To: whatsapp:+14155238886
  Body: Hola
```

### 5.3 Verify Response

You should receive a WhatsApp reply from Yume's AI assistant.

## Common Issues

### Webhook Not Receiving Messages

- ❌ **Webhook URL not accessible**: Make sure ngrok is running and URL is correct
- ❌ **Wrong HTTP method**: Twilio sends POST requests
- ❌ **Sandbox not joined**: You must send the join message first (development only)

### Messages Not Being Sent

- ❌ **Invalid credentials**: Check `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`
- ❌ **Number format**: Ensure phone numbers include country code with +
- ❌ **24-hour window**: WhatsApp requires templates for messages outside the 24-hour window

### Mock Mode Active

If logs show "🔧 WhatsApp client in MOCK mode":
- Verify `TWILIO_ACCOUNT_SID` is set in your `.env` file
- Restart the server after updating `.env`

## Production Deployment

### Use HTTPS

- Twilio webhooks REQUIRE HTTPS in production
- Use proper SSL certificates (Let's Encrypt, Cloudflare, etc.)
- Update `APP_BASE_URL` in `.env` to your production domain

### Update Webhook URL

1. Update callback URL in Twilio Console to production domain
2. Test with a real message

### Number Provisioning

For production, businesses can have dedicated WhatsApp numbers provisioned through the onboarding flow. This is handled automatically by Yume's Twilio provisioning service.

## Next Steps

- Set up message templates for notifications (requires Twilio Content Templates)
- Configure business hours and holidays
- Test full booking flow
- Monitor logs and webhook reliability

## Resources

- [Twilio WhatsApp API Docs](https://www.twilio.com/docs/whatsapp)
- [Twilio WhatsApp Sandbox](https://www.twilio.com/docs/whatsapp/sandbox)
- [Twilio Content Templates](https://www.twilio.com/docs/content)
