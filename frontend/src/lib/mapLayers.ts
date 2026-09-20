import L from 'leaflet';

/**
 * Shared map layer definitions for SpotEditor and PublicMap.
 * All IGN layers use the public `decouverte` key — no authentication required.
 */

export interface PresetLayer {
  id: string;
  label: string;
  url: string;
  attribution: string;
  maxNativeZoom: number;
}

export const PRESET_LAYERS: PresetLayer[] = [
  {
    id: 'osm',
    label: 'Plan OSM',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
    maxNativeZoom: 19,
  },
  {
    id: 'satellite-esri',
    label: 'Satellite ESRI',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution:
      'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP',
    maxNativeZoom: 19,
  },
  {
    id: 'ign-ortho',
    label: 'Photos Aériennes IGN',
    url: 'https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image%2Fjpeg',
    attribution: '&copy; IGN Géoplateforme',
    maxNativeZoom: 19,
  },
  {
    id: 'ign-plan',
    label: 'Plan IGN',
    url: 'https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image%2Fpng',
    attribution: '&copy; IGN Géoplateforme',
    maxNativeZoom: 19,
  },
  {
    id: 'ign-cadastre',
    label: 'Cadastre',
    url: 'https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=CADASTRALPARCELS.PARCELLAIRE_EXPRESS&STYLE=normal&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image%2Fpng',
    attribution: '&copy; IGN Géoplateforme',
    maxNativeZoom: 19,
  },
];

export const CUSTOM_LAYER_ID = 'custom';

/**
 * Build a Leaflet TileLayer for the given URL and attribution string.
 */
export function buildTileLayer(url: string, attribution: string, maxNativeZoom = 19): L.TileLayer {
  return L.tileLayer(url, {
    maxZoom: 22,
    maxNativeZoom,
    attribution,
  });
}

/**
 * Find a preset by its tile URL (used to initialise the selector from a stored wms_url).
 * Returns undefined if no preset matches (= custom layer).
 */
export function findPresetByUrl(wmsUrl: string | null | undefined): PresetLayer | undefined {
  if (!wmsUrl) return undefined;
  return PRESET_LAYERS.find((p) => p.url === wmsUrl);
}

/**
 * Return the default OSM preset layer.
 */
export function getDefaultLayer(): PresetLayer {
  return PRESET_LAYERS[0];
}
