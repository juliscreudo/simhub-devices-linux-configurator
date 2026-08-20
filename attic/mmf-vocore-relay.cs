// Relay: device "Special : Generic MMF rendering V2" do SimHub -> /dev/shm.
//
// ⚠️ SUPERADO em 2026-08-18 pela ponte libusb -- ver attic/README.md. Fica como
// fallback para usar a tela FORA do SimHub. Os offsets abaixo sao de RUNTIME e
// valem para o SimHub 9.11.22; re-meça antes de confiar neles.
//
// Roda DENTRO do prefixo Wine (x64). Abre o MMF "SimHubDashRenderv2" que o
// device da aba Devices cria/atende e repassa os frames para um arquivo em
// Z:\dev\shm (= /dev/shm do Linux), onde o attic/mpro-dash-daemon.py os entrega ao
// framebuffer da tela VoCore (driver mpro_drm). Touch/acoes fazem o caminho
// inverso.
//
// Protocolo do lado SimHub (medido no IL de GenericMMFServiceV2, 2026-08-16):
//   - leitor escreve RequestedRenderWidth/HeightPixels + RequestActive;
//     o device so' conecta com isso preenchido (ConnectToScreen);
//   - leitor incrementa ReadCount como heartbeat; parado por ReadTimeout
//     (>= 5 s) o SimHub desconecta ("Rendering request timeout");
//   - frames 32bpp em double-buffer: WriteCount muda, LastFilledBuffer diz
//     qual RenderBuffer (1 ou 2) esta' pronto;
//   - CursorPressed/X/Y e ActionCommand1..4 sao lidos pelo pollCommands a
//     cada 5 ms (touch e botoes de overlay).
//
// ⚠️ OFFSETS DE RUNTIME, nao de marshaling: o SimHub acessa o MMF por
// ponteiro cru (bool = 1 byte). Marshal.OffsetOf da' valores ERRADOS (bool
// vira 4 bytes; a diferenca bate com mmfSize: 16589964 vs 16589949 = 5 bools
// x 3 bytes). Medidos com DynamicMethod+ldflda contra a DLL do SimHub 9.11.22,
// por uma sonda descartavel que NAO esta neste repo. Se o SimHub atualizar,
// refaca a medicao (a tecnica das sondas por reflexao esta no CLAUDE.md).
//
// Compilar (dentro do prefixo, tecnica do CLAUDE.md):
//   wine csc.exe /nologo /platform:x64 /unsafe /out:mmf-vocore-relay.exe mmf-vocore-relay.cs
// Rodar:
//   wine mmf-vocore-relay.exe [screenId]
// (screenId concatena no nome do MMF, igual ao campo do device; vazio = padrao)

using System;
using System.IO;
using System.IO.MemoryMappedFiles;
using System.Text;
using System.Threading;

static class Relay
{
    // ---- MMFHeaderV2, offsets de RUNTIME (SimHub 9.11.22) ----
    const int MMF_SIZE       = 16589949;
    const int OFF_ReqW       = 4;
    const int OFF_ReqH       = 8;
    const int OFF_ReqDouble  = 12;   // bool
    const int OFF_TouchMode  = 141;  // enum i32 (0=Unchanged)
    const int OFF_ReadTimeout= 146;
    const int OFF_Requester  = 150;  // ascii fixo 128
    const int OFF_ReadCount  = 278;
    const int OFF_ReqActive  = 282;  // bool
    const int OFF_CurPressed = 539;  // bool
    const int OFF_CurX       = 540;
    const int OFF_CurY       = 544;
    const int OFF_AC1        = 548;  // ActionCommand: +0 active(bool) +4 id(i32) +8 action(i32)
    const int OFF_BufCur     = 725;
    const int OFF_LastFilled = 729;
    const int OFF_WriteCount = 733;
    const int OFF_DataSize   = 737;
    const int OFF_RendW      = 741;
    const int OFF_RendH      = 745;
    const int OFF_BPR        = 749;
    const int OFF_Bright     = 753;
    const int OFF_RB1        = 885;      // RenderBuffer: +0 pixels, +8294400 UpdateCount
    const int OFF_RB2        = 8295417;
    const int RB_PIXELS      = 8294400;  // 1920*1080*4

    // ---- bridge em /dev/shm (layout proprio; ver mpro-dash-daemon.py) ----
    const int B_MAGIC = 0;   // 0x4D50524F "MPRO"
    const int B_ALIVE = 4;   // relay vivo (incrementa)
    const int B_RQW   = 8;   // daemon -> relay: resolucao pedida
    const int B_RQH   = 12;
    const int B_FRAME = 16;  // relay -> daemon: novo frame
    const int B_W     = 20;
    const int B_H     = 24;
    const int B_BPR   = 28;
    const int B_SIZE  = 32;
    const int B_BRIGHT= 36;
    const int B_TP    = 40;  // daemon -> relay: touch pressed
    const int B_TX    = 44;
    const int B_TY    = 48;
    const int B_ACT   = 52;  // daemon -> relay: Action (1=PrevScreen 2=Next 3=First 4..7=A-D)
    const int B_ACTSEQ= 56;
    const int B_PIX   = 128;
    const int BRIDGE_SIZE = B_PIX + RB_PIXELS;

    unsafe static void Main(string[] args)
    {
        string screenId = args.Length > 0 ? args[0] : "";
        string mmfName = "SimHubDashRenderv2" + screenId;

        // bridge primeiro: e' o daemon quem dita a resolucao
        var fs = new FileStream(@"Z:\dev\shm\simhub-mpro", FileMode.OpenOrCreate,
                                FileAccess.ReadWrite, FileShare.ReadWrite);
        fs.SetLength(BRIDGE_SIZE);
        var bmmf = MemoryMappedFile.CreateFromFile(fs, null, BRIDGE_SIZE,
                       MemoryMappedFileAccess.ReadWrite, null,
                       HandleInheritability.None, false);
        var bacc = bmmf.CreateViewAccessor(0, BRIDGE_SIZE);
        byte* bp = null;
        bacc.SafeMemoryMappedViewHandle.AcquirePointer(ref bp);
        *(int*)(bp + B_MAGIC) = 0x4D50524F;

        var mmf = MemoryMappedFile.CreateOrOpen(mmfName, MMF_SIZE,
                       MemoryMappedFileAccess.ReadWrite);
        var acc = mmf.CreateViewAccessor(0, MMF_SIZE);
        byte* p = null;
        acc.SafeMemoryMappedViewHandle.AcquirePointer(ref p);
        Console.WriteLine("[relay] MMF '" + mmfName + "' aberto; bridge Z:\\dev\\shm\\simhub-mpro");

        // identifica o leitor (ascii, buffer fixo de 128)
        byte[] who = Encoding.ASCII.GetBytes("mpro-bridge");
        for (int i = 0; i < who.Length; i++) p[OFF_Requester + i] = who[i];

        int lastWc = *(int*)(p + OFF_WriteCount);
        int lastActSeq = *(int*)(bp + B_ACTSEQ);
        int announced = 0;
        while (true)
        {
            int rqw = *(int*)(bp + B_RQW), rqh = *(int*)(bp + B_RQH);
            if (rqw > 0 && rqh > 0)
            {
                *(int*)(p + OFF_ReqW) = rqw;
                *(int*)(p + OFF_ReqH) = rqh;
                p[OFF_ReqDouble] = 1;
                *(int*)(p + OFF_ReadTimeout) = 10;
                p[OFF_ReqActive] = 1;
                *(int*)(p + OFF_ReadCount) = *(int*)(p + OFF_ReadCount) + 1; // heartbeat
                if (announced == 0)
                {
                    Console.WriteLine("[relay] pedindo " + rqw + "x" + rqh);
                    announced = 1;
                }
            }

            int wc = *(int*)(p + OFF_WriteCount);
            if (wc != lastWc)
            {
                lastWc = wc;
                int which = *(int*)(p + OFF_LastFilled);
                byte* src = p + (which == 2 ? OFF_RB2 : OFF_RB1);
                int size = *(int*)(p + OFF_DataSize);
                if (size > 0 && size <= RB_PIXELS)
                {
                    Buffer.MemoryCopy(src, bp + B_PIX, RB_PIXELS, size);
                    *(int*)(bp + B_W)      = *(int*)(p + OFF_RendW);
                    *(int*)(bp + B_H)      = *(int*)(p + OFF_RendH);
                    *(int*)(bp + B_BPR)    = *(int*)(p + OFF_BPR);
                    *(int*)(bp + B_SIZE)   = size;
                    *(int*)(bp + B_BRIGHT) = *(int*)(p + OFF_Bright);
                    *(int*)(bp + B_FRAME)  = *(int*)(bp + B_FRAME) + 1;
                }
            }

            // touch: daemon -> SimHub (pollCommands le a cada 5 ms)
            p[OFF_CurPressed] = (byte)(*(int*)(bp + B_TP) != 0 ? 1 : 0);
            *(int*)(p + OFF_CurX) = *(int*)(bp + B_TX);
            *(int*)(p + OFF_CurY) = *(int*)(bp + B_TY);

            // acoes de overlay (next/prev screen, A-D)
            int seq = *(int*)(bp + B_ACTSEQ);
            if (seq != lastActSeq)
            {
                lastActSeq = seq;
                *(int*)(p + OFF_AC1 + 4) = seq;                    // RequestId
                *(int*)(p + OFF_AC1 + 8) = *(int*)(bp + B_ACT);    // Action
                p[OFF_AC1] = 1;                                    // RequestActive
            }

            *(int*)(bp + B_ALIVE) = *(int*)(bp + B_ALIVE) + 1;
            Thread.Sleep(3);
        }
    }
}
