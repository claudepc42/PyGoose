#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdio.h>
#include <mach-o/dyld.h>

static void strip_last(char *path) {
    char *p = strrchr(path, '/');
    if (p && p != path) *p = '\0';
}

int main(void) {
    char buf[4096];
    uint32_t sz = sizeof(buf);
    if (_NSGetExecutablePath(buf, &sz) != 0) {
        FILE *f = fopen("/tmp/pygoose_launcher.log", "w");
        if (f) { fprintf(f, "FAIL: _NSGetExecutablePath\n"); fclose(f); }
        return 1;
    }

    char resolved[4096];
    if (!realpath(buf, resolved)) {
        FILE *f = fopen("/tmp/pygoose_launcher.log", "w");
        if (f) { fprintf(f, "FAIL: realpath(%s)\n", buf); fclose(f); }
        return 1;
    }

    /* Walk up: filename -> Contents/MacOS -> Contents -> .app -> parent dir */
    strip_last(resolved);
    strip_last(resolved);
    strip_last(resolved);
    strip_last(resolved);

    /* Log sits next to the .app where it's easy to find */
    char logpath[4096];
    snprintf(logpath, sizeof(logpath), "%s/pygoose_launcher.log", resolved);
    FILE *log = fopen(logpath, "w");
    if (log) fprintf(log, "launcher started\nparent dir: %s\n", resolved);

    char binary[4096];
    snprintf(binary, sizeof(binary), "%s/PyGoose", resolved);
    if (log) fprintf(log, "binary path: %s\n", binary);

    char cmd[8192];
    snprintf(cmd, sizeof(cmd), "/usr/bin/xattr -cr \"%s\" 2>/dev/null", binary);
    int xr = system(cmd);
    if (log) fprintf(log, "xattr returned: %d\n", xr);

    if (log) { fprintf(log, "calling execv...\n"); fclose(log); }

    char *argv[] = { binary, NULL };
    execv(binary, argv);

    /* execv only returns on failure */
    log = fopen(logpath, "a");
    if (log) { fprintf(log, "FAIL: execv failed\n"); fclose(log); }
    return 1;
}
