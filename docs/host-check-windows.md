# Host check: Windows (task 0.7)

Goal: confirm the Phase 0 pass-through plugin loads, passes audio, and survives a save/reopen in Ableton Live 12, FL Studio, and Bitwig on Windows. About 20 minutes. (Logic and the Mac versions wait for Mac checkpoint A.)

## 1. Get the build

Either build it yourself (`tools\msvc.cmd cmake --build --preset windows-release`) and use `build\windows-release\plugin\Clay_artefacts\Release\`, or download the **Clay-windows** artifact from the latest green CI run on GitHub (Actions tab → latest run on `main` → Artifacts) and unzip it.

## 2. Install (needs admin, once per new build)

Copy these into the standard plugin folders (Windows will ask for permission):

| File | Copy to |
|---|---|
| `VST3\Clay.vst3` (the whole folder) | `C:\Program Files\Common Files\VST3\` |
| `CLAP\Clay.clap` | `C:\Program Files\Common Files\CLAP\` |

The standalone app (`Standalone\Clay.exe`) runs from anywhere.

## 3. Check each host

Tick each box. If something fails, note what you saw (error text or screenshot) and tell Claude.

**Ableton Live 12** (VST3; Live doesn't load CLAP)
- [ ] Options → Preferences → Plug-Ins: "Use VST3 Plug-In System Folders" on → Rescan
- [ ] Drag *Clay* (Plug-Ins → VST3 → Clay) onto an audio track with a vocal clip
- [ ] Playback sounds identical with the plugin on and off
- [ ] The Clay window opens and shows "Clay · Engine 0.0.1 · Phase 0 pass-through"
- [ ] Save the set, close Live, reopen the set: Clay is still on the track, no error

**FL Studio** (VST3 and CLAP)
- [ ] Options → Manage plugins → Find installed plugins
- [ ] Add Clay (VST3) to a mixer insert with audio playing: sound unchanged, window opens
- [ ] Repeat with Clay (CLAP)
- [ ] Save, close, reopen the project: Clay is still there

**Bitwig** (VST3 and CLAP)
- [ ] Settings → Locations: VST3 and CLAP folders listed; let it rescan
- [ ] Add Clay (CLAP) to an audio track: sound unchanged, window opens
- [ ] Repeat with Clay (VST3)
- [ ] Save, close, reopen: Clay is still there

**Standalone**
- [ ] `Clay.exe` opens; Options → Audio/MIDI settings shows your audio device

When all boxes are ticked, tell Claude "Windows host check passed".
