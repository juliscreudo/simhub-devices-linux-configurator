# SimHub Devices on Linux — LEDs, screens and buttons working in the Devices tab

[🇧🇷 Português](README.pt-BR.md) · **🇬🇧 English**

Tools and a step-by-step guide to make [SimHub](https://www.simhubdash.com/)'s **Devices** tab
recognize wheels, dashes and button boxes when it runs **under Wine on Linux** — LEDs, screens
and buttons.

The symptom this project attacks is the Devices tab stuck on `Searching device ...` forever.
It is not a limitation of the hardware or of SimHub: these are specific gaps in **Wine** — USB
identity for serial ports, HID collection splitting, missing USB topology — and each one has a
known fix.

### What this project is — and what it is not

This is **the solution I used** to get my peripherals working in the Devices tab, organized so
that someone else can reproduce it.

**SimHub was not ported, not rewritten, and is not redistributed here.** There is no Linux
build of SimHub: the app is the **official Wotever binary** you download from their site. This
repo is analysis, measurement and configuration.

But **"it modifies nothing" would be a lie**, and the difference deserves to sit up here. What
this project changes in *your* installation:

| what | what it does | reversible? |
|---|---|---|
| `pdu5-leds-patch.py` | swaps **two opcodes** in the IL of your copy of `SimHub.Plugins.dll` | yes — `--revert`, with a backup first |
| `install bridge` | replaces SimHub's `libusb-1.0.dll` with [ours](https://github.com/juliscreudo/wine-libusb-bridge) | yes — the original becomes `.orig` |
| `install pdu5-leds` | removes the prefix's NGen cache | yes — the images are **moved**, not deleted |
| `install udev` / `install registry` | system udev rules and prefix registry keys | yes — `system.reg` is backed up |

This repo ships **the patcher, never a patched DLL**: the modification happens on your machine
and disappears on SimHub's next update. And the bridge doesn't reimplement SimHub — it
reimplements the `libusb-1.0` ABI, a free library, which is the piece missing under Wine.

SimHub belongs to **Wotever**; `linux-simracing-utils` and Winecarte belong to
**[srounce](https://github.com/srounce)**. Much of the credit for what works belongs to those
projects — this repo just puts the pieces together.

Personal project, no warranty, no support.

Validated with the hardware connected on **CachyOS** (kernel 7.1, Wine 11.15), between
2026-08-16 and 2026-08-19. Nothing here is distro-specific; only package names change.

## What works

| device | VID:PID | what connects | status |
|---|---|---|---|
| Conspit H.AO HUB | `3514:0007` | LEDs + buttons (serial) | ✅ **hardware-validated** |
| Pokornyi MCP ButtonBox | `0483:cb40` | LEDs + buttons (HID) | ✅ **hardware-validated** |
| Pokornyi MCP EncoderBox | `0483:cb41` | LEDs + buttons (HID) | ✅ **hardware-validated** |
| Pokornyi MCP IgnitionBox | `0483:cb42` | LEDs + buttons (HID) | ✅ **hardware-validated** |
| Pokornyi PDU5 | `0483:cb01` | RPM LEDs (HID) + screen | ✅ **validated** — needs step 5 |
| Pokornyi HYP-R | `0483:cb10` | LEDs (HID) + screen | ✅ **hardware-validated** |
| Pokornyi GTB Pro | `0483:cb11` | LEDs (HID) + screen | ✅ **hardware-validated** |
| Pokornyi FGT | `0483:cb15` | LEDs (HID) | ✅ **validated** — plugging it in and restarting SimHub was enough |
| Pokornyi RALLY | `0483:cb12` | LEDs (HID) | ✅ **validated** — same, zero new steps |
| Cube Controls AMG (AC190) | `c872:200b` | LEDs + buttons (HID) | ✅ **hardware-validated** |
| VoCore screen | `c872:1004` | dash + **touch** (libusb) | ✅ **validated** — 854×480, via the bridge |

The **FGT** is the evidence that the recipe generalizes: it had never been connected to this
bench, and plugging it in and restarting SimHub was enough — no device-specific configuration
at all. The why is in [CLAUDE.md](CLAUDE.md).

And what the recipes **should** cover, with nobody having tested it: the remaining Pokornyi
devices (PDU7, LED Brows, LMPH, F499, HYP-R PRO, LMP PRO V2, GTE PRO V3), the rest of
Cube Controls (F-PRO, GT-PRO V2, Astra) and the other Conspit wheels (300GT,
MAX 01, 310 APEX, 290 GP, PW1, CSD). SimHub's catalog holds **more than 200 devices**; the
three paths below cover the vast majority.

> **Your device isn't listed?** That's expected — there is only one test bench here. Go
> straight to [My device isn't in the list](#my-device-isnt-in-the-list): almost everything in
> this project matches by **transport**, not by model, and there is a diagnostic walkthrough to
> find out which one is yours.

### The three paths

Every device in the catalog falls into one of these, and **the right path depends on the
transport**, not on the brand:

| path | how SimHub talks to it | who uses it | step |
|---|---|---|---|
| **HID** | `/dev/hidraw*` via `winebus` | Pokornyi, Cube Controls | [1](#step-1--udev-hardware-access) + [2](#step-2--winebus-registry-hid-devices) |
| **Serial** | COM port (CDC) | Conspit, the wiki's Arduinos | [3](#step-3--serial-devices-conspit-and-arduinos) |
| **VoCore screen** | libusb, raw USB | any wheel with a screen | [4](#step-4--vocore-screens-the-libusb-bridge) |

Wheels with screens are a **composite**: LEDs **and** screen as independent devices. The two
halves need different steps — and the LEDs are the **primary** device, so a screen won't
connect while its LEDs don't.

---

## The layer stack

This project is the top layer. Each one only makes sense with the one below it in place, and
diagnosing out of order sends you off to fix the wrong thing:

```
linux-simracing-utils   installs SimHub and creates the Wine prefix
       ↓
wine-libusb-bridge      makes libusb work under Wine (VoCore screens)
       ↓
simhub-devices-linux    configures the devices in the Devices tab   ← this repo
```

`simhub-devices doctor` checks the whole stack in that order and tells you which layer
you're stuck on.

---

## The path, in 5 steps

| step | what it solves | required? |
|---|---|---|
| **1 — udev** | access to `/dev/hidraw*` and to the screen's USB node | **yes**, for HID and screens |
| **2 — winebus registry** | Wine hands over the real HID device, not the SDL-synthesized one | **yes**, for HID |
| **3 — serial device** | gives the COM port the USB identity Wine doesn't give it | only for Conspit/Arduino |
| **4 — libusb bridge** | makes the VoCore screen visible and writable | only for screens |
| **5 — PDU5 / PDU7 / LED Brows** | fixes the HID collection the manager asks for | only for those three |

If all you have is a button box or a screenless wheel, **steps 1 and 2 are enough**.

At any point, `simhub-devices doctor` tells you where you are and what's missing.

---

## Prerequisites

```bash
git clone https://github.com/juliscreudo/simhub-devices-linux.git ~/apps/simhub-devices-linux
cd ~/apps/simhub-devices-linux
mkdir -p ~/.local/bin && ln -s "$PWD/tools/simhub-devices" ~/.local/bin/simhub-devices
```

The rest of this guide calls the command as `simhub-devices`, without the `tools/` prefix —
the symlink above is what makes that work. Make sure `~/.local/bin` is on your `PATH` (most
distros already have it there); if `simhub-devices doctor` says "command not found", run
`export PATH="$HOME/.local/bin:$PATH"` (and add it to your `.bashrc`/`.zshrc`).

### Packages

| what | used for | Fedora | Arch / CachyOS |
|---|---|---|---|
| Python 3 | the installer and the tools | `python3` | `python` |
| `dnfile` | IL analysis (the "device not listed" walkthrough) | via `venv` | via `venv` |
| `gcc-mingw-w64` *(optional)* | building the `.exe` diagnostic probes | `mingw64-gcc` | `mingw-w64-gcc` |
| `libusb` + `gcc` | building the bridge (step 4) | `libusb1-devel` | `libusb` |

```bash
# Fedora
sudo dnf install -y python3 git mingw64-gcc libusb1-devel

# Arch / CachyOS
sudo pacman -S --needed python git mingw-w64-gcc libusb
```

`dnfile` is only needed if you're going to investigate a device that isn't listed:

```bash
python3 -m venv venv && ./venv/bin/pip install dnfile
```

> ⚠️ On Arch, do **not** run a global `pip install`: PEP 668 blocks it, and the `venv` is the
> right way.

### SimHub under Wine (layer 1)

This project **does not install SimHub**. It expects a prefix that is already set up, created
by **[linux-simracing-utils](https://github.com/srounce/linux-simracing-utils)** (srounce), at
`~/apps/linux-simracing-utils/pfx`:

```bash
git clone https://github.com/srounce/linux-simracing-utils ~/apps/linux-simracing-utils
cd ~/apps/linux-simracing-utils
bash install.sh          # pick the SimHub component
```

> ⚠️ **Always launch SimHub through `lsu-launch-wrapper`** (which is what this repo's
> `run-simhub` does). Outside the wrapper the app opens and the devices work, but **telemetry
> never arrives**: the wrapper is what starts `winehub`, the daemon that mirrors the game's
> shared memory into the prefix. The symptom shows up far from the cause.

### The libusb bridge (layer 2 — only for VoCore screens)

**[wine-libusb-bridge](https://github.com/juliscreudo/wine-libusb-bridge)** replaces the app's
`libusb-1.0.dll` with a forwarder to Linux's `libusb`. It is what makes the VoCore screen work.

You don't need to fetch it yourself: `install bridge` (step 4) pulls the pinned release into
`vendor/` on its own. **It is deliberately not a submodule** — the bridge serves any Windows app
under Wine, not just SimHub. To point at another copy, use `$SIMHUB_PONTE`;
`SIMHUB_PONTE_VERSION` pins a tag.

If you don't have a VoCore screen, **skip this** — nothing else in the project depends on it.

---

## Step 0 — diagnose

Before touching anything:

```bash
simhub-devices doctor
```

It lists the known devices that are plugged in, says whether each one has access to the right
node, checks the three layers of the stack, and warns you if the **NGen cache** is active (see
step 5).

> ⚠️ **Everything in the installer is dry-run by default.** Without `--apply` it only prints
> what it would do. `--apply` works in any position: `install bridge --apply` and
> `install --apply bridge` do the same thing.

Available commands:

```
simhub-devices doctor                  diagnostics (default; read-only)
simhub-devices install udev            ACLs for /dev/hidraw* and the screen's USB node
simhub-devices install registry        winebus: EnableHidraw / Enable SDL / DisableInput
simhub-devices install bridge          libusb bridge DLL + the run-simhub launcher
simhub-devices install pdu5-leds       usagePage patch + NGen cache removal
simhub-devices install serial [...]    serial recipe: PnP node + COM port
simhub-devices install shortcut        menu shortcut that goes through run-simhub
simhub-devices post-update             redoes what a SimHub update undoes
simhub-devices clean-cache             removes the NGen cache
```

> The tool's own output and inline comments are in Portuguese. Subcommands and flags are in
> English, with one exception: `--nome` ("name") in `install serial`. This README covers
> what each one does.

---

## Step 1 — udev (hardware access)

This is **the step that unlocks the HID recipe**, and for a long time I thought it was the
registry. It isn't.

```bash
simhub-devices install udev --apply
```

Installs `udev/70-pokornyi.rules` and `udev/70-vocore.rules`, reloads the rules and fires the
trigger. Replug the device (or reboot) if the ACL doesn't show up.

By default `/dev/hidraw*` is **root-only**: `winebus` tries to open it, fails, and **discards
the device silently** — no error, no log, just `Searching device ...` forever. The same goes
for the screen, which needs **write** access on its USB node for libusb to claim the interface.

> ⚠️ **The `70-` prefix is mandatory.** What actually applies `TAG+="uaccess"` is systemd's
> `73-seat-late.rules`, and a `99-` rule arrives after that check: hidraw stays root-only,
> silently. This applies to any rule you add yourself.

> ⚠️ The Pokornyi rule matches `0483:cb??`, **not** the whole vendor — `0483` is
> STMicroelectronics' generic VID, and opening all of it would grant access to hardware with no
> connection to sim racing. Since every Pokornyi PID is in the `CBxx` range, a new model works
> without editing the file. The VoCore rule matches PID `1004` exactly, because `c872` is
> **also** Cube Controls' VID.

Verify:

```bash
simhub-devices doctor        # your device's line should say "acessivel" (accessible)
```

## Step 2 — winebus registry (HID devices)

```bash
simhub-devices install registry --apply
wineserver -k                      # winebus needs to re-read it
```

Writes three values under `HKLM\System\CurrentControlSet\Services\winebus`:

| value | type | role |
|---|---|---|
| `EnableHidraw` | `REG_MULTI_SZ` | **the one doing the work**: one `VVVV:PPPP` line per device |
| `Enable SDL` | `REG_DWORD` `0` | half of the safety net |
| `DisableInput` | `REG_DWORD` `1` | the other half — **only works with both** |

> ⚠️ The key is `Services\`**`winebus`**, **not** the `\Parameters` subkey — the driver never
> reads `\Parameters`. Writing to the wrong place is ignored **silently**; that mistake cost
> three days in the sibling Conspit project.

What this changes: by default Wine hands out joysticks **synthesized by SDL**, with a single
collection. The 64-byte vendor channels the LEDs speak over simply **do not exist** for the
app. On the **hidraw** backend Wine passes the real descriptor and `hidclass` splits the
top-level collections into `&Col01`/`&Col02`, exactly like Windows.

### Verifying with `hidenum`

This is the measurement that tells you whether the step worked. Build it and run it **inside
the prefix**:

```bash
x86_64-w64-mingw32-gcc tools/hidenum.c -o tools/hidenum.exe -lhid -lsetupapi
WINEPREFIX=~/apps/linux-simracing-utils/pfx wine tools/hidenum.exe 0483
```

With no arguments it lists everything; with arguments it filters by VID in hex. **What to
expect is not always "two lines"** — it depends on the report descriptor's topology:

| descriptor | expected from `hidenum` |
|---|---|
| **sibling** collections (e.g. Conspit CPP.LITE) | **two** lines: `usage 0x04` and `usage 0x3A`, both `in 64 out 64` |
| **nested** vendor (all Pokornyi) | **one** line: `usage 0x04`, `in 64 out 64` |
| still SDL-synthesized | `usage 0x05` with `out 0` — **wrong** in both cases |

Wine only promotes **sibling** collections to their own PDO; with a nested vendor collection
the channel comes through the **same handle** as the joystick — which is why the MCPs' LEDs
work with a single PDO.

> ⚠️ **Enumeration has a race.** Right after a `wineserver -k` the first pass may not list
> everything. Always measure on the second run, ~3 s apart.

## Step 3 — serial devices (Conspit and Arduinos)

Only for devices on the **serial** path. In SimHub's catalog, **all seven Conspit wheels** go
through here (measured 2026-08-19), as do the Arduinos from the official wiki.

First see what's plugged in:

```bash
simhub-devices install serial
```

Without `--dev` it just lists the available serial devices. Then:

```bash
simhub-devices install serial \
    --dev /dev/serial/by-id/usb-CONSPIT_H.AO_XXXXXXXX-if00 \
    --vid 3514 --pid 0007 --com 37 --nome 'CONSPIT H.AO' --apply
wineserver -k
```

### Why this is necessary

Under Wine **every COM port is born without a USB identity** (measured: 36 ports, all `VID=0
PID=0`), and SimHub matches the device precisely by the port's VID/PID. Without a PnP node
carrying that data, the match fails silently. The installer creates that node.

> ⚠️ **SimHub reads `DEVPKEY_NAME`**, and Wine only resolves it from a `Properties\...`
> subkey with a `hex(ffff0012)` value. Legacy `FriendlyName`/`DeviceDesc` are **no
> substitute** — the "legacy" node that is enough for Qt and ConspitLink is **not enough
> here**. Use `tools/nameprobe.c` to see which API answers what, and [CLAUDE.md](CLAUDE.md)
> for the full chain.

> ⚠️ **Use COM > 32.** `wineboot` fills `com1..com32` by scanning `/dev/ttyS*` and overwrites
> any symlink in that range. The installer refuses numbers ≤ 32.

> ⚠️ **`wineserver -k` at the end is mandatory**: `SERIALCOMM` is volatile and only gets
> repopulated when the wineserver restarts. A symlink created while it's up won't show.

> ⚠️ Always use `/dev/serial/by-id/` — `ttyACMn` renumbers on every re-enumeration.

## Step 4 — VoCore screens (the libusb bridge)

Only for wheels and dashes with a screen.

```bash
simhub-devices install bridge --apply
run-simhub                              # starts the bridge and SimHub, in that order
```

`install bridge` downloads (or builds) the bridge, preserves the original `libusb-1.0.dll` as
`.orig`, installs the bridge's DLL in its place, and creates the `~/.local/bin/run-simhub`
link.

### Why a bridge, and not a driver

The screen has **no display driver**: SimHub writes to it as a raw USB device, over libusb
(`SimHub.BitmapDisplay.Vocore.dll` → `SimHub.LibUsbNative.dll` → `libusb-1.0.dll`). On Windows,
SimHub's installer **binds WinUSB to the device** — without that, libusb can't talk to it.

> ⚠️ **Do not try to reproduce that step in the prefix.** It would install a Windows kernel
> driver, which Wine does not execute; and Wine's builtin `winusb.dll` is a **stub**. There is
> nothing in Wine today that makes libusb's Windows backend work.

The bridge skips all of that: a pure **PE32** DLL forwards the 32 calls to a native helper that
talks to Linux's `libusb-1.0.so`. And it solves a second problem for free: since every VoCore
screen is `c872:1004`, SimHub works out which wheel each one belongs to by walking up the USB
tree — a tree that **doesn't exist in Wine's PnP**, but which it asks libusb for, and Linux's
libusb has it.

- ✅ The screen's **touch** works over the same bridge, with no evdev and no fight with the
  desktop: the kernel doesn't even see the screen as an input device, since no driver claims
  it.
- ⚠️ **Always use `run-simhub`.** The helper must be up **before** SimHub, otherwise the
  bridge DLL returns an error and the screen won't connect; and a helper left dangling after
  SimHub dies keeps the interface claimed, causing `LIBUSB_ERROR_BUSY` next time. The launcher
  handles both ends. **Opening it from the Windows/Wine menu shortcut doesn't count** — it
  launches SimHub directly, without the bridge. `simhub-devices install shortcut --apply`
  creates a menu shortcut that goes through `run-simhub`.
- ⚠️ If you have the `mpro_drm` kernel module loaded, **unload it** (`rmmod mpro`): with it the
  kernel claims the interface and the bridge stops seeing the device. The two cannot coexist.

## Step 5 — PDU5, PDU7 and LED Brows LEDs

Only for those three. If your wheel isn't one of them, **skip it** — but do read
[item 4 of the diagnostic walkthrough](#4-hid-check-your-managers-usagepage), because the same
trap may exist in another manager.

```bash
simhub-devices install pdu5-leds --apply
```

The command makes **two** fixes, and **neither one alone is enough** (verified by
elimination):

1. **The wrong HID collection.** `PokornyiPEPDU5Manager` looks for the **vendor** collection
   (`usagePage 0xFF`), but the PDU5's descriptor is an **empty** Joystick collection with the
   vendor collection **nested** inside — and Wine only promotes sibling collections to a PDO.
   The only PDO that exists is `0x0001/0x04`, so the filter never matches. The patch swaps two
   opcodes in the IL.
2. **The NGen cache.** The prefix holds precompiled native images, and SimHub runs **32-bit**
   executing the one for `SimHub.Plugins`: **the DLL's IL is ignored**. Without removing the
   image, the patch is a no-op.

> ⚠️ **If you're going to patch anything in SimHub, remember NGen.** Probes built for **x64**
> JIT the IL from disk and "prove" the patch works, while the 32-bit app uses the native image
> and doesn't change at all — the two worlds never agree. To detect it: change a constant
> that's easy to observe in a manager that already works and see whether the app reacts. If it
> doesn't, it's NGen. The full case is in [CLAUDE.md](CLAUDE.md).

> ⚠️ **Why the failure was totally silent.** `PokornyiDriver`'s `Scanning ...` log line comes
> **after** the collection filter. With the wrong `usagePage` the list comes back empty and
> there is **not a single line** — no error, no "Scanning".

## After every SimHub update

An update reinstalls the original `libusb-1.0.dll` **and runs `ngen` again**. Without redoing
both steps, the screen and the PDU5's LEDs stop working **with no warning**:

```bash
simhub-devices post-update --apply
```

---

## My device isn't in the list

There is only one test bench here, and SimHub's catalog holds **more than 200 devices**. Almost
everything in this project matches by **transport**, not by model — the udev rule covers every
Pokornyi, the registry keys are global to the prefix, and every VoCore screen is `c872:1004`.
So there's a good chance your device simply works after steps 1 and 2.

If it doesn't, here's the walkthrough. It works for any brand.

### 1. Is it in SimHub's catalog at all?

```bash
SH=~/apps/linux-simracing-utils/pfx/drive_c/Program\ Files\ \(x86\)/SimHub
./venv/bin/python tools/ildump.py "$SH/SimHub.Plugins.dll" 'GetDevices>d__0' \
  | grep ldstr | awk -F"'" '{print $2}' | grep -vE '^[0-9A-F]{8}-' | sort -u
```

That lists the device names of the entire catalog. Filter by your brand:

```bash
... | grep -i ascher
```

If your device **doesn't show up**, it has no descriptor in SimHub and this project won't help
— the path there is SimHub's custom protocol (Arduino / generic serial), which is Wotever's
official wiki's subject, not ours.

### 2. Which transport is it?

This is the question that decides everything, and you answer it **before** touching the prefix.
Find your device's driver and see what it uses:

```bash
./venv/bin/python tools/ildump.py "$SH/BA63Driver.dll" "AscherDriver" \
  | grep -oE "HidDevice[A-Za-z]*|SerialPort[A-Za-z]*" | sort | uniq -c
```

| what shows up | transport | go to |
|---|---|---|
| `HidDeviceList`, `HidDeviceExtensions` | **HID** | steps [1](#step-1--udev-hardware-access) and [2](#step-2--winebus-registry-hid-devices) |
| `SerialPortBase`, `SerialPorts` | **serial** | step [3](#step-3--serial-devices-conspit-and-arduinos) |
| descriptor has a `BitmapDisplayDevice` | **VoCore screen** | step [4](#step-4--vocore-screens-the-libusb-bridge) |

⚠️ Two traps about where to look:

- The **managers** live in `SimHub.Plugins.dll`; the **drivers**, in `BA63Driver.dll`. Looking
  in the wrong DLL returns nothing and makes it look like the type doesn't exist.
- Wheels with screens are **composites**: they need the LEDs' transport **and** step 4. The LEDs
  are the **primary** device — if they don't connect, neither does the screen.

### 3. Find the VID/PID and follow the recipe

```bash
lsusb                              # with the device plugged in
simhub-devices doctor        # says whether it's already known and whether access is ok
```

If the VID isn't `0483` (Pokornyi), `c872` (Cube Controls / VoCore) or `3514` (Conspit), you
need to add it:

- **udev**: copy `udev/70-pokornyi.rules` to `udev/70-<brand>.rules` and change
  `idVendor`/`idProduct`. Keep the `70-` prefix and prefer `TAG+="uaccess"` over `MODE="0666"`
  — the former grants access only to the active session's user.
- **registry**: add the pair to the `CATALOGO` dictionary at the top of `tools/simhub-devices`
  and run `install registry --apply`. `EnableHidraw` is built from it.

Then **measure with `hidenum`** (step 2) — that's what tells you whether Wine started handing
over the real device or is still handing over the SDL-synthesized one.

### 4. HID: check YOUR manager's `usagePage`

⚠️ **This is the step nobody thinks to do, and it's what blocked the PDU5 for days.**

Each manager asks for a specific HID collection, and the argument comes out as a **constant in
the IL**. The value is **per manager**, not per brand — two devices from the same vendor can
ask for different things.

```bash
./venv/bin/python tools/ildump.py "$SH/SimHub.Plugins.dll" "PokornyiPEPDU5Manager" \
  | grep -B8 "GetDevice" | grep "ldc.i4"
```

The signature is `GetDevice(mapper, pid, usagePage, usage, BWButtonsCount, serial, vid)`, so
the constants come out in this order:

```
ldc.i4  51969 (0xCB01)   <- pid
ldc.i4  1                <- usagePage   ]  must match what
ldc.i4  4                <- usage       ]  hidenum showed
ldc.i4  0                <- BWButtonsCount
ldc.i4  1155 (0x483)     <- vid
```

Compare `usagePage`/`usage` against the line `hidenum` printed for your device. If they don't
match, the `MatchUsage` filter never matches and there is **not a single line in the log** — no
error, no "Scanning". In that case `tools/pdu5-leds-patch.py` serves as a template: it's two
same-size opcodes, and the script checks the assembly isn't strong-named before writing.

⚠️ **If you patch anything, remove the NGen cache** (`install pdu5-leds` already does, or
`clean-cache --apply`). Without that the patch is a no-op in the app — see
[step 5](#step-5--pdu5-pdu7-and-led-brows-leds).

### 5. "It failed" is not the same as "it was never tried"

This distinction is the reason the installer exists, and it changes where you look:

| what you see | what it means | where to look |
|---|---|---|
| `Searching device ...` in the UI | SimHub **is trying** and not finding it | access (udev), registry, VID/PID |
| device appears in the DEBUG log but doesn't connect | it **was scanned** and failed | driver, serial number, firmware |
| **nothing** in the DEBUG log | it **was never scanned** | `usagePage`, NGen cache — upstream of the driver |

To get the DEBUG log, adjust the level in `SimHubWPF.exe.config` inside the prefix.

### 6. Contribute the measurement back

If you do (or don't) get a device working, the data that matters is: **`hidenum`'s output**,
the **manager's constants**, and what showed up in the log. That's what makes it possible to
say whether the recipe generalizes or whether that model has something of its own. Open an
issue with those three.

> ⚠️ **Strip the serial number before pasting log output into an issue.** `install serial`
> shows the device's **USB serial**, and a serial is more than an identifier: several vendors
> use it as proof of ownership for warranty claims. If someone files a claim with **yours**,
> you're the one who can end up without coverage. Replace it with `<SERIAL>`.
>
> `doctor` also prints absolute paths containing your username — far less serious, but swap in
> `~/` if you like. **VID/PID and model can stay**: they're public vendor data, and they're
> exactly the technical content an issue needs.

---

## Known issues

### The device doesn't show up, and there's nothing in the log

In order of likelihood:

1. **`/dev/hidraw*` without ACLs** — step 1. The most common cause, and the most silent.
2. **`winebus` without `EnableHidraw`** — step 2. Check with `hidenum`: `usage 0x05` with
   `out 0` means you're still on the SDL-synthesized joystick.
3. **Wrong `usagePage` in the manager** — item 4 of the walkthrough above.
4. **NGen cache** swallowing a patch — step 5.

### Stale PnP entries

A leftover `Enum\HID\VID_xxxx&PID_xxxx*` — typical after swapping in another PCB of the same
model — makes the collection get registered but never become "present", and the driver receives
`null`. It shows up as a `NullReferenceException` every 2 s in the log. Deleting the entries and
letting Wine recreate them fixes it, but the cleanup is still manual: it requires editing
`system.reg` with the wineserver stopped.

### A HID probe returns an empty list

⚠️ **HID probes only work with SimHub STOPPED.** With it running,
`HidDeviceList.GetHidDevices` returns an empty list for **every** PID, including the ones it
has connected itself.

### Composites don't log `Device Status changed` with two fields

Not even the ones that work. They use the **three**-field form, with the `CompositeLabel`.
Concluding "the device never receives `Update()`" from the absence of the two-field log is
**invalid** — that wrong conclusion cost time here.

### `FindGamePath` / `CompatibilityStoreHelper` errors in the log

Those are a different matter (finding installed games, native Steam). They are **not** a clue
to a device problem — ignore them when diagnosing the Devices tab.

---

## Tools

| file | what it does |
|---|---|
| `tools/simhub-devices` | **the installer and the diagnostics** — dry-run by default |
| `tools/run-simhub` | starts the libusb bridge and SimHub in the right order, and cleans up on exit |
| `tools/pdu5-leds-patch.py` | the PDU5 `usagePage` patch (`--check` / `--apply` / `--revert`) |
| `tools/ildump.py` | disassembles a type's IL — calls and constants survive obfuscation |
| `tools/ilgrep.py` | finds who calls a given method |
| `tools/hidenum.c` | enumerates HID **from inside the prefix**: what SimHub actually sees |
| `tools/nameprobe.c` | shows which SetupAPI name API answers what (used in step 3) |
| `udev/70-pokornyi.rules` | ACLs for `/dev/hidraw*` for Pokornyi (`0483:cb??`) |
| `udev/70-vocore.rules` | write access to the VoCore screen's USB node (`c872:1004`) |

The two C probes build with mingw:

```bash
x86_64-w64-mingw32-gcc tools/hidenum.c   -o tools/hidenum.exe   -lhid -lsetupapi
x86_64-w64-mingw32-gcc tools/nameprobe.c -o tools/nameprobe.exe -lsetupapi
```

### SimHub is obfuscated

The public repo (`SHWotever/SimHub`) only carries the wiki and issues. **The source of truth is
the prefix's DLLs**, and the code is obfuscated — method names become CJK characters (`귇`,
`궏`…). What survives obfuscation, and what the tools above extract, is **strings, constants
and calls**.

The full technical detail — the Devices tab's architecture, the hypotheses tested and refuted,
and the methodological traps — lives in [CLAUDE.md](CLAUDE.md) (in Portuguese; it doubles as
LLM context).

---

## Safety

⚠️ **If you have a high-torque direct drive base, read this.** SimHub scans serial ports
looking for Arduinos, and an OpenFFBoard base shows up mapped on more than one COM. It ignores
text that isn't a valid command, so the risk is low — but **check that SimHub's Arduino
auto-detect is restricted to the right ports**, and never send `=`, `sys.0.save`,
`sys.0.format` or `odrv.*` calibration to a port that might be the base.

This repo's diagnostic probes are **read-only** by default, and the installer is **dry-run**
until you pass `--apply`. Writing to the prefix's registry is reversible (the installer backs
up `system.reg` first); writing to firmware is not.

---

## Scope and credits

- Sim racing on Linux, SimHub under Wine. One single setup: the author's.
- Nothing here ports or redistributes third-party software. SimHub belongs to
  **[Wotever](https://www.simhubdash.com/)**; `linux-simracing-utils` and Winecarte belong to
  **[srounce](https://github.com/srounce)**; the libusb bridge is
  **[ours](https://github.com/juliscreudo/wine-libusb-bridge)**, but lives in its own repo
  because it serves any Windows app under Wine.
- This repo is **analysis and configuration**.
- Personal project, no warranty, no support.

Licensed under **[GPL-3.0](LICENSE)**: use it, study it, modify it, fork it. Whoever distributes
a modified version must keep the source open under the same license — nobody closes this into a
proprietary product. ⚠️ The license covers **this repo**; SimHub remains Wotever's, under their
own terms.
