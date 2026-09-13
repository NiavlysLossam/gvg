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
  is_offline?: boolean;
  payment_method?: string | null;
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

export type DuplicateDirection =
  | 'stand_axis_right'
  | 'stand_axis_left'
  | 'stand_axis_front'
  | 'stand_axis_back'
  | 'cardinal_east'
  | 'cardinal_west'
  | 'cardinal_north'
  | 'cardinal_south';

export interface SpotBatchCreateInput {
  spots: SpotCreateInput[];
}

export interface SpotBatchCreateResponse extends SpotFeatureCollection {
  created_count: number;
}

export interface SpotRenumberItem {
  spot_id: string;
  label: string;
}

export interface SpotBatchRenumberInput {
  spot_ids?: string[];
  prefix?: string;
  start_number?: number;
  zero_padding?: number;
  renumberings?: SpotRenumberItem[];
}

export interface SpotBatchRenumberResponse extends SpotFeatureCollection {
  updated_count: number;
}


