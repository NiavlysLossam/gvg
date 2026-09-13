export interface GuestOrderCreate {
  session_token: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  street_address: string;
  postal_code: string;
  city: string;
  honor_declaration_accepted: boolean;
}

export interface BookingItemOut {
  id: string;
  order_id: string;
  spot_id: string;
  price_cents: number;
  price: number;
  spot_label?: string | null;
  spot_linear_meters?: number | null;
  created_at?: string | null;
}

export interface OrderOut {
  id: string;
  event_id: string;
  order_number: string;
  first_name: string;
  last_name: string;
  email?: string | null;
  phone: string;
  street_address?: string | null;
  postal_code?: string | null;
  city?: string | null;
  honor_declaration_accepted: boolean;
  honor_declaration_accepted_at: string;
  total_price_cents: number;
  total_price: number;
  status: 'pending' | 'pending_approval' | 'confirmed' | 'rejected' | 'refunded' | 'cancelled' | string;
  payment_method: string;
  offline_payment_reference?: string | null;
  admin_notes?: string | null;
  stripe_payment_intent_id?: string | null;
  access_token: string;
  items: BookingItemOut[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface PaymentIntentResponse {
  client_secret: string;
  publishable_key: string;
  payment_intent_id: string;
  amount_cents: number;
  currency: string;
}

export interface AdminOrder {
  id: string;
  event_id: string;
  order_number: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email?: string | null;
  phone: string;
  street_address?: string | null;
  postal_code?: string | null;
  city?: string | null;
  honor_declaration_accepted: boolean;
  honor_declaration_accepted_at?: string | null;
  total_price_cents: number;
  total_price: number;
  status: 'pending' | 'pending_approval' | 'confirmed' | 'rejected' | 'refunded' | 'cancelled' | string;
  payment_method: 'stripe' | 'check' | 'cash' | 'other' | string;
  is_offline: boolean;
  offline_payment_reference?: string | null;
  admin_notes?: string | null;
  stripe_payment_intent_id?: string | null;
  access_token: string;
  items: BookingItemOut[];
  spot_labels: string[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DashboardStats {
  total_spots: number;
  reserved_spots: number;
  locked_spots: number;
  available_spots: number;
  occupancy_rate: number;
  total_revenue_cents: number;
  total_revenue: number;
  stripe_revenue_cents: number;
  stripe_revenue: number;
  offline_revenue_cents: number;
  offline_revenue: number;
  offline_check_cents: number;
  offline_check_revenue: number;
  offline_cash_cents: number;
  offline_cash_revenue: number;
  offline_other_cents: number;
  offline_other_revenue: number;
  total_orders_count: number;
  confirmed_orders_count: number;
  pending_orders_count: number;
  offline_orders_count: number;
  pending_approval_orders_count?: number;
}

export interface OrderApprovalAction {
  reason?: string;
}

export interface AdminOrderListResponse {
  items: AdminOrder[];
  total: number;
  stats?: DashboardStats | null;
}

export interface OfflineBookingPayload {
  spot_ids: string[];
  first_name: string;
  last_name: string;
  email?: string;
  phone: string;
  street_address?: string;
  postal_code?: string;
  city?: string;
  payment_method: 'check' | 'cash' | 'other';
  offline_payment_reference?: string;
  admin_notes?: string;
  custom_price_cents?: number;
}


