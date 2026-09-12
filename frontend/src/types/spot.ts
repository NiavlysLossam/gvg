export interface GeoJSONPolygon {
  type: 'Polygon';
  coordinates: number[][][]; // [[[x, y], ...]]
}

export interface SpotProperties {
  id: string;
  event_id: string;
  label: string;
  linear_meters: number;
  price_cents: number;
  price: number;
  status: 'available' | 'locked' | 'reserved' | 'blocked';
  locked_until?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SpotFeature {
  type: 'Feature';
  id: string;
  geometry: GeoJSONPolygon;
  properties: SpotProperties;
}

export interface SpotFeatureCollection {
  type: 'FeatureCollection';
  features: SpotFeature[];
}

export interface SpotCreateInput {
  label: string;
  linear_meters: number;
  price_cents?: number;
  price?: number;
  geometry: GeoJSONPolygon;
}

export interface SpotUpdateInput {
  label?: string;
  linear_meters?: number;
  price_cents?: number;
  price?: number;
  geometry?: GeoJSONPolygon;
  status?: 'available' | 'locked' | 'reserved' | 'blocked';
}

