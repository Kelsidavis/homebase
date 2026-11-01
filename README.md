# Home Base

An open-source TV home screen for the Raspberry Pi 4. It boots straight to a
big, remote-friendly interface with YouTube, Plex, a music player with live
visualizers, weather, and an AP News ticker.

It is built for a Pi connected to a TV over HDMI and driven by a keyboard
remote with a trackpad, though any USB keyboard and mouse work.

## Features

- **Home screen**: clock, weather for your location, and large tiles for
  YouTube, Plex, Music and casting.
- **YouTube** in its TV ("leanback") interface.
- **Plex movies and shows**, built in: Continue Watching, Recently Added and
  each library, with seasons and episodes. Videos play full screen in mpv
  with the Pi's hardware decoder, and progress is reported back to Plex
  (resume anywhere; watched past 90%).
- **Music** from your Plex server: browse albums, artists and playlists, with
  Spectrum, Mirror and Wave visualizers driven by the real audio, and a full
  screen visualizer mode.
- **Cast to TV**: the Pi shows up as a player in the Plex app on your phone
  (via [plex-mpv-shim](https://github.com/iwalton3/plex-mpv-shim)).
- **AP News ticker**: headlines from AP News only.
- **Settings on the TV**: Wi-Fi and IP address, remote access (SSH), display
  resolution, refresh rate and menu size (with a 15-second safety revert),
  screen edge adjustment, location, temperature units, clock format and Plex
  account.
- **14 themes** and three wallpaper styles (plain, ambient, album art).
- **First-boot setup on the TV**: country, Wi-Fi, location, theme and Plex.

## Privacy

- Your location is only what you type into Settings. Home Base never looks up
  your location from your IP address.
- Weather comes from [Open-Meteo](https://open-meteo.com): the city you search
  for and the saved coordinates are sent to it.
- AP headlines are fetched through Google News' public RSS feed, restricted to
  apnews.com.
- The Plex token stays on the Pi; the browser only talks to the local backend.
- SSH is off by default and can only be turned on after setting a password.

## Requirements

- Raspberry Pi 4 (2 GB RAM or more)
- microSD card, 8 GB or larger
- A TV or monitor on HDMI (use the micro-HDMI port next to the USB-C power
  jack)
- A keyboard remote, or a USB keyboard and mouse

## Install

### Option 1: flash the image

1. Download the latest `homebase-<version>.img.xz` from the
   [releases page](../../releases).
2. Write it to a microSD card with
   [Raspberry Pi Imager](https://www.raspberrypi.com/software/) ("Use custom").
   Choose **No** when Imager offers OS customisation: Home Base sets itself up
   on the TV.
3. Put the card in the Pi, connect the TV and power it on. Follow the setup on
   screen.

### Option 2: install on Raspberry Pi OS Lite

On a fresh Raspberry Pi OS Lite (64-bit, trixie) with network access:

```sh
git clone https://github.com/Kelsidavis/homebase.git
cd homebase
sudo sh system/install.sh
sudo reboot
```

This creates a `homebase` user that logs in automatically on the TV and runs
the interface.

## Remote keys

| Key | Action |
| --- | --- |
| Arrow keys | Move between items |
| Enter | Open or choose |
| Esc, Backspace or Back | Go back |
| Home | Return to the home screen from anywhere: closes a video or game, and leaves YouTube |
| Volume Up, Down, Mute | System volume, from any screen |
| Play/Pause, Next, Previous, Fast-forward, Rewind | Control music and videos |
| While a video plays | OK/Space pause, Left/Right 10 s, Up/Down 1 min, Back/Esc stop, `s` subtitles, `a` audio track |

## Building the image

The image is built with Raspberry Pi's [pi-gen](https://github.com/RPi-Distro/pi-gen)
in Docker:

```sh
./image/build.sh
```

The result is written to `image/deploy/`. Building on an arm64 machine (such as
an Apple Silicon Mac) is fastest.

## Development

The backend is a single Python file using only the standard library. To run
the interface on another machine with simulated network and display data:

```sh
HB_FAKE=1 HB_CONF_DIR=/tmp/homebase-dev python3 backend/homebase.py
```

Then open http://127.0.0.1:8099 in a browser.

## Layout

| Path | Contents |
| --- | --- |
| `backend/homebase.py` | Local web server and JSON API: settings, network (NetworkManager), display (wlr-randr), weather, news, Plex, power |
| `ui/` | The TV interface (HTML, CSS, JavaScript; no build step) |
| `chromium-ext/` | Kiosk extension: Home key handling and YouTube TV mode |
| `bin/` | Session and cast receiver launch scripts |
| `system/` | Installer, services, sudo rules and configuration |
| `image/` | pi-gen stage and build script for the SD card image |

## License

Home Base is licensed under the GNU General Public License v3.0. See
[LICENSE](LICENSE).

The bundled [Outfit](https://github.com/Outfitio/Outfit-Fonts) font is
licensed under the SIL Open Font License 1.1 (`ui/fonts/OFL.txt`).

YouTube, Plex and AP are trademarks of their respective owners. Home Base is
not affiliated with or endorsed by them.
