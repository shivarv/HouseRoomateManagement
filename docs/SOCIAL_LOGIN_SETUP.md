# Social sign-in: setup

"Continue with Apple / Google / Facebook" is built into the backend, the website and the iOS app.
Each button appears **once its IDs are set on the backend** (Render → `housemate-api` →
Environment). Nothing else needs changing in the code, and the apps read the IDs from
`GET /api/v1/auth/providers`.

| Provider | iOS | Website | Backend env |
|---|---|---|---|
| Apple | ✅ always shown | — (optional, not built) | none (checks tokens for the bundle ID `com.roommatesapp.HouseRoomateManagement`) |
| Google | ✅ | ✅ | `GOOGLE_IOS_CLIENT_ID`, `GOOGLE_WEB_CLIENT_ID` |
| Facebook | ✅ | ✅ | `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET` |

Instagram can't be used: Meta's Instagram login only works for business and creator accounts.
Apple is required on iOS once Google or Facebook is offered (App Review Guideline 4.8).

## How it works

1. The app runs the provider's own sign-in. That's the Apple sheet on iOS. For Google and Facebook it's their web page in a secure sheet on iOS, or their buttons on the website.
2. The app sends the token it gets back to `POST /api/v1/auth/oauth/{google|apple|facebook}`.
3. The backend checks the token with the provider, then does one of these:
   - **Signs you in** if that provider account is already linked to a user.
   - **Links it** to an existing account if the provider *confirms* the same email, then signs you in.
     A password account and a Google account with the same Gmail become one account.
   - **Creates the account,** if it has a **first or last name** and an **email or phone**.
     If the provider didn't give one of those, the app shows a "Finish your profile" form and sends the same token again.
     This happens when Apple has already shared the name once, or a Facebook account has no email.
4. A phone number is contact info only for now. There's no SMS login.

Accounts made this way have no password. Logging in with a password on such an account says
"This account signs in with Google. Use that button instead."

## Google (≈10 minutes, free)

1. <https://console.cloud.google.com> → create a project, e.g. "Roommates".
2. **APIs & Services → OAuth consent screen:**
   - User type: External.
   - App name, support email, and the app logo (the icon in `ios/.../AppIcon.png`).
   - Authorised domains: `onrender.com` (and your own domain).
   - Privacy policy link: `https://<website>/privacy`.
   - Scopes: `openid`, `email`, `profile` only. These are "non-sensitive", so no Google review is needed.
   - **Publish** the app. In "Testing" mode only listed test users can sign in.
3. **Credentials → Create credentials → OAuth client ID**, twice:
   - **Web application.** Authorised JavaScript origins: `https://housemate-web.onrender.com`, your domain, and `http://localhost:5173` for local work. No redirect URIs are needed. Copy the client ID into `GOOGLE_WEB_CLIENT_ID`.
   - **iOS.** Bundle ID: `com.roommatesapp.HouseRoomateManagement`. Copy the client ID into `GOOGLE_IOS_CLIENT_ID`.
4. Set both on Render and redeploy the API.

## Facebook (≈20 minutes, free)

1. <https://developers.facebook.com> → **Create app** → use case "Authenticate and request data from users with Facebook Login".
2. **App settings → Basic:**
   - Privacy policy URL: `https://<website>/privacy`.
   - User data deletion: *Data deletion instructions URL* = `https://<website>/privacy` (the "Deleting your data" section).
   - App icon and category.
3. **Facebook Login → Settings:**
   - Valid OAuth redirect URIs: `https://housemate-web.onrender.com/` (and your domain).
   - Allowed domains for the JavaScript SDK: the same sites.
4. **Add platform:**
   - **iOS:** Bundle ID `com.roommatesapp.HouseRoomateManagement`.
   - **Website:** Site URL `https://housemate-web.onrender.com`.
5. Copy the **App ID** into `FACEBOOK_APP_ID` and the **App secret** into `FACEBOOK_APP_SECRET`, on Render only. The secret must never go in the apps.
6. Switch the app from **Development** to **Live**. In Development, only people with a role on the app can sign in.
   - `public_profile` and `email` work without Meta's App Review.
   - Meta may ask for **Business Verification** before going Live.

## Apple (part of the Apple Developer Program)

- **iOS:** nothing to set up beyond the Developer Program. The app already has the **Sign in with Apple** capability (`ios/RoommateApp/RoommateApp.entitlements`). When signing with your team in Xcode, keep that capability ticked under Signing & Capabilities.
- **Website (optional, not built yet):** it needs a Services ID, a verified domain and a return URL. Add the Services ID to `APPLE_CLIENT_IDS` (comma-separated after the bundle ID) and `APPLE_WEB_SERVICES_ID` if we build it.
- **Private relay:** if someone hides their email, Apple gives an `…@privaterelay.appleid.com` address. To email them, register your sending domain in Apple Developer → Sign in with Apple for Email Communication.

## Testing

- **Backend:** `pytest tests/test_oauth.py`. The providers are faked, apart from one real token-signature check made with a locally generated key.
- **iOS simulator:** Sign in with Apple works once the simulator is signed in to an Apple ID (Settings → Apple Account). Google and Facebook open their real pages, so their client IDs must be set on the backend the app talks to.
- Try the edge cases:
  - Sign in with Google using the same Gmail as an existing password account. You should end up in the same account, with both ways to sign in listed in Profile.
  - Sign in with Apple and **Hide My Email**.
  - Sign in with a Facebook account that has no email. It should ask for an email or phone.

## Database

Migration `0020` (applied on the next Render deploy):
- Adds `users.phone`, which is unique and optional.
- Makes `users.email` and `users.password_hash` optional.
- Adds the `user_identities` table: one row per linked Google, Apple or Facebook account.
