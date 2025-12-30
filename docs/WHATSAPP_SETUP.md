# WhatsApp Integration Setup Guide

This guide walks you through connecting your Meta WhatsApp Business account to Yume.

## Prerequisites

- A Meta Business account
- A WhatsApp Business Platform account
- A phone number to use for WhatsApp Business (cannot be a personal WhatsApp number)
- Your backend server accessible via HTTPS (use ngrok for local testing)

## Step 1: Get Your Meta Credentials

### 1.1 Meta App ID and Secret

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Navigate to **My Apps** → Select your app (or create a new one)
3. Go to **Settings** → **Basic**
4. Copy your **App ID** → This is your `META_APP_ID`
5. Click **Show** next to **App Secret** → This is your `META_APP_SECRET`

### 1.2 WhatsApp Access Token

1. In your Meta app, go to **WhatsApp** → **Getting Started**
2. Under **Temporary access token**, click **Copy**
   - ⚠️ This token expires in 24 hours - for production, generate a permanent token:
     - Go to **Business Settings** → **System Users**
     - Create a system user
     - Assign WhatsApp permissions
     - Generate a permanent token
3. Copy the token → This is your `META_ACCESS_TOKEN`

### 1.3 Phone Number ID

1. In **WhatsApp** → **Getting Started**
2. Under **From**, you'll see a test phone number
3. Click on it to see the **Phone number ID** (looks like `123456789012345`)
4. Save this - you'll need it when testing

## Step 2: Configure Webhook

### 2.1 Generate Verify Token

Create a secure random string for your webhook verify token:

```bash
# Generate a random token
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Save this as your `META_WEBHOOK_VERIFY_TOKEN`.

### 2.2 Expose Your Local Server (Development)

If testing locally, use ngrok to create a public URL:

```bash
# Install ngrok (if not already)
brew install ngrok  # macOS
# or download from https://ngrok.com/download

# Expose port 8000
ngrok http 8000
```

You'll get a URL like: `https://abc123.ngrok.io`

### 2.3 Register Webhook with Meta

1. In your Meta app, go to **WhatsApp** → **Configuration**
2. In the **Webhook** section, click **Edit**
3. Enter your webhook URL:
   - **Callback URL**: `https://your-domain.com/api/v1/webhooks/whatsapp`
   - For ngrok: `https://abc123.ngrok.io/api/v1/webhooks/whatsapp`
4. Enter your **Verify Token**: Use the `META_WEBHOOK_VERIFY_TOKEN` you generated
5. Click **Verify and Save**

✅ You should see "Webhook verified successfully"

### 2.4 Subscribe to Webhook Events

1. Still in **WhatsApp** → **Configuration**
2. Click **Manage** next to **Webhook fields**
3. Subscribe to: **messages**
4. Click **Save**

## Step 3: Configure Yume Backend

Update your `.env` file with all credentials:

```bash
# Meta WhatsApp
META_APP_ID=your-app-id-here
META_APP_SECRET=your-app-secret-here
META_WEBHOOK_VERIFY_TOKEN=your-generated-verify-token
META_ACCESS_TOKEN=your-whatsapp-access-token
META_API_VERSION=v18.0

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

In Meta Developer Console:

1. Go to **WhatsApp** → **API Setup**
2. Under **Send and receive messages**, select a test number
3. Send a test message: "Hola"

### 5.2 Check Backend Logs

You should see:
```
📬 Webhook received: whatsapp_business_account
Processing entry: 123456789
✅ WhatsApp client in REAL mode
```

### 5.3 Verify Response

The test number should receive a response from your AI assistant!

## Step 6: Add Your Business Data

Before real customer conversations work, add your organization data:

### 6.1 Create Organization

```bash
# Use API or create via database
curl -X POST "http://localhost:8000/api/v1/organizations" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Mi Barbería",
    "phone_number": "+525512345678",
    "phone_number_id": "your-phone-number-id-from-meta",
    "timezone": "America/Mexico_City"
  }'
```

### 6.2 Add Location

```bash
curl -X POST "http://localhost:8000/api/v1/organizations/{org_id}/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sucursal Centro",
    "address": "Av. Reforma 123, CDMX"
  }'
```

### 6.3 Add Staff Members

```bash
curl -X POST "http://localhost:8000/api/v1/organizations/{org_id}/staff" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Juan Pérez",
    "phone_number": "+525598765432",
    "role": "owner",
    "is_owner": true
  }'
```

### 6.4 Add Service Types

```bash
curl -X POST "http://localhost:8000/api/v1/organizations/{org_id}/service-types" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Corte de Cabello",
    "duration_minutes": 30,
    "price": 150.00
  }'
```

### 6.5 Add Spots (Service Stations)

```bash
curl -X POST "http://localhost:8000/api/v1/organizations/{org_id}/spots" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Silla 1",
    "location_id": "{location_id}"
  }'
```

### 6.6 Set Staff Availability

```bash
curl -X POST "http://localhost:8000/api/v1/organizations/{org_id}/staff/{staff_id}/availability" \
  -H "Content-Type: application/json" \
  -d '{
    "day_of_week": 1,
    "start_time": "09:00:00",
    "end_time": "18:00:00",
    "is_available": true
  }'
```

## Common Issues

### Webhook Verification Fails

- ❌ **"Invalid verify token"**: Check that `META_WEBHOOK_VERIFY_TOKEN` in `.env` matches what you entered in Meta
- ❌ **"Cannot reach callback URL"**: Make sure your server is running and accessible (check ngrok URL)
- ❌ **403 Forbidden**: Your webhook endpoint might be blocking the request

### Messages Not Being Received

- Check webhook subscriptions (must include `messages`)
- Verify `phone_number_id` in your organization matches Meta's phone number ID
- Check backend logs for errors

### Messages Not Being Sent

- ❌ **"Invalid access token"**: Generate a new permanent token from system user
- ❌ **"Recipient phone number not registered"**: In test mode, only test numbers can receive messages
- Check that `META_ACCESS_TOKEN` is set correctly in `.env`

### Mock Mode Still Active

If logs show "🔧 WhatsApp client in MOCK mode":
- Verify `META_ACCESS_TOKEN` is set in your `.env` file
- Restart the server after updating `.env`
- Check that `.env` is being loaded (try `echo $META_ACCESS_TOKEN` after sourcing)

## Production Deployment

### Generate Permanent Access Token

1. Go to **Business Settings** → **System Users**
2. Create a new system user or select existing
3. Click **Generate New Token**
4. Select your WhatsApp app
5. Assign permissions: `whatsapp_business_messaging`
6. Copy and save this token securely - it doesn't expire!

### Use HTTPS

- WhatsApp webhooks REQUIRE HTTPS in production
- Use proper SSL certificates (Let's Encrypt, Cloudflare, etc.)
- Update `APP_BASE_URL` in `.env` to your production domain

### Update Webhook URL

1. Update callback URL in Meta to production domain
2. Re-verify webhook
3. Test with a real message

## Next Steps

- Set up message templates for notifications
- Configure business hours and holidays
- Add more service types and staff
- Test full booking flow
- Monitor logs and webhook reliability

## Resources

- [Meta WhatsApp Cloud API Docs](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [Webhook Setup Guide](https://developers.facebook.com/docs/graph-api/webhooks/getting-started)
- [WhatsApp Business Platform](https://business.whatsapp.com/)
