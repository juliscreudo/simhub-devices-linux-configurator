#!/usr/bin/env python3
"""Daemon: /dev/shm/simhub-mpro -> framebuffer da tela VoCore (mpro_drm).

A outra ponta e' o tools/mmf-vocore-relay.cs, rodando dentro do prefixo do
SimHub: ele conecta o device "Special : Generic MMF rendering V2" da aba
Devices e copia cada frame para o bridge em /dev/shm. Este daemon:

  1. acha o framebuffer do mpro_drm (fb cujo device ancestral e' USB c872:1004);
  2. escreve a resolucao da tela no bridge (o relay a repassa ao SimHub, que
     renderiza o dash JA' no tamanho certo -- sem scaling);
  3. copia cada frame novo para o framebuffer, respeitando os strides;
  4. (volta) touch do kernel -> bridge -> relay -> SimHub  [fase 2]
  5. (volta) brightness do SimHub -> backlight do mpro     [best-effort]

Frames do SimHub sao BGRA 32bpp little-endian == XRGB8888 do DRM: copia
direta quando o fb e' 32bpp; conversao para RGB565 se for 16bpp (numpy).

⚠️ O compositor nao pode estar dono da tela: desabilite o output do mpro nas
configuracoes de tela do KDE antes de rodar (senao o KWin e o daemon brigam
pelo mesmo CRTC e o resultado e' indefinido).

Uso:  python3 tools/mpro-dash-daemon.py [--fb /dev/fbN] [--test]
      --test: escreve um degrade e sai (valida o caminho ate' a tela sem SimHub)
"""
import argparse
import ctypes
import fcntl
import mmap
import os
import struct
import sys
import time

BRIDGE = "/dev/shm/simhub-mpro"
MAGIC = 0x4D50524F
PIX_MAX = 1920 * 1080 * 4
BRIDGE_SIZE = 128 + PIX_MAX

# offsets do bridge (espelham o relay)
B_MAGIC, B_ALIVE, B_RQW, B_RQH, B_FRAME = 0, 4, 8, 12, 16
B_W, B_H, B_BPR, B_SIZE, B_BRIGHT = 20, 24, 28, 32, 36
B_TP, B_TX, B_TY, B_ACT, B_ACTSEQ, B_PIX = 40, 44, 48, 52, 56, 128

FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602


def acha_fb_mpro():
    """O fb do mpro: sobe do device do fb ate' achar idVendor/idProduct USB."""
    for fb in sorted(os.listdir("/sys/class/graphics")):
        if not fb.startswith("fb"):
            continue
        d = os.path.realpath(f"/sys/class/graphics/{fb}/device")
        p = d
        for _ in range(8):
            vid = os.path.join(p, "idVendor")
            if os.path.exists(vid):
                v = open(vid).read().strip()
                pid = open(os.path.join(p, "idProduct")).read().strip()
                if (v, pid) == ("c872", "1004"):
                    return f"/dev/{fb}"
                break
            p = os.path.dirname(p)
    return None


def fb_info(fd):
    v = fcntl.ioctl(fd, FBIOGET_VSCREENINFO, bytes(160))
    xres, yres = struct.unpack_from("<II", v, 0)
    bpp = struct.unpack_from("<I", v, 24)[0]
    f = fcntl.ioctl(fd, FBIOGET_FSCREENINFO, bytes(80))
    line_length = struct.unpack_from("<I", f, 48)[0]
    return xres, yres, bpp, line_length


def acha_backlight():
    base = "/sys/class/backlight"
    if not os.path.isdir(base):
        return None
    for b in os.listdir(base):
        # o mpro registra backlight proprio; num setup com uma tela USB so',
        # qualquer entrada nova dele e' a certa -- filtra por 'mpro' se houver
        if "mpro" in b.lower():
            return os.path.join(base, b)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fb")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()

    fbdev = args.fb or acha_fb_mpro()
    if not fbdev:
        sys.exit("framebuffer do mpro nao encontrado (modulo carregado? sudo insmod mpro.ko)")
    fd = os.open(fbdev, os.O_RDWR)
    xres, yres, bpp, stride = fb_info(fd)
    print(f"[daemon] {fbdev}: {xres}x{yres} {bpp}bpp stride={stride}")
    fbsize = stride * yres
    fbm = mmap.mmap(fd, fbsize)

    if args.test:
        px = bytearray(stride)
        for y in range(yres):
            for x in range(xres):
                if bpp == 32:
                    struct.pack_into("<I", px, x * 4,
                                     (x * 255 // xres) << 16 | (y * 255 // yres) << 8 | 0x40)
                else:
                    r = x * 31 // xres
                    g = y * 63 // yres
                    struct.pack_into("<H", px, x * 2, (r << 11) | (g << 5) | 8)
            fbm[y * stride:y * stride + stride] = px
        print("[daemon] padrao de teste escrito; conferir a tela")
        return

    np = None
    if bpp == 16:
        try:
            import numpy
            np = numpy
        except ImportError:
            sys.exit("fb de 16bpp exige numpy para conversao (pacman -S python-numpy)")

    # bridge: cria/dimensiona e pede a resolucao da tela
    bfd = os.open(BRIDGE, os.O_RDWR | os.O_CREAT, 0o644)
    os.ftruncate(bfd, BRIDGE_SIZE)
    bm = mmap.mmap(bfd, BRIDGE_SIZE)

    def bset(off, val):
        struct.pack_into("<i", bm, off, val)

    def bget(off):
        return struct.unpack_from("<i", bm, off)[0]

    bset(B_RQW, xres)
    bset(B_RQH, yres)
    print(f"[daemon] pedindo dash {xres}x{yres}; aguardando relay/SimHub…")

    backlight = acha_backlight()
    max_bright = None
    if backlight:
        max_bright = int(open(os.path.join(backlight, "max_brightness")).read())
        print(f"[daemon] backlight: {backlight} (max {max_bright})")

    last_frame = bget(B_FRAME)
    last_bright = -1
    avisado = False
    while True:
        frame = bget(B_FRAME)
        if frame == last_frame:
            time.sleep(0.004)
            continue
        last_frame = frame
        if not avisado:
            print("[daemon] frames chegando do SimHub ✔")
            avisado = True

        w, h, bpr = bget(B_W), bget(B_H), bget(B_BPR)
        w, h = min(w, xres), min(h, yres)
        if bpp == 32:
            if bpr == stride and w == xres:
                fbm[:h * stride] = bm[B_PIX:B_PIX + h * stride]
            else:
                for y in range(h):
                    fbm[y * stride:y * stride + w * 4] = \
                        bm[B_PIX + y * bpr:B_PIX + y * bpr + w * 4]
        else:  # 16bpp: BGRA -> RGB565
            a = np.frombuffer(bm, dtype=np.uint8,
                              count=h * bpr, offset=B_PIX).reshape(h, bpr // 4, 4)[:, :w, :]
            r = (a[:, :, 2] >> 3).astype(np.uint16)
            g = (a[:, :, 1] >> 2).astype(np.uint16)
            b = (a[:, :, 0] >> 3).astype(np.uint16)
            out = ((r << 11) | (g << 5) | b)
            fbv = np.frombuffer(fbm, dtype=np.uint16,
                                count=h * stride // 2).reshape(h, stride // 2)
            fbv[:, :w] = out

        if backlight:
            br = bget(B_BRIGHT)
            if br != last_bright and 0 <= br <= 100:
                last_bright = br
                try:
                    with open(os.path.join(backlight, "brightness"), "w") as f:
                        f.write(str(br * max_bright // 100))
                except PermissionError:
                    pass  # sem ACL no sysfs; brightness fica pelo SimHub apenas


if __name__ == "__main__":
    main()
