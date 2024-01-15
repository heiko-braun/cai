# Tokens

## SLACK_APP_TOKEN

- In the left-hand menu under "Settings", click on "Socket Mode"
- In the "Connect using Socket Mode section", slide the toggle for "Enable Socket Mode"
- Pick and enter a token name in the window that appears. The name you choose does not seem to matter.
- Click "Generate"
- In the new window, a token starting with xapp- will appear. This is your slack_app_token.

## BOT_TOKEN

- features > OAuth & Permissions > Bot Token (starts with `xoxb-...`)

### App Manifest

```
display_information:
  name: Camel Assitant
features:
  bot_user:
    display_name: Camel Assitant
    always_online: false
oauth_config:
  scopes:
    user:
      - channels:history
      - groups:history
      - mpim:history
    bot:
      - app_mentions:read
      - channels:history
      - channels:read
      - chat:write
      - commands
      - groups:history
      - groups:read
      - im:history
      - mpim:history
      - users:read
settings:
  event_subscriptions:
    user_events:
      - message.channels
      - message.groups
      - message.mpim
    bot_events:
      - app_mention
      - channel_shared
      - message.im
      - message.mpim
  interactivity:
    is_enabled: true
  org_deploy_enabled: false
  socket_mode_enabled: true
  token_rotation_enabled: false

```