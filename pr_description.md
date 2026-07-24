🔒 [security] Prevent accidental exposure of sensitive keys in .env.example

🎯 **What:** Updated `.env.example` to include explicit security warnings and replace empty values with placeholder texts like `your_api_key_here_DO_NOT_COMMIT`.

⚠️ **Risk:** The previous `.env.example` had empty values for sensitive API keys, which might tempt developers to paste their real credentials into this tracked file, inadvertently exposing them to version control.

🛡️ **Solution:**
- Added a prominent warning block at the top of `.env.example` explaining that the file is versioned and instructing users to copy it to `.env` or `.env.local` instead.
- Populated empty secret fields with clear placeholder text to explicitly indicate they shouldn't contain real data.
