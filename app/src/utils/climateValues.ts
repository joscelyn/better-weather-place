import { fromUrl, type GeoTIFFImage } from "geotiff";

type ClimateRaster = {
  image: GeoTIFFImage;
  bounds: readonly [number, number, number, number];
  nodata: number | null;
};

const rasterCache = new Map<string, Promise<ClimateRaster>>();
const VALUE_SCALE = 0.1;

function climateCogUrl(layerId: string, month: number): string {
  const relative = `/data/1991-2020/raw/${layerId}/${String(month).padStart(2, "0")}.tif`;
  return new URL(relative, window.location.href).href;
}

async function loadRaster(layerId: string, month: number): Promise<ClimateRaster> {
  const url = climateCogUrl(layerId, month);
  let pending = rasterCache.get(url);
  if (!pending) {
    pending = fromUrl(url).then(async (tiff) => {
      const image = await tiff.getImage();
      return {
        image,
        bounds: image.getBoundingBox() as [number, number, number, number],
        nodata: image.getGDALNoData(),
      };
    });
    rasterCache.set(url, pending);
  }
  return pending;
}

export async function readClimateValue(
  layerId: string,
  month: number,
  longitude: number,
  latitude: number,
): Promise<number | null> {
  const { image, bounds, nodata } = await loadRaster(layerId, month);
  const [west, south, east, north] = bounds;
  if (longitude < west || longitude > east || latitude < south || latitude > north) { return null; }

  const x = Math.min(
    image.getWidth() - 1,
    Math.max(0, Math.floor(((longitude - west) / (east - west)) * image.getWidth())),
  );
  const y = Math.min(
    image.getHeight() - 1,
    Math.max(0, Math.floor(((north - latitude) / (north - south)) * image.getHeight())),
  );
  const rasters = await image.readRasters({ window: [x, y, x + 1, y + 1], samples: [0] });
  const rawValue = Number(rasters[0][0]);
  if (!Number.isFinite(rawValue) || (nodata !== null && rawValue === nodata)) { return null; }
  return rawValue * VALUE_SCALE;
}
