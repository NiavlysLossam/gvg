import { EventCreateInput, EventListResponse, EventModel } from '../types/event';

const API_BASE = import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api/v1` : '/api/v1';

export class ApiError extends Error {
  constructor(public status: number, public detail: string | Record<string, unknown>[]) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail));
    this.name = 'ApiError';
  }
}

export async function createEvent(data: EventCreateInput): Promise<EventModel> {
  const response = await fetch(`${API_BASE}/events`, {
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

export async function fetchEvents(): Promise<EventListResponse> {
  const response = await fetch(`${API_BASE}/events`);
  if (!response.ok) {
    throw new Error('Erreur lors de la récupération des événements');
  }
  return response.json();
}

export async function fetchEvent(idOrSlug: string): Promise<EventModel> {
  const response = await fetch(`${API_BASE}/events/${encodeURIComponent(idOrSlug)}`);
  if (!response.ok) {
    throw new Error('Événement introuvable');
  }
  return response.json();
}

