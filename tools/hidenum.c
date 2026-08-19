/* Enumera os devices HID visiveis para uma aplicacao Windows DENTRO do
 * prefixo, do mesmo jeito que o SimHub faz: SetupDiGetClassDevs(HidD_GetHidGuid)
 * -> CreateFile -> HidD_GetAttributes + HidP_GetCaps.
 *
 * Responde: o SimHub enxerga o canal vendor do device, ou so' o joystick
 * sintetizado pelo SDL?
 *
 *   sem argumento  -> TODOS os devices
 *   com argumentos -> so' os VIDs dados, em hex (ex: `hidenum 0483 c872`)
 *
 * ⚠️ Derivado do ~/apps/conspit-ares-linux/tools/hidenum.c, que tem o filtro
 * `attr.VendorID == 0x3514` CRAVADO NO CODIGO. Rodar aquele aqui devolve
 * lista vazia para Pokornyi/Cube Controls e parece que o device nao existe --
 * custou uma conclusao errada em 2026-08-16, contradita pelo usuario, que via
 * os tres MCP conectados no SimHub enquanto a ferramenta dizia que nao havia
 * nenhum VID_0483.
 *
 * ⚠️ Um device que outro processo abriu SEM compartilhamento nao e' aberto
 * aqui; a linha sai marcada [sem acesso] usando so' o que o SetupAPI da',
 * em vez de sumir da lista.
 *
 * x86_64-w64-mingw32-gcc hidenum.c -o hidenum.exe -lhid -lsetupapi
 */
#include <windows.h>
#include <setupapi.h>
#include <hidsdi.h>
#include <stdio.h>
#include <stdlib.h>

static int vid_pedido(int argc, char **argv, unsigned vid)
{
    if (argc < 2) return 1;                 /* sem filtro: tudo */
    for (int i = 1; i < argc; i++)
        if ((unsigned)strtoul(argv[i], NULL, 16) == vid) return 1;
    return 0;
}

int main(int argc, char **argv)
{
    GUID guid;
    HidD_GetHidGuid(&guid);

    HDEVINFO set = SetupDiGetClassDevsW(&guid, NULL, NULL,
                                        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if (set == INVALID_HANDLE_VALUE) { printf("SetupDiGetClassDevs falhou\n"); return 1; }

    int total = 0, mostrados = 0;
    SP_DEVICE_INTERFACE_DATA iface = { .cbSize = sizeof(iface) };
    for (DWORD i = 0; SetupDiEnumDeviceInterfaces(set, NULL, &guid, i, &iface); i++) {
        DWORD need = 0;
        SetupDiGetDeviceInterfaceDetailW(set, &iface, NULL, 0, &need, NULL);
        SP_DEVICE_INTERFACE_DETAIL_DATA_W *det = malloc(need);
        if (!det) continue;
        det->cbSize = sizeof(*det);
        if (!SetupDiGetDeviceInterfaceDetailW(set, &iface, det, need, NULL, NULL)) {
            free(det); continue;
        }
        total++;

        HANDLE h = CreateFileW(det->DevicePath, GENERIC_READ | GENERIC_WRITE,
                               FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
                               OPEN_EXISTING, 0, NULL);
        if (h == INVALID_HANDLE_VALUE)
            h = CreateFileW(det->DevicePath, 0,
                            FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
                            OPEN_EXISTING, 0, NULL);

        if (h != INVALID_HANDLE_VALUE) {
            HIDD_ATTRIBUTES attr = { .Size = sizeof(attr) };
            HidD_GetAttributes(h, &attr);

            if (vid_pedido(argc, argv, attr.VendorID)) {
                PHIDP_PREPARSED_DATA pp = NULL;
                HIDP_CAPS caps = { 0 };
                if (HidD_GetPreparsedData(h, &pp)) {
                    HidP_GetCaps(pp, &caps);
                    HidD_FreePreparsedData(pp);
                }
                WCHAR prod[256] = { 0 };
                HidD_GetProductString(h, prod, sizeof(prod));

                printf("VID_%04X PID_%04X  usage_page 0x%04X usage 0x%02X  "
                       "in %u out %u feat %u  \"%ls\"\n",
                       attr.VendorID, attr.ProductID,
                       caps.UsagePage, caps.Usage,
                       caps.InputReportByteLength, caps.OutputReportByteLength,
                       caps.FeatureReportByteLength, prod);
                printf("    path: %ls\n", det->DevicePath);
                mostrados++;
            }
            CloseHandle(h);
        } else {
            /* Nao da' para ler VID/PID sem handle: o proprio DevicePath os
             * carrega (hid#vid_xxxx&pid_xxxx...). Imprime sempre -- sumir da
             * lista e' pior que aparecer incompleto. */
            printf("[sem acesso] %ls\n", det->DevicePath);
            mostrados++;
        }
        free(det);
    }
    SetupDiDestroyDeviceInfoList(set);
    printf("\n-- %d interfaces HID no prefixo, %d exibidas --\n", total, mostrados);
    return 0;
}
