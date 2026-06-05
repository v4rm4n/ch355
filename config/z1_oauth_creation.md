Getting a Google Client ID is completely free and takes about two minutes. You do it through the Google Cloud Console.

# Create a Google Cloud Project

- Go to the Google Cloud Console.

- Log in with your normal Google account.

- In the top-left corner (next to the Google Cloud logo), click the Project Dropdown and click New Project.

- Name it something like ch355-backend and click Create. Make sure your new project is selected at the top.

# Configure the OAuth Consent Screen

Before Google lets you create a Client ID, they want to know what the login screen should look like when players try to log in to your game.

- Use the left-hand hamburger menu and go to APIs & Services > OAuth consent screen.

- Under "User Type", select External (this allows anyone with a Gmail account to log in) and click Create.

- Fill out the required fields:

    - App name: ch355

    - User support email: (Your email)

    - Developer contact information: (Your email)

- Click Save and Continue at the bottom of all the remaining screens. You do not need to add scopes or submit it for verification right now—verification is only for published production apps.

# Grab your keys

- Click that Create OAuth client button on the right side.

- Application type: Select Web application from the dropdown.

- Name: You can leave it as "Web client 1" or name it something like ch355 API.

- Authorized JavaScript origins: This is the important part. Click + ADD URI and enter:

    - `http://localhost:3000` (for your future game UI)

    - Click + ADD URI again and add `http://127.0.0.1:8000` (for your local FastAPI testing)

- Leave "Authorized redirect URIs" completely blank.

- Click Create at the bottom.

- A box will pop up displaying your Client ID and Client Secret.

- Copy that Client ID (the long string ending in `.apps.googleusercontent.com`), paste it into your `.env` file as **GOOGLE_CLIENT_ID=your-copied-id**, and your Google setup is officially 100% complete.


The client ID can always be accessed from Clients tab under Google Auth Platform.

OAuth access is restricted to the test users  listed on your OAuth consent screen

```Client ID
8419327201-adr3t5sb8qb1assmo40dc53h0788bmno.apps.googleusercontent.com
```