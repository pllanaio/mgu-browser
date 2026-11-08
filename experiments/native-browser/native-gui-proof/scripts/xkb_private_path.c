#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdlib.h>
__attribute__((constructor)) static void configure_private_xkb(void) { char **path = (char **)dlsym(RTLD_DEFAULT, "XkbBinDirectory"); const char *configured = getenv("MGU_XKB_BIN_DIR"); if (path && configured && configured[0] == '/') *path = (char *)configured; }
