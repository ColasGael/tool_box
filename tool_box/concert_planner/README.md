# Configuration


## Playlist API

### Create Google Client ID

For: the App

Follow the guide: https://developers.google.com/workspace/guides/get-started

To create a Google Cloud project with the following specificities:
- Enabled API: `YouTube Data API`
- Enabled scope: `youtube.force-ssl`
- Application Type: `Desktop`
- Client ID: `OAuth 2.0`

### Create Google Authorization Token

For: your Google Account

To: allow access to your YouTube Account.

The first time running the script, you will be prompted to visit a URL.
Open it and allow access.

A local token will be saved to allow for immediate access next times.

### References

YouTube sample APIs: https://developers.google.com/youtube/v3/docs


## Upcoming concerts API

### Create TicketMaster Token

1. Create a developper account: https://developer.ticketmaster.com/
2. Retrieve your personnal token (`API key`): https://developer.ticketmaster.com/products-and-docs/apis/getting-started/
3. Save it here to: `ticketmaster_token.txt`

### References

- `Discovery` API documentation: https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/

### Notes

- `TicketMaster` vs `BandsInTown`

While the `TicketMaster` API limits you to events they are selling ticket for,
`BandsInTown` seems to have a more comprehensive list of upcoming events.
But their API is not open to all.

Having an artist account seems to include some API access.
But not sure how much.
See: https://help.artists.bandsintown.com/en/articles/7053475-what-is-the-bandsintown-api
