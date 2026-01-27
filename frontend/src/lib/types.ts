// Core entity types matching backend schemas

export interface ServiceTypeSummary {
  id: string;
  name: string;
  duration_minutes: number;
  price_cents: number;
  currency: string;
}

export interface Organization {
  id: string;
  name: string;
  phone_country_code: string;
  phone_number: string;
  timezone: string;
  whatsapp_phone_number_id: string | null;
  whatsapp_waba_id: string | null;
  status: string;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Location {
  id: string;
  organization_id: string;
  name: string;
  address: string | null;
  is_primary: boolean;
  business_hours: Record<string, { open: string; close: string }>;
  created_at: string;
  updated_at: string;
}

export interface Spot {
  id: string;
  location_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  display_order: number;
  service_types: ServiceTypeSummary[];
  created_at: string;
  updated_at: string;
}

export interface Staff {
  id: string;
  organization_id: string;
  location_id: string | null;
  default_spot_id: string | null;
  name: string;
  phone_number: string;
  role: 'owner' | 'employee';
  permissions: Record<string, boolean>;
  is_active: boolean;
  settings: Record<string, unknown>;
  service_types: ServiceTypeSummary[];
  created_at: string;
  updated_at: string;
}

export interface ServiceType {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  duration_minutes: number;
  price_cents: number;
  currency: string;
  is_active: boolean;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Customer {
  id: string;
  organization_id: string;
  phone_number: string;
  name: string | null;
  email: string | null;
  notes: string | null;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Appointment {
  id: string;
  organization_id: string;
  location_id: string;
  customer_id: string;
  staff_id: string | null;
  service_type_id: string;
  spot_id: string | null;
  scheduled_start: string;
  scheduled_end: string;
  status: 'pending' | 'confirmed' | 'completed' | 'cancelled' | 'no_show';
  source: 'whatsapp' | 'web' | 'manual' | 'walk_in';
  notes: string | null;
  cancellation_reason: string | null;
  reminder_sent_at: string | null;
  created_at: string;
  updated_at: string;
}

// Form types for creating/updating
export interface AppointmentCreate {
  customer_id: string;
  service_type_id: string;
  staff_id?: string | null;
  location_id: string;
  spot_id?: string | null;
  scheduled_start: string;
  scheduled_end: string;
  notes?: string | null;
  source?: string;
}

export interface StaffCreate {
  name: string;
  phone_number: string;
  role?: string;
  location_id?: string | null;
  default_spot_id?: string | null;
  permissions?: Record<string, boolean>;
  is_active?: boolean;
  settings?: Record<string, unknown>;
}

export interface LocationCreate {
  name: string;
  address?: string | null;
  is_primary?: boolean;
  business_hours?: Record<string, { open: string; close: string }>;
}

export interface SpotCreate {
  name: string;
  description?: string | null;
  is_active?: boolean;
  display_order?: number;
}

export interface ServiceTypeCreate {
  name: string;
  description?: string | null;
  duration_minutes: number;
  price_cents: number;
  currency?: string;
  is_active?: boolean;
  settings?: Record<string, unknown>;
}

export interface StaffUpdate {
  name?: string;
  phone_number?: string;
  role?: string;
  location_id?: string | null;
  default_spot_id?: string | null;
  permissions?: Record<string, boolean>;
  is_active?: boolean;
  settings?: Record<string, unknown>;
}

export interface LocationUpdate {
  name?: string;
  address?: string | null;
  is_primary?: boolean;
  business_hours?: Record<string, { open: string; close: string }>;
}

export interface SpotUpdate {
  name?: string;
  description?: string | null;
  is_active?: boolean;
  display_order?: number;
}

export interface ServiceTypeUpdate {
  name?: string;
  description?: string | null;
  duration_minutes?: number;
  price_cents?: number;
  currency?: string;
  is_active?: boolean;
  settings?: Record<string, unknown>;
}

// Availability types
export interface Availability {
  id: string;
  staff_id: string;
  availability_type: 'regular' | 'exception';
  day_of_week: number | null;
  specific_date: string | null;
  start_time: string;
  end_time: string;
  is_available: boolean;
  created_at: string;
  updated_at: string;
}

export interface AvailabilityCreate {
  availability_type: 'regular' | 'exception';
  day_of_week?: number | null;
  specific_date?: string | null;
  start_time: string;
  end_time: string;
  is_available?: boolean;
}

// Admin types
export interface AdminLoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface AdminOrganizationSummary {
  id: string;
  name: string;
  phone_number: string;
  phone_country_code: string;
  status: string;
  whatsapp_connected: boolean;
  created_at: string;
}

export interface AdminOrganizationDetail extends AdminOrganizationSummary {
  timezone: string;
  settings: Record<string, unknown>;
  location_count: number;
  staff_count: number;
  customer_count: number;
  appointment_count: number;
}

export interface AdminStats {
  organizations: {
    total: number;
    active: number;
    onboarding: number;
    suspended: number;
    churned: number;
  };
  appointments: {
    total: number;
    pending: number;
    confirmed: number;
    completed: number;
    cancelled: number;
    no_show: number;
  };
  customers_total: number;
  messages_total: number;
}

export interface AdminConversationSummary {
  id: string;
  organization_id: string;
  organization_name: string;
  customer_phone: string;
  customer_name: string | null;
  status: string;
  message_count: number;
  last_message_at: string | null;
  created_at: string;
}

export interface AdminMessageDetail {
  id: string;
  direction: 'inbound' | 'outbound';
  sender_type: 'customer' | 'ai' | 'staff';
  content: string;
  content_type: string;
  created_at: string;
}

export interface AdminConversationDetail extends AdminConversationSummary {
  messages: AdminMessageDetail[];
}

export interface AdminActivityItem {
  id: string;
  timestamp: string;
  organization_id: string;
  organization_name: string;
  action_type: string;
  details: Record<string, unknown>;
}

export interface AdminImpersonateResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  organization: AdminOrganizationSummary;
}

// Playground types
export interface PlaygroundUserSummary {
  phone_number: string;
  name: string | null;
  user_type: 'staff' | 'customer';
  organization_id: string;
  organization_name: string;
  role: string | null;
  user_id: string;
}

export interface PlaygroundUserDetail extends PlaygroundUserSummary {
  created_at: string;
  is_active: boolean | null;
  appointment_count: number | null;
}

export interface PlaygroundSendRequest {
  phone_number: string;
  message_content: string;
}

export interface PlaygroundSendResponse {
  response_text: string;
  exchange_id: string;
  latency_ms: number;
  route: string;
  organization_id: string | null;
}

export interface TraceStepSummary {
  id: string;
  trace_type: string;
  sequence_number: number;
  latency_ms: number;
  is_error: boolean;
  tool_name: string | null;
  llm_call_number: number | null;
}

export interface TraceExchangeSummary {
  exchange_id: string;
  created_at: string;
  total_latency_ms: number;
  step_count: number;
  user_message_preview: string | null;
  ai_response_preview: string | null;
  steps: TraceStepSummary[];
}

export interface TraceStepDetail {
  id: string;
  exchange_id: string;
  trace_type: string;
  sequence_number: number;
  started_at: string;
  completed_at: string;
  latency_ms: number;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  metadata: Record<string, unknown>;
  is_error: boolean;
  error_message: string | null;
}

export interface PlaygroundExchangeListResponse {
  phone_number: string;
  exchanges: TraceExchangeSummary[];
}

export interface PlaygroundTraceListResponse {
  exchange_id: string;
  total_latency_ms: number;
  traces: TraceStepSummary[];
}
