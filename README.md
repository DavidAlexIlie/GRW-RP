# GRWRP – Ghost Recon Wildlands RolePlay

[![GRWRP video](https://img.youtube.com/vi/mqBH2iFz04A/maxresdefault.jpg)](https://youtu.be/mqBH2iFz04A)

▶ **[Watch the video](https://youtu.be/mqBH2iFz04A)**

A small Windows app with on/off switches that hide gear on your character, so you can roleplay as a civilian:

- **Hide weapons**: the Super Shorty and/or the D-50 pistol become invisible. They still work. Choose which in Settings.
- **Hide backpack**: the Hydra (CamelBak) backpack.
- **Hide earpiece**: the radio earpiece/headset.
- **Hide pants holster**: removes the leg holster (strap and sheath) from the pants you pick in a visual picker.

Changes apply the next time you start the game. **Single-player only.**

## How to use
1. Unzip anywhere. Putting the `GRWRP` folder inside the game folder lets it find the game instantly.
2. Close the game and run `GRWRP.exe`.
   - It looks for the game in your Steam libraries, Ubisoft Connect, Epic and on all drives.
   - If it can't find the game, browse to the folder that contains `GRW.exe`.
3. Flip the switches, then start the game.

While the game is running, the app locks itself, because game files can't be changed while they're in use.

## How it works and how to undo it
- GRWRP edits the game's `.forge` archives **on your PC**. It never replaces them.
  - For each hidden model it writes a modified copy at the end of the archive.
  - It then points the archive's index at that copy. The model is kept but draws no triangles.
- Before changing anything, it saves the exact original index bytes to a small file next to the archive: `*.forge.civmod_<option>_undo.json`.
- **Turning a switch OFF restores those original bytes**, so the game reads its untouched data again.
- To remove everything: turn every switch OFF.
  - Steam's *Verify integrity of game files* also restores the originals.
  - After a game update, verify files, then switch your options on again.

## Is this safe?
- **Full source code is included** (`GRWRP_source.zip`). You can read it, run it with Python (`python app.py`), or build the exe yourself (`build.bat`).
- **No internet access.** The app has no network code, and Qt's network module isn't even bundled. No updates, telemetry or downloads.
- **No game files are shipped.** The pants previews are rendered on your own PC, from your own game files, in the background the first time you start the app. The download contains only the app, an icon, two badge images and a list of model names.
- **It only touches what you switch on**, and every change can be reverted (see above).
- **Antivirus warnings:** apps packaged with PyInstaller are sometimes flagged as false positives. That's why the source is included. [VirusTotal report](https://www.virustotal.com/gui/file/2c2ce1c520c5ab4efecff239dc871457fc0cb7279be7c84cd6f33a92f1976bb9)
- The app itself doesn't touch anti-cheat. You switch Easy Anti-Cheat off yourself (see above), so use it in single-player only. Modified game files in online modes are at your own risk.

## Building from source
Requires Windows and Python 3.10+. Run `build.bat`, or run `python app.py` directly after `pip install -r requirements.txt`.

`render_thumbs.py` and `ghostcivmod.py` also work from the command line when run from the game folder.

*Not affiliated with or endorsed by Ubisoft. Ghost Recon Wildlands is a trademark of Ubisoft Entertainment.*
