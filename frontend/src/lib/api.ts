import { EventCreateInput, EventUpdateInput, EventListResponse, EventModel } from '../types/event';
import {
  SpotCreateInput,
  SpotUpdateInput,
  SpotFeature,
  SpotFeatureCollection,
  SpotBatchCreateInput,
  SpotBatchCreateResponse,
  SpotBatchRenumberInput,
  SpotBatchRenumberResponse,
} from '../types/spot';

import {
  LoginCredentials,
  LoginResponse,
  User,
  AdminUserListItem,
  CreateUserData,
  UpdateUserData,
  ResetPasswordData,
} from '../types/auth';

const API_BASE = import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api/v1` : '/api/v1';
const TOKEN_KEY = 'gvg_access_token';

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuthToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
}

export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401 && token) {
    clearAuthToken();
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('gvg:auth:expired'));
    }
  }
  return response;
}

export async function loginApi(credentials: LoginCredentials): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(credentials),
  });

  if (!response.ok) {
    let detail = 'Identifiants invalides';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  const data: LoginResponse = await response.json();
  setAuthToken(data.access_token);
  return data;
}

export async function fetchCurrentUser(): Promise<User> {
  const response = await authFetch(`${API_BASE}/auth/me`);
  if (!response.ok) {
    let detail = 'Impossible de charger les informations du compte';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string | Record<string, unknown>[]) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail));
    this.name = 'ApiError';
  }
}

export async function createEvent(data: EventCreateInput): Promise<EventModel> {
  const response = await authFetch(`${API_BASE}/events`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let detail = 'Erreur lors de la création de l’événement';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function updateEvent(idOrSlug: string, data: EventUpdateInput): Promise<EventModel> {
  const response = await authFetch(`${API_BASE}/events/${encodeURIComponent(idOrSlug)}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let detail = 'Erreur lors de la mise à jour de l’événement';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function uploadBackgroundImage(eventIdOrSlug: string, file: File): Promise<EventModel> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await authFetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/background-image`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    let detail = 'Erreur lors du téléversement du fond de plan';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function uploadEventPoster(eventIdOrSlug: string, file: File): Promise<EventModel> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await authFetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/poster`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    let detail = 'Erreur lors du téléversement de l’affiche';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function deleteEventPoster(eventIdOrSlug: string): Promise<EventModel> {
  const response = await authFetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/poster`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    let detail = 'Erreur lors de la suppression de l’affiche';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function fetchEvents(): Promise<EventListResponse> {
  const response = await authFetch(`${API_BASE}/events`);
  if (!response.ok) {
    throw new Error('Erreur lors de la récupération des événements');
  }
  return response.json();
}

export async function fetchEvent(idOrSlug: string): Promise<EventModel> {
  const response = await authFetch(`${API_BASE}/events/${encodeURIComponent(idOrSlug)}`);
  if (!response.ok) {
    throw new Error('Événement introuvable');
  }
  return response.json();
}

export function getImageUrl(path?: string | null): string {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  const baseUrl = import.meta.env.VITE_API_URL || '';
  return `${baseUrl}${path}`;
}

export async function fetchSpots(eventIdOrSlug: string): Promise<SpotFeatureCollection> {
  const response = await authFetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/spots`);
  if (!response.ok) {
    let detail = 'Erreur lors de la récupération des emplacements';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}

export async function createSpot(eventIdOrSlug: string, data: SpotCreateInput): Promise<SpotFeature> {
  const response = await authFetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/spots`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let detail = 'Erreur lors de la création du stand';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function updateSpot(
  eventIdOrSlug: string,
  spotId: string,
  data: SpotUpdateInput
): Promise<SpotFeature> {
  const response = await authFetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/spots/${encodeURIComponent(spotId)}`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    let detail = 'Erreur lors de la mise à jour du stand';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function deleteSpot(eventIdOrSlug: string, spotId: string): Promise<void> {
  const response = await authFetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/spots/${encodeURIComponent(spotId)}`,
    {
      method: 'DELETE',
    }
  );

  if (!response.ok) {
    let detail = 'Erreur lors de la suppression du stand';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
}

export async function createSpotsBatch(
  eventIdOrSlug: string,
  data: SpotBatchCreateInput
): Promise<SpotBatchCreateResponse> {
  const response = await authFetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/spots/batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let detail = 'Erreur lors de la création groupée des stands';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function renumberSpotsBatch(
  eventIdOrSlug: string,
  data: SpotBatchRenumberInput
): Promise<SpotBatchRenumberResponse> {
  const response = await authFetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/spots/batch-renumber`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    let detail = 'Erreur lors de la renumérotation des stands';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function fetchPublicEvents(search?: string): Promise<import('../types/public').PublicEventListItem[]> {
  const query = search && search.trim() ? `?search=${encodeURIComponent(search.trim())}` : '';
  const response = await authFetch(`${API_BASE}/public/events${query}`);
  if (!response.ok) {
    let detail = 'Erreur lors du chargement des événements';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}

export async function fetchPublicEvent(slug: string): Promise<import('../types/public').PublicEventResponse> {
  const response = await authFetch(`${API_BASE}/public/events/${encodeURIComponent(slug)}`);
  if (!response.ok) {
    let detail = 'Événement introuvable';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}

export async function fetchPublicSpots(slug: string): Promise<import('../types/public').PublicSpotFeatureCollection> {
  const response = await authFetch(`${API_BASE}/public/events/${encodeURIComponent(slug)}/spots`);
  if (!response.ok) {
    let detail = 'Erreur lors de la récupération des emplacements';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}

export async function lockSpot(
  slug: string,
  spotId: string,
  sessionToken: string
): Promise<import('../types/public').CartResponse> {
  const response = await authFetch(
    `${API_BASE}/public/events/${encodeURIComponent(slug)}/spots/${encodeURIComponent(spotId)}/lock`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Token': sessionToken,
      },
      body: JSON.stringify({ session_token: sessionToken }),
    }
  );

  if (!response.ok) {
    let detail = 'Impossible de verrouiller cet emplacement';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function unlockSpot(
  slug: string,
  spotId: string,
  sessionToken: string
): Promise<import('../types/public').CartResponse> {
  const response = await authFetch(
    `${API_BASE}/public/events/${encodeURIComponent(slug)}/spots/${encodeURIComponent(spotId)}/unlock`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Token': sessionToken,
      },
      body: JSON.stringify({ session_token: sessionToken }),
    }
  );

  if (!response.ok) {
    let detail = 'Impossible de déverrouiller cet emplacement';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function fetchCart(
  slug: string,
  sessionToken: string
): Promise<import('../types/public').CartResponse> {
  const response = await authFetch(
    `${API_BASE}/public/events/${encodeURIComponent(slug)}/cart?session_token=${encodeURIComponent(sessionToken)}`,
    {
      headers: {
        'X-Session-Token': sessionToken,
      },
    }
  );

  if (!response.ok) {
    let detail = 'Impossible de récupérer le panier';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function createGuestOrder(
  slug: string,
  payload: import('../types/order').GuestOrderCreate
): Promise<import('../types/order').OrderOut> {
  const response = await authFetch(`${API_BASE}/public/events/${encodeURIComponent(slug)}/orders`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Session-Token': payload.session_token,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = 'Erreur lors de la réservation';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function fetchPublicOrder(
  slug: string,
  orderId: string,
  accessToken: string
): Promise<import('../types/order').OrderOut> {
  const response = await authFetch(
    `${API_BASE}/public/events/${encodeURIComponent(slug)}/orders/${encodeURIComponent(orderId)}?token=${encodeURIComponent(accessToken)}`,
    {
      headers: {
        'X-Access-Token': accessToken,
      },
    }
  );

  if (!response.ok) {
    let detail = 'Commande introuvable';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function createPaymentIntent(
  slug: string,
  orderId: string,
  accessToken: string
): Promise<import('../types/order').PaymentIntentResponse> {
  const response = await authFetch(
    `${API_BASE}/public/events/${encodeURIComponent(slug)}/orders/${encodeURIComponent(orderId)}/payment-intent?token=${encodeURIComponent(accessToken)}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Access-Token': accessToken,
      },
    }
  );

  if (!response.ok) {
    let detail = 'Erreur lors de l’initialisation du paiement sécurisé';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function fetchEventOrders(
  eventIdOrSlug: string,
  status?: string,
  search?: string,
  skip: number = 0,
  limit: number = 100
): Promise<import('../types/order').AdminOrderListResponse> {
  const params = new URLSearchParams();
  if (status && status !== 'all') {
    params.set('status', status);
  }
  if (search && search.trim()) {
    params.set('search', search.trim());
  }
  if (skip > 0) {
    params.set('skip', String(skip));
  }
  if (limit !== 100) {
    params.set('limit', String(limit));
  }

  const queryString = params.toString() ? `?${params.toString()}` : '';
  const response = await authFetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/orders${queryString}`
  );

  if (!response.ok) {
    let detail = 'Erreur lors de la récupération des inscriptions';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function fetchEventDashboardStats(
  eventIdOrSlug: string
): Promise<import('../types/order').DashboardStats> {
  const response = await authFetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/dashboard-stats`
  );

  if (!response.ok) {
    let detail = 'Erreur lors de la récupération des statistiques';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function createManualBooking(
  eventIdOrSlug: string,
  payload: import('../types/order').OfflineBookingPayload
): Promise<import('../types/order').AdminOrder> {
  const response = await authFetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/orders/manual`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    let detail = 'Erreur lors de la création de la réservation manuelle';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function approveOrder(
  eventIdOrSlug: string,
  orderId: string,
  payload?: import('../types/order').OrderApprovalAction
): Promise<import('../types/order').AdminOrder> {
  const response = await authFetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/orders/${encodeURIComponent(orderId)}/approve`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload || {}),
    }
  );

  if (!response.ok) {
    let detail = 'Erreur lors de la validation de la commande';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function rejectOrder(
  eventIdOrSlug: string,
  orderId: string,
  payload?: import('../types/order').OrderApprovalAction
): Promise<import('../types/order').AdminOrder> {
  const response = await authFetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/orders/${encodeURIComponent(orderId)}/reject`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload || {}),
    }
  );

  if (!response.ok) {
    let detail = 'Erreur lors du refus de la commande';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function submitCancellationRequest(
  slug: string,
  orderId: string,
  accessToken: string,
  payload: import('../types/order').CancellationRequestIn
): Promise<import('../types/order').OrderOut> {
  const response = await authFetch(
    `${API_BASE}/public/events/${encodeURIComponent(slug)}/orders/${encodeURIComponent(orderId)}/cancellation-request?token=${encodeURIComponent(accessToken)}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Access-Token': accessToken,
      },
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    let detail = "Erreur lors de la soumission de la demande d'annulation";
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function refundOrder(
  eventIdOrSlug: string,
  orderId: string,
  payload?: import('../types/order').OrderRefundAction
): Promise<import('../types/order').AdminOrder> {
  const response = await authFetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/orders/${encodeURIComponent(orderId)}/refund`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload || {}),
    }
  );

  if (!response.ok) {
    let detail = 'Erreur lors du remboursement de la commande';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function rejectCancellationRequest(
  eventIdOrSlug: string,
  orderId: string,
  payload: import('../types/order').OrderRejectCancellationAction
): Promise<import('../types/order').AdminOrder> {
  const response = await authFetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/orders/${encodeURIComponent(orderId)}/reject-cancellation`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    let detail = "Erreur lors du refus de la demande d'annulation";
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function cancelAndRefundAllEventOrders(
  eventIdOrSlug: string,
  payload: import('../types/order').BulkEventCancelIn
): Promise<import('../types/order').BulkEventCancelResponse> {
  const response = await authFetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/cancel-and-refund-all`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    let detail = "Erreur lors de l'annulation générale et du remboursement groupé";
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function fetchEventReminderStatus(
  eventIdOrSlug: string
): Promise<import('../types/reminder').ReminderStatus> {
  const response = await authFetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/reminders/status`);
  if (!response.ok) {
    let detail = 'Erreur lors de la récupération du statut des rappels';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}

export async function triggerEventReminders(
  eventIdOrSlug: string,
  reminderType?: 'j7' | 'j2' | null,
  force: boolean = false
): Promise<import('../types/reminder').ReminderTriggerReport> {
  const response = await authFetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/reminders/trigger`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      reminder_type: reminderType,
      force,
    }),
  });

  if (!response.ok) {
    let detail = 'Erreur lors du déclenchement des rappels';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function previewBroadcastEmail(
  eventIdOrSlug: string,
  payload: import('../types/broadcast').BroadcastPreviewRequest
): Promise<import('../types/broadcast').BroadcastPreviewResponse> {
  const response = await authFetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/broadcast/preview`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = "Erreur lors de la prévisualisation de l'e-mail";
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function sendBroadcastEmail(
  eventIdOrSlug: string,
  payload: import('../types/broadcast').BroadcastSendRequest
): Promise<import('../types/broadcast').BroadcastSendResponse> {
  const response = await authFetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/broadcast/send`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = "Erreur lors de l'envoi de la diffusion";
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export function getPublicAttestationPdfUrl(slug: string, orderId: string, token: string): string {
  return `${API_BASE}/public/events/${encodeURIComponent(slug)}/orders/${encodeURIComponent(orderId)}/attestation.pdf?token=${encodeURIComponent(token)}`;
}

export function getAdminAttestationPdfUrl(eventIdOrSlug: string, orderId: string): string {
  const token = getAuthToken();
  const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/orders/${encodeURIComponent(orderId)}/attestation.pdf${tokenQuery}`;
}

export function getAdminCheckinPdfUrl(eventIdOrSlug: string, sortBy: 'spot' | 'alpha' = 'spot'): string {
  const token = getAuthToken();
  const tokenParam = token ? `&token=${encodeURIComponent(token)}` : '';
  return `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/checkin.pdf?sort_by=${encodeURIComponent(sortBy)}${tokenParam}`;
}

export function getAdminCheckinXlsxUrl(eventIdOrSlug: string, sortBy?: 'spot' | 'alpha'): string {
  const token = getAuthToken();
  const params = new URLSearchParams();
  if (sortBy) params.set('sort_by', sortBy);
  if (token) params.set('token', token);
  const query = params.toString() ? `?${params.toString()}` : '';
  return `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/checkin.xlsx${query}`;
}

export async function deleteEvent(idOrSlug: string): Promise<void> {
  const response = await authFetch(`${API_BASE}/events/${encodeURIComponent(idOrSlug)}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    let detail = "Impossible de supprimer l'événement";
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
}

export async function fetchAdminUsers(): Promise<AdminUserListItem[]> {
  const response = await authFetch(`${API_BASE}/admin/users`);
  if (!response.ok) {
    let detail = 'Impossible de récupérer la liste des utilisateurs';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}

export async function createAdminUser(data: CreateUserData): Promise<AdminUserListItem> {
  const response = await authFetch(`${API_BASE}/admin/users`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let detail = "Impossible de créer l'utilisateur";
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}

export async function updateAdminUser(
  userId: string,
  data: UpdateUserData
): Promise<AdminUserListItem> {
  const response = await authFetch(`${API_BASE}/admin/users/${encodeURIComponent(userId)}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let detail = "Impossible de mettre à jour l'utilisateur";
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}

export async function resetAdminUserPassword(
  userId: string,
  data: ResetPasswordData
): Promise<{ message: string }> {
  const response = await authFetch(
    `${API_BASE}/admin/users/${encodeURIComponent(userId)}/reset-password`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    let detail = 'Impossible de réinitialiser le mot de passe';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}



