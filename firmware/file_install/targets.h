/* Original fixed commissioning allowlist (MIT); paths are root-relative. */
#ifndef HEARTH_FILE_TARGETS_H
#define HEARTH_FILE_TARGETS_H
static const char *const hearth_target_paths[HEARTH_TARGET_COUNT] = {
    "nestlabs/lib/libnlwebservice.so", "etc/ssl/certs/ca-bundle.pem",
    "etc/ssl/certs/nest-crl-bundle.pem", "etc/ntp.conf",
    "nestlabs/lib/libhearth-settings-compat.so", "nestlabs/sbin/hearth-nlclient",
    "etc/init.d/nestlabs", "settings.config", "etc/nestlabs/client.config"
};
#endif
