export type MapType = 'geographic' | 'planar';

export type EventStatus = 'draft' | 'published' | 'archived';

export interface EventModel {
  id: string;
  slug: string;
  title: string;
  description?: string | null;
  map_type: MapType;
  background_image_url?: string | null;
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
  stripe_account_id?: string | null;
  manual_approval_required: boolean;
  rules_text?: string | null;
  status: EventStatus;
  created_at: string;
  updated_at: string;
}

export interface EventCreateInput {
  title: string;
  description?: string;
  map_type: MapType;
  background_image_url?: string;
  start_date: string;
  end_date: string;
  setup_start_time?: string;
  setup_end_time?: string;
  public_start_time?: string;
  public_end_time?: string;
  location_address?: string;
  organizer_email?: string;
  price_per_meter: number;
  manual_approval_required?: boolean;
  rules_text?: string;
}

export interface EventListResponse {
  items: EventModel[];
  total: number;
}

