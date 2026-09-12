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
  email: string;
  phone: string;
  street_address: string;
  postal_code: string;
  city: string;
  honor_declaration_accepted: boolean;
  honor_declaration_accepted_at: string;
  total_price_cents: number;
  total_price: number;
  status: 'pending' | 'confirmed' | 'refunded' | 'cancelled' | string;
  payment_method: string;
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

