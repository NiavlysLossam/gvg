import { GeoJSONPolygon } from './spot';

export type PublicSpotStatus = 'available' | 'locked' | 'reserved' | 'blocked';

export interface PublicSpotProperties {
  id: string;
  event_id: string;
  label: string;
  linear_meters: number;
  price_cents: number;
  price: number;
  status: PublicSpotStatus;
  locked_until?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface PublicSpotFeature {
  type: 'Feature';
  id: string;
  geometry: GeoJSONPolygon;
  properties: PublicSpotProperties;
}

export interface PublicSpotFeatureCollection {
  type: 'FeatureCollection';
  features: PublicSpotFeature[];
}

export interface PublicEventResponse {
  id: string;
  title: string;
  slug: string;
  description?: string | null;
  map_type: 'geographic' | 'planar';
  background_image_url?: string | null;
  center_latitude?: number | null;
  center_longitude?: number | null;
  default_zoom?: number | null;
  price_per_meter_cents: number;
  price_per_meter: number;
  start_date: string;
  end_date: string;
  setup_start_time?: string | null;
  setup_end_time?: string | null;
  public_start_time?: string | null;
  public_end_time?: string | null;
  location_address?: string | null;
  organizer_email?: string | null;
  rules_text?: string | null;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface LockSpotRequest {
  session_token: string;
}

export interface UnlockSpotRequest {
  session_token: string;
}

export interface CartSpotItem {
  id: string;
  label: string;
  linear_meters: number;
  price_cents: number;
  price: number;
  locked_until: string;
}

export interface CartResponse {
  session_token: string;
  spots: CartSpotItem[];
  total_count: number;
  total_linear_meters: number;
  total_price_cents: number;
  total_price: number;
  expires_at?: string | null;
}

