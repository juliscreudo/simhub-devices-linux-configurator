/* Para o no PnP do H.AO criado a mao: qual API de nome devolve o que?
 *
 *   SPDRP_DEVICEDESC / SPDRP_FRIENDLYNAME  (legado, RegQueryValue direto)
 *   DEVPKEY_NAME / DEVPKEY_Device_FriendlyName / _DeviceDesc (moderno,
 *   SetupDiGetDevicePropertyW -- o Wine le da subchave Properties\{...})
 *
 * O WoteverCommon do SimHub monta o "Name" do device por uma dessas; a regex
 * de porta ("(COMxx)") roda sobre esse Name.
 */
#include <windows.h>
#include <setupapi.h>
#define INITGUID
#include <devpkey.h>
#include <stdio.h>

static void devprop(HDEVINFO di, SP_DEVINFO_DATA *dd, const DEVPROPKEY *k,
                    const char *rot)
{
    WCHAR buf[512] = {0};
    DEVPROPTYPE tipo;
    if (SetupDiGetDevicePropertyW(di, dd, k, &tipo, (PBYTE)buf, sizeof(buf), NULL, 0))
        printf("   %-28s %ls\n", rot, buf);
    else
        printf("   %-28s <erro %lu>\n", rot, GetLastError());
}

static void regprop(HDEVINFO di, SP_DEVINFO_DATA *dd, DWORD id, const char *rot)
{
    char buf[512] = {0};
    if (SetupDiGetDeviceRegistryPropertyA(di, dd, id, NULL, (PBYTE)buf,
                                          sizeof(buf), NULL))
        printf("   %-28s %s\n", rot, buf);
    else
        printf("   %-28s <erro %lu>\n", rot, GetLastError());
}

int main(void)
{
    HDEVINFO di = SetupDiGetClassDevsA(NULL, "USB", NULL,
                                       DIGCF_ALLCLASSES | DIGCF_PRESENT);
    SP_DEVINFO_DATA dd = {.cbSize = sizeof(dd)};
    for (DWORD i = 0; SetupDiEnumDeviceInfo(di, i, &dd); i++) {
        char inst[512] = {0};
        SetupDiGetDeviceInstanceIdA(di, &dd, inst, sizeof(inst), NULL);
        if (!strstr(inst, "346534443132") || strstr(inst, "MI_"))
            continue;
        printf("%s\n", inst);
        regprop(di, &dd, SPDRP_DEVICEDESC,   "SPDRP_DEVICEDESC");
        regprop(di, &dd, SPDRP_FRIENDLYNAME, "SPDRP_FRIENDLYNAME");
        devprop(di, &dd, &DEVPKEY_NAME,                  "DEVPKEY_NAME");
        devprop(di, &dd, &DEVPKEY_Device_FriendlyName,   "DEVPKEY_Device_FriendlyName");
        devprop(di, &dd, &DEVPKEY_Device_DeviceDesc,     "DEVPKEY_Device_DeviceDesc");
        devprop(di, &dd, &DEVPKEY_Device_BusReportedDeviceDesc,
                                                         "DEVPKEY_BusReportedDeviceDesc");
    }
    SetupDiDestroyDeviceInfoList(di);
    return 0;
}
