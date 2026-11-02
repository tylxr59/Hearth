# Hearth artwork

The project owner supplied the orange flame artwork for Hearth branding. The
canonical PNG is `homeassistant/custom_components/hearth/brand/icon.png`, also
used by the README and bundled by the HA source packager. The supplied canvas
and pixels are preserved. The committed PNG contains only image/rendering chunks;
EXIF, text, timestamps, location and other ancillary metadata are absent.

The custom integration ships its own local `brand/` asset. HA can use the square
icon as the logo and as the fallback for dark/high-density variants, without
fetching Hearth's artwork from an external brands CDN. The isolated real-HA
check verifies the actual icon/logo/dark/high-density endpoints return its bytes.

The supplied high-resolution raster is retained as-is; no transparent-background
variant or redesigned mark has been generated. A future submission to the shared
brands repository would need to meet that repository's current asset guidelines.

Reference: [HA integration branding](https://contributors.home-assistant.io/core/integrations/brands/).
