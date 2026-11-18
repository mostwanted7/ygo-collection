# YGO Collection

A small Linux app for tracking your Yu-Gi-Oh! cards, with a picture gallery and EDOPro integration. Your collection stays on your computer. No account, subscription, or hosted service.

## Get started

You need **Linux**, **Python 3.9 or newer**, a web browser, and an installed, updated copy of [EDOPro / Project Ignis](https://projectignis.github.io/). No pip packages or build step are needed. On Debian/Ubuntu, install the launcher prerequisites with `sudo apt install python3 git xdg-utils`; on Fedora, use `sudo dnf install python3 git xdg-utils`.

```sh
git clone https://github.com/mostwanted7/ygo-collection.git
cd ygo-collection
./ygo-collection
```

The app opens a browser window and runs at **http://127.0.0.1:8737**. Keep the terminal open; press **Ctrl+C** there to stop the app. Closing the browser window does not stop the server. Chromium-based browsers, when found, open a standalone app window; other browsers open a normal tab.

EDOPro is expected at `~/Games/ProjectIgnis`. If yours is elsewhere:

```sh
EDOPRO_DIR="/path/to/ProjectIgnis" ./ygo-collection
```

To remember that location, add `export EDOPRO_DIR="/path/to/ProjectIgnis"` to your shell's startup file. The database is read directly from EDOPro; this app does not download or bundle a card database. Open/update EDOPro first if the app reports that no database was found.

Downloaded the repository as a ZIP instead? Extract it, open a terminal in its folder, and run `chmod +x ygo-collection` once before launching.

## Add cards quickly

1. Type a card name in the search box.
2. Click **1**, **2**, or **3** below the matching card to set how many copies you own.
3. After the save succeeds, the search box is automatically focused with its text selected. Just type the next card name and repeat.

**Ctrl+K** (or **Cmd+K**) returns to search from anywhere, including the card details popup. **Escape** clears the search or closes the popup. Click a card's picture for its details; use **×** to remove it. Quantity buttons set the total, rather than adding to it.

The existing gallery includes collection filtering, monster/spell/trap filters, sorting by name, quantity, or recently added, and card/copy totals. The current model tracks **up to three copies per card**, suitable for deck building; it does not distinguish printings, rarities, conditions, or alternate artworks, and is not a price tracker.

## Build decks from your collection

Each save updates `lflists/Collection.lflist.conf` in your EDOPro installation. Restart EDOPro, then choose **Collection** in its deck editor's banlist selector. Cards are limited to the copies you own, and unowned cards are forbidden. This is an ownership whitelist, not a tournament banlist. The generated file is replaced on subsequent saves, so do not edit it manually.

## Your data and backups

- Your collection is `collection.json` beside the app, created on the first save. A fresh installation starts empty.
- Back up that file to a separate location. To restore, stop the app and copy it back beside `collection.py`.
- Artwork is reused from EDOPro when available; otherwise it is downloaded from Project Ignis and cached in `~/.cache/ygo-collection/pics`. Searching and editing work offline once EDOPro's database is present. Uncached images need internet access.
- Collection files, exports under `exports/`, caches, and local configuration are excluded from Git. Do not force-add personal data when contributing.
- If a collection file is invalid or unreadable, startup stops instead of silently replacing it with an empty collection.

To update an installation cloned from this public repository, back up `collection.json`, stop the app, and run `git pull --ff-only` in its folder.

## Showcase your collection

Export a **read-only HTML snapshot**:

```sh
mkdir -p exports
./ygo-collection --export exports/collection.html
```

Open the HTML file directly in a browser or upload it to any static web host. It keeps the gallery, filtering, sorting, quantities, and card details, without editing controls or a running app backend. Exporting does not modify your collection or EDOPro banlist. The destination must be a new file; use a different filename or remove the previous export before exporting again.

Artwork already available locally is embedded in the HTML. Missing artwork uses Project Ignis image URLs and needs an internet connection; visitors' browsers request those images from that service. A card-name placeholder appears if an image cannot load. Embedded artwork can make a large collection's export quite large. Visit the collection gallery and let its images load before exporting if you want more artwork included offline.

**On a home server:** copy just the exported HTML into a static site served by Caddy, nginx, or Apache. For example, place it at `/srv/ygo-collection/index.html` and use this Caddy site block, replacing the example domain:

```caddyfile
cards.example.com {
    root * /srv/ygo-collection
    file_server
}
```

Point that domain to your server and make ports 80/443 reachable for Caddy's automatic HTTPS, or use a tunnel to the static site if your connection does not permit inbound traffic. Do not expose the editable app on port 8737: it is a local tool without user accounts or authentication. Only the static export belongs in the public web directory.

**Without a home server:** create a separate GitHub Pages repository for your showcase, upload the export as `index.html`, and enable Pages for that repository. Other static hosts work too. Each user hosts their own snapshot; this project does not host anyone's collection.

Snapshots do not update automatically. Re-export and replace the hosted HTML when you want to publish changes. Anyone with access to the snapshot can view and copy its collection data, so publish only what you intend to share.

## Other launch options

```sh
./ygo-collection --help
./ygo-collection --no-open       # start the local server without opening a window
./ygo-collection --port 8738     # use a different local port
```

The launcher can also be run by its full path from any directory. Python remains the runtime, but you do not need to invoke it yourself. Keep the launcher beside `collection.py` and `index.html`.

## Contributing

Bug reports and small, focused pull requests are welcome. Include your Linux distribution, Python version, EDOPro location, and steps to reproduce. Do not attach your collection unless you intend to share it publicly. Keep the app lightweight and preserve the existing interface.

Run the backend tests with:

```sh
python3 -m unittest discover -s tests -v
```

Tests use temporary collection data and a small fixture database; they do not need your EDOPro installation or modify your collection. Manually check search → quantity → type next card when changing the frontend, and open an HTML export without the server running.

## License and credits

The app's source code is available under the [MIT license](LICENSE). Yu-Gi-Oh! names, card text, artwork, and other third-party assets belong to their respective rights holders and are not covered by that license. This is an unofficial fan project, not affiliated with or endorsed by Konami. Card data and artwork are sourced through your EDOPro installation and [Project Ignis](https://projectignis.github.io/).
