/* Enumera os devices HID visiveis para uma aplicacao Windows DENTRO do
 * prefixo, do mesmo jeito que o SimHub faz: SetupDiGetClassDevs(HidD_GetHidGuid)
 * -> CreateFile -> HidD_GetAttributes + HidP_GetCaps.
 *
 * Responde: o SimHub enxerga o canal vendor do device, ou so' o joystick
 * sintetizado pelo SDL?
 *
 *   sem argumento  -> TODOS os devices
 *   com argumentos -> so' os VIDs dados, em hex (ex: `hidenum 0483 c872`)
 *   --serial       -> mostra o instance ID inteiro (por padrao e' mascarado)
 *
 * ⚠️ O DevicePath embute o NUMERO DE SERIE do device, e a saida desta ferramenta
 * e' justamente o que os READMEs pedem para colar num issue. Serial nao e'
 * metadado: varios fabricantes o usam como prova de titularidade em garantia.
 * Por isso o instance ID sai como <INSTANCIA> por padrao -- VID/PID, caps e
 * usage, que sao o dado tecnico, continuam completos. Use --serial quando
 * precisar distinguir duas unidades iguais (LedsGenericManagerWithSerialNumber)
 * e a saida NAO for sair da sua maquina.
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
#include <string.h>

static int mostrar_serial = 0;

static int vid_pedido(int argc, char **argv, unsigned vid)
{
    int tem_filtro = 0;
    for (int i = 1; i < argc; i++) {
        if (argv[i][0] == '-') continue;    /* opcao, nao e' VID */
        tem_filtro = 1;
        if ((unsigned)strtoul(argv[i], NULL, 16) == vid) return 1;
    }
    return !tem_filtro;                     /* sem filtro: tudo */
}

/* `\\?\hid#vid_0483&pid_cb01&mi_00#<INSTANCIA>#{guid}` -- o terceiro campo e'
 * o instance ID, que carrega o serial. Mascara-o preservando o resto. */
static void print_path(const WCHAR *p)
{
    if (mostrar_serial) { printf("%ls\n", p); return; }
    const WCHAR *a = NULL, *b = NULL;
    int n = 0;
    for (const WCHAR *q = p; *q; q++)
        if (*q == L'#') { n++; if (n == 2) a = q; else if (n == 3) { b = q; break; } }
    if (!a || !b) { printf("%ls\n", p); return; }
    printf("%.*ls#<INSTANCIA>%ls\n", (int)(a - p), p, b);
}

/* VID a partir do proprio DevicePath (`\\?\hid#vid_0483&pid_cb40#...`), para
 * quando nao ha' handle: sem isto o ramo [sem acesso] ignorava o filtro e
 * `hidenum 0483` despejava device de todo VID, contrariando o proprio uso. */
static unsigned vid_do_path(const WCHAR *p)
{
    for (; *p; p++) {
        if ((p[0] == L'v' || p[0] == L'V') && (p[1] == L'i' || p[1] == L'I') &&
            (p[2] == L'd' || p[2] == L'D') && p[3] == L'_')
            return (unsigned)wcstoul(p + 4, NULL, 16);
    }
    return 0xFFFFFFFFu;                     /* desconhecido: nunca casa filtro */
}

int main(int argc, char **argv)
{
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--serial")) mostrar_serial = 1;

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
        /* ⚠️ a primeira chamada SEMPRE "falha" (ERROR_INSUFFICIENT_BUFFER); o que
         * importa e' `need`. Se ela falhar por outro motivo, need fica 0 e o
         * `det->cbSize = ...` abaixo escreveria fora de uma alocacao vazia. */
        if (need < sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W)) continue;
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
                printf("    path: "); print_path(det->DevicePath);
                mostrados++;
            }
            CloseHandle(h);
        } else if (vid_pedido(argc, argv, vid_do_path(det->DevicePath))) {
            /* Nao da' para ler VID/PID sem handle: o proprio DevicePath os
             * carrega (hid#vid_xxxx&pid_xxxx...), e e' de la' que sai o filtro.
             * Imprime -- sumir da lista e' pior que aparecer incompleto. */
            printf("[sem acesso] "); print_path(det->DevicePath);
            mostrados++;
        }
        free(det);
    }
    SetupDiDestroyDeviceInfoList(set);
    printf("\n-- %d interfaces HID no prefixo, %d exibidas --\n", total, mostrados);
    return 0;
}
