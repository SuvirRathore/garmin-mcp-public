"""Run once to exchange a Garmin password for OAuth tokens stored in ~/.garth."""

from getpass import getpass

import garth


def main() -> None:
    email = input("Garmin email: ")
    password = getpass("Garmin password: ")
    garth.login(email, password)          # SSO handshake; prompts for MFA if enabled
    garth.save("~/.garth")                # writes OAuth1 + OAuth2 tokens only
    print("Tokens saved to ~/.garth")


if __name__ == "__main__":
    main()
