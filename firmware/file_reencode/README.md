# Original-file re-encoding

A narrowly scoped C helper that rewrites a plan's exact original files with
NONE encoding. It is compiled **instead of** `file_install/posix.c`: it reuses
that file's bounded private helpers and adds a separate, explicit
force-rewrite API. Ordinary install and restore behaviour is unchanged.

The file writer and network writer compile it in (`firmware/file_writer/` and
`firmware/network_writer/`). It only runs on a target kernel that writes NONE
encoding only, and it keeps the writers' journal, archive-inventory and
original-byte checks.

It was written to recover from the LZO-compressed files an early writer
produced, which the native kernel cannot read. See the
[compression recovery note](../../docs/development/history/research/compression-recovery-2026-10-31.md)
and the JFFS2 section of
[findings](../../docs/development/findings.md#filesystem-jffs2).
