# Easter eggs

> **Spoilers ahead.** These are meant to be found. Maintainers, read on.

| Secret | How to find it | What happens |
|---|---|---|
| **Disco mode** | Type `disco`. The Konami code (<kbd>↑</kbd> <kbd>↑</kbd> <kbd>↓</kbd> <kbd>↓</kbd> <kbd>←</kbd> <kbd>→</kbd> <kbd>←</kbd> <kbd>→</kbd> <kbd>B</kbd> <kbd>A</kbd>) also works | For twelve seconds the brand dot and the playback bar cycle through soft colours, then quietly return to normal. |
| **Vinyl mode** | Type `vinyl` | The player artwork becomes a record that spins while music plays and stops when you pause. Type `vinyl` again to turn it off. |
| **Zen mode** | Type `zen` | The sidebar slides away, leaving only the page and the player. Press <kbd>Esc</kbd> or type `zen` again to bring it back. |
| **The vault** | Click the iSpotify logo five times quickly | A card shows your library stats: songs, favorites, playlists and total plays. |
| **Up to eleven** | Set the volume to 100, then keep scrolling up (or press <kbd>↑</kbd>) on the volume slider | A tribute to the amp that goes one louder. |

## Guarantees

- **Nothing is swallowed.** The watchers only listen. Every key, click and
  scroll still reaches the control it was meant for.
- **Text fields are safe.** Typed secrets are ignored while a text input has
  focus, so searching for "zen" or "vinyl" works normally.
- **Nothing is saved.** Every mode lasts only for the current session and
  never touches the library or settings.
- **Scope.** Secrets only trigger in the main window, never in dialogs.
  Key auto-repeat is ignored.

The implementation is in `ui/easter_eggs.py`, with the effects in
`MainWindow` (the `# -- secrets` section) and `ArtworkLabel.set_vinyl`.
Tests are in `tests/test_easter_eggs.py`.
