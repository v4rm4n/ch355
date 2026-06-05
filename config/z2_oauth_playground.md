To get a real, cryptographically signed Google id_token to test your backend right now, we use a tool built exactly for backend developers: the Google OAuth 2.0 Playground.

However, because your backend securely verifies that the token was minted specifically for your game, we have to tell the Playground to use your exact Client ID.

Here is the 3-minute setup to generate a real token for Bruno:

1. Whitelist the Playground in Google Console
Before the Playground can generate a token for you, Google needs to know it's allowed to do so.

Go back to your Google Cloud Console Credentials.

Click on your ch355 Web Client to edit it.

Scroll down to Authorized redirect URIs.

Click + ADD URI and paste exactly this: `https://developers.google.com/oauthplayground`

Click Save at the bottom. (Keep this tab open, you need your Client Secret in a second).

2. Configure the OAuth Playground
Open the Google OAuth 2.0 Playground.

In the top right corner, click the Gear Icon (OAuth 2.0 configuration).

Check the box for Use your own OAuth credentials.

Paste your OAuth Client ID and your OAuth Client secret into the boxes. (If you didn't save the secret earlier, you can copy it right from the Google Console tab you just left open).

Click Close.

3. Generate the Token
On the left side of the screen under Step 1, scroll all the way to the bottom to the box that says "Input your own scopes".

Type exactly this into the box: openid email profile

Click the blue Authorize APIs button.

Google will pop up a standard login screen. Log in with your own Gmail account and click Continue.

You will automatically be pushed to Step 2. Click the blue Exchange authorization code for tokens button.

4. Grab Your id_token
On the right side of the screen, you will see a large JSON response block appear. Inside that block, look for the "id_token" key.

It will be a massive string starting with eyJ.... Copy that entire string (without the quotes).

Drop that massive string into your Bruno JSON body and fire the request:


```json
{
  "status": "success",
  "code": 200,
  "message": "Generated a JWT using Google Auth",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZGl0eWF2YXJtYW4ubWFuanVuYXRoQGdtYWlsLmNvbSIsImV4cCI6MTc4MTI4NTg0N30.kTbfRTU29yVhhjwW_0HoIPtymfH8FYYGJ3liRamyXCU",
    "token_type": "bearer"
  }
}
```

PS: You'll need to have the corresponding client ID in your app's `.env` for this to work. Otherwise you'd get an `unauthorized` error.

The Server-to-Server Flow (Authorization Code Grant): The backend actively talks to Google to exchange a code for a token. This flow requires the Client Secret because your server must prove its identity to Google. (This is what the Google OAuth Playground did behind the scenes, which is why it asked for your secret).

The Frontend-to-Backend Flow (Implicit/ID Token Verification): Your game frontend (or mobile app) talks directly to Google, gets the id_token, and hands it to your FastAPI server. Your backend just needs to check if that token is cryptographically valid. Because your backend is only verifying a signature using Google's public keys, it never needs to prove its identity to Google, so it doesn't need the Client Secret.

You can safely leave the Client Secret sitting in your Google Cloud Console. You would only ever need to copy it if you decide to change your architecture in the future to a server-side authorization flow, or if you integrate a third-party service that handles the authentication for you.

For ch355, your backend only needs the GOOGLE_CLIENT_ID to make sure the token belongs to your app.