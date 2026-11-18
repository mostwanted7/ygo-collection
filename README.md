# YGO Collection

A lightweight Linux app for tracking your Yu-Gi-Oh! cards, with a picture gallery and EDOPro integration. Your collection stays on your computer—no account or hosted service.

## Get started

You need **Python 3.9+**, a browser, and an updated installation of [EDOPro / Project Ignis](https://projectignis.github.io/). No pip packages or build step required.

Install prerequisites if needed: `sudo dnf install python3 git xdg-utils` on Fedora, or `sudo apt install python3 git xdg-utils` on Debian/Ubuntu.

```sh
git clone https://github.com/mostwanted7/ygo-collection.git
cd ygo-collection
./ygo-collection
```

The app opens at **http://127.0.0.1:8737**. Keep the terminal open; press **Ctrl+C** there to stop it.

EDOPro is expected at `~/Games/ProjectIgnis`. For another location:

```sh
EDOPRO_DIR="/path/to/ProjectIgnis" ./ygo-collection
```

Downloaded a ZIP? Run `chmod +x ygo-collection` once after extracting it. Use `./ygo-collection --help` for options, including `--no-open` and `--port`.

## Using the app

Search a card, click **1**, **2**, or **3** to set your total copies, then type the next name. After saving, search is automatically focused with the previous text selected.

- **Ctrl+K** returns to search; **Escape** clears it or closes card details.
- Click a picture for details, or **×** to remove a card.
- Filter your collection by name or type, and sort by name, quantity, or recently added.

The app tracks **up to three copies per card**, without distinguishing printings, rarities, conditions, or alternate artworks.

Each save also updates EDOPro's `lflists/Collection.lflist.conf`. Restart EDOPro and select **Collection** in its deck editor to build with only the cards and quantities you own. This generated ownership whitelist is separate from tournament legality.

## Data and backups

Your cards are saved in `collection.json` beside the app. Back up that file; to restore it, stop the app and copy it back. Collection data and files under `exports/` are excluded from Git.

Artwork is reused from EDOPro or downloaded from Project Ignis into `~/.cache/ygo-collection/pics`. Searching and editing work offline; uncached artwork needs internet access.

To update, back up your collection, stop the app, and run `git pull --ff-only`.

## Share your collection

Create a **read-only HTML snapshot** with the same gallery, filters, and card details:

```sh
mkdir -p exports
./ygo-collection --export exports/collection.html
```

Open it directly in a browser, or publish it:

- **Home server:** serve the exported file as `index.html` using Caddy, nginx, or Apache with HTTPS.
- **GitHub Pages:** upload it as `index.html` in a separate repository and enable Pages.

Host only the exported HTML—not the editable app on port 8737, which has no authentication. Each user hosts their own snapshot; this project does not host collections.

Cached artwork is embedded; missing images load from Project Ignis. Exports can be large and include your collection data. They do not update automatically: re-export and replace the hosted file to share changes. The export command requires a new filename, so rename or remove the previous export first.

## License and credits

Source code: [MIT](LICENSE). Card data and artwork come through EDOPro / Project Ignis and belong to their respective rights holders. Unofficial fan project; not affiliated with or endorsed by Konami.
