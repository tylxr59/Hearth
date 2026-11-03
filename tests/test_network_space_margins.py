"""Space margins in the network writer, checked against the 2026-11-03 measurement."""

import re
from pathlib import Path

SOURCE = Path("firmware/network_writer/data.c").read_text()


def margin(name):
    return int(re.search(rf"#define {name} (\d+)U", SOURCE)[1])


def test_install_margin_always_leaves_room_for_its_own_restore():
    assert margin("HN_SHARED_INSTALL_MARGIN") >= margin("HN_RESTORE_MARGIN") + 256 * 1024
    assert '#error "an install must leave room for its own guided restore"' in SOURCE


def test_measured_unit_installs_and_can_restore_afterwards():
    # Real sizes from the owner's 2026-11-03 kit and no-commit preflight.
    files = (5_122_360, 687_028, 3_063)
    available, core_reserve = 13_217_792, 216_202
    total, largest = sum(files), max(files)
    install = total + largest + margin("HN_SHARED_INSTALL_MARGIN") + core_reserve
    assert install <= available
    # After installing, the replacements are added and the originals kept.
    # Conservative node overhead: 72 bytes per 4 KiB page plus 64 KiB.
    overhead = -(-total // 4096) * 72 + 65536
    after = available - total - overhead - core_reserve
    assert largest + margin("HN_RESTORE_MARGIN") <= after


def test_copy_based_install_bound_is_unchanged():
    assert "3U*total+2U*1048576U" in SOURCE
