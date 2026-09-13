export interface ReminderStatus {
  event_id: string;
  event_slug: string;
  event_title: string;
  start_date: string;
  days_until_event: number;
  j7_eligible: boolean;
  j7_sent_count: number;
  j2_eligible: boolean;
  j2_sent_count: number;
  total_confirmed_orders: number;
  total_confirmed_with_email: number;
}

export interface ReminderTriggerReport {
  event_id: string;
  event_title: string;
  reminder_type: string;
  orders_processed: number;
  reminders_sent: number;
  reminders_skipped: number;
  orders_without_email: number;
  errors: string[];
}

